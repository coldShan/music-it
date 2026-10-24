import type { PlaybackEvent } from '@music-it/shared-types'

import type { PlaybackMode } from './player'

export type PracticeStep = {
  index: number
  beat: number
  measure: number
  required: number[]
  accompaniment: PlaybackEvent[]
}

export type PracticeRange = { startMeasure: number; endMeasure: number } | null
export type AutoPlayCue = { delayBeats: number; events: PlaybackEvent[] }
export type PracticeFeedback =
  | 'none'
  | 'hit'
  | 'wrong'
  | 'step-complete'
  | 'loop'
  | 'finished'

export type PracticeState = {
  steps: PracticeStep[]
  current: number
  hits: number[]
  loop: boolean
  passes: number
  wrongCount: number
  wrongByMeasure: Record<number, number>
  startedAt: number | null
  finishedAt: number | null
}

export type PracticeOutput = {
  state: PracticeState
  autoPlay: AutoPlayCue[]
  feedback: PracticeFeedback
}

function inRange(event: PlaybackEvent, range: PracticeRange | undefined): boolean {
  if (!range) return true
  return event.sourceMeasure >= range.startMeasure && event.sourceMeasure <= range.endMeasure
}

export function buildPracticeSteps(
  events: PlaybackEvent[],
  mode: PlaybackMode,
  range?: PracticeRange,
): PracticeStep[] {
  const groups = new Map<number, PlaybackEvent[]>()

  for (const event of events) {
    if (!inRange(event, range)) continue
    const key = Math.round(event.startBeat * 1000)
    const group = groups.get(key)
    if (group) {
      group.push(event)
    } else {
      groups.set(key, [event])
    }
  }

  return Array.from(groups.entries())
    .sort(([left], [right]) => left - right)
    .map(([, group], index) => {
      const required = new Set<number>()
      const accompaniment: PlaybackEvent[] = []

      for (const event of group) {
        if (mode === 'both' || event.hand === mode) {
          for (const midi of event.midis) {
            required.add(midi)
          }
        } else {
          accompaniment.push(event)
        }
      }

      return {
        index,
        beat: group[0].startBeat,
        measure: Math.min(...group.map((event) => event.sourceMeasure)),
        required: Array.from(required).sort((left, right) => left - right),
        accompaniment,
      }
    })
}

function cueAfter(step: PracticeStep, steps: PracticeStep[], delayOffset = 0): AutoPlayCue[] {
  const cues: AutoPlayCue[] = []
  if (step.accompaniment.length > 0) {
    cues.push({ delayBeats: delayOffset, events: step.accompaniment })
  }

  for (let index = step.index + 1; index < steps.length; index += 1) {
    const next = steps[index]
    if (next.required.length > 0) break
    cues.push({
      delayBeats: next.beat - step.beat + delayOffset,
      events: next.accompaniment,
    })
  }

  return cues
}

function firstRequiredIndex(steps: PracticeStep[]): number {
  return steps.findIndex((step) => step.required.length > 0)
}

function openingCues(steps: PracticeStep[], delayOffset = 0): AutoPlayCue[] {
  const cues: AutoPlayCue[] = []
  const firstBeat = steps[0]?.beat ?? 0

  for (const step of steps) {
    if (step.required.length > 0) break
    cues.push({ delayBeats: step.beat - firstBeat + delayOffset, events: step.accompaniment })
  }

  return cues
}

export function startPractice(
  steps: PracticeStep[],
  options: { loop?: boolean } = {},
): PracticeOutput {
  const state: PracticeState = {
    steps,
    current: 0,
    hits: [],
    loop: options.loop ?? false,
    passes: 0,
    wrongCount: 0,
    wrongByMeasure: {},
    startedAt: null,
    finishedAt: null,
  }

  const firstRequired = firstRequiredIndex(steps)
  const autoPlay = openingCues(steps)

  if (firstRequired === -1) {
    return {
      state: { ...state, current: steps.length },
      autoPlay,
      feedback: 'finished',
    }
  }

  return {
    state: { ...state, current: firstRequired },
    autoPlay,
    feedback: 'none',
  }
}

function completedStepOutput(
  state: PracticeState,
  step: PracticeStep,
  now: number,
): PracticeOutput {
  const nextRequired = state.steps.findIndex(
    (candidate, index) => index > step.index && candidate.required.length > 0,
  )
  const autoPlay = cueAfter(step, state.steps)

  if (nextRequired !== -1) {
    return {
      state: {
        ...state,
        current: nextRequired,
        hits: [],
      },
      autoPlay,
      feedback: 'step-complete',
    }
  }

  const passes = state.passes + 1
  if (state.loop) {
    const firstRequired = firstRequiredIndex(state.steps)
    return {
      state: {
        ...state,
        current: firstRequired === -1 ? state.steps.length : firstRequired,
        hits: [],
        passes,
        finishedAt: null,
      },
      autoPlay: [...autoPlay, ...openingCues(state.steps, 1)],
      feedback: 'loop',
    }
  }

  return {
    state: {
      ...state,
      current: state.steps.length,
      hits: [],
      passes,
      finishedAt: now,
    },
    autoPlay,
    feedback: 'finished',
  }
}

export function handleNoteOn(state: PracticeState, midi: number, now: number): PracticeOutput {
  if (state.current >= state.steps.length) {
    return { state, autoPlay: [], feedback: 'none' }
  }

  const step = state.steps[state.current]
  const startedAt = state.startedAt ?? now

  if (!step.required.includes(midi)) {
    return {
      state: {
        ...state,
        startedAt,
        wrongCount: state.wrongCount + 1,
        wrongByMeasure: {
          ...state.wrongByMeasure,
          [step.measure]: (state.wrongByMeasure[step.measure] ?? 0) + 1,
        },
      },
      autoPlay: [],
      feedback: 'wrong',
    }
  }

  if (state.hits.includes(midi)) {
    return {
      state: state.startedAt === null ? { ...state, startedAt } : state,
      autoPlay: [],
      feedback: 'none',
    }
  }

  const hits = [...state.hits, midi]
  const completed = step.required.every((requiredMidi) => hits.includes(requiredMidi))

  if (!completed) {
    return {
      state: { ...state, startedAt, hits },
      autoPlay: [],
      feedback: 'hit',
    }
  }

  return completedStepOutput({ ...state, startedAt, hits }, step, now)
}

export function summarizePractice(
  state: PracticeState,
  now: number,
): {
  passes: number
  wrongCount: number
  elapsedMs: number
  worstMeasures: { measure: number; count: number }[]
} {
  const elapsedMs =
    state.startedAt === null ? 0 : (state.finishedAt ?? now) - state.startedAt

  const worstMeasures = Object.entries(state.wrongByMeasure)
    .map(([measure, count]) => ({ measure: Number(measure), count }))
    .filter((entry) => entry.count > 0)
    .sort((left, right) => right.count - left.count || left.measure - right.measure)
    .slice(0, 3)

  return {
    passes: state.passes,
    wrongCount: state.wrongCount,
    elapsedMs,
    worstMeasures,
  }
}
