import { describe, expect, it } from 'vitest'
import type { PlaybackEvent } from '@music-it/shared-types'

import {
  buildPracticeSteps,
  handleNoteOn,
  startPractice,
  summarizePractice,
  type PracticeState,
  type PracticeStep,
} from './practice'

function event(overrides: Partial<PlaybackEvent> & Pick<PlaybackEvent, 'startBeat' | 'hand' | 'midis'>): PlaybackEvent {
  const pitches = overrides.midis.map((midi) => String(midi))
  return {
    durationBeat: 1,
    gateBeat: 0.9,
    pitches,
    staff: overrides.hand === 'right' ? '1' : '2',
    voice: '1',
    sourceMeasure: 1,
    ...overrides,
  }
}

function step(overrides: Partial<PracticeStep> & Pick<PracticeStep, 'index' | 'beat' | 'required'>): PracticeStep {
  return {
    measure: 1,
    accompaniment: [],
    ...overrides,
  }
}

describe('buildPracticeSteps', () => {
  const events = [
    event({ startBeat: 0, hand: 'right', midis: [60], sourceMeasure: 1 }),
    event({ startBeat: 0, hand: 'left', midis: [48, 55], sourceMeasure: 1 }),
    event({ startBeat: 1, hand: 'right', midis: [62], sourceMeasure: 1 }),
    event({ startBeat: 2, hand: 'left', midis: [50], sourceMeasure: 2 }),
  ]

  it('groups events by beat and keeps both hands as required in both mode', () => {
    const steps = buildPracticeSteps(events, 'both')

    expect(steps.map((entry) => entry.beat)).toEqual([0, 1, 2])
    expect(steps.map((entry) => entry.required)).toEqual([[48, 55, 60], [62], [50]])
    expect(steps.every((entry) => entry.accompaniment.length === 0)).toBe(true)
    expect(steps.map((entry) => entry.index)).toEqual([0, 1, 2])
    expect(steps[0].measure).toBe(1)
  })

  it('puts the other hand into accompaniment for right-hand practice', () => {
    const steps = buildPracticeSteps(events, 'right')

    expect(steps[0].required).toEqual([60])
    expect(steps[0].accompaniment).toEqual([events[1]])
    expect(steps[1].required).toEqual([62])
    expect(steps[1].accompaniment).toEqual([])
    expect(steps[2].required).toEqual([])
    expect(steps[2].accompaniment).toEqual([events[3]])
  })

  it('puts the other hand into accompaniment for left-hand practice', () => {
    const steps = buildPracticeSteps(events, 'left')

    expect(steps[0].required).toEqual([48, 55])
    expect(steps[0].accompaniment).toEqual([events[0]])
    expect(steps[1].required).toEqual([])
    expect(steps[1].accompaniment).toEqual([events[2]])
    expect(steps[2].required).toEqual([50])
    expect(steps[2].accompaniment).toEqual([])
  })

  it('filters by an inclusive measure range', () => {
    const steps = buildPracticeSteps(events, 'both', { startMeasure: 1, endMeasure: 1 })

    expect(steps).toHaveLength(2)
    expect(steps.map((entry) => entry.beat)).toEqual([0, 1])
  })

  it('rounds beat keys before grouping', () => {
    const steps = buildPracticeSteps(
      [
        event({ startBeat: 0.0001, hand: 'right', midis: [60] }),
        event({ startBeat: 0.0004, hand: 'left', midis: [48] }),
      ],
      'both',
    )

    expect(steps).toHaveLength(1)
    expect(steps[0].required).toEqual([48, 60])
  })
})

describe('startPractice', () => {
  it('returns leading automatic steps before the first required step', () => {
    const left = event({ startBeat: 0, hand: 'left', midis: [48] })
    const steps = [
      step({ index: 0, beat: 0, required: [], accompaniment: [left] }),
      step({ index: 1, beat: 1, required: [60] }),
    ]

    const output = startPractice(steps)

    expect(output.state.current).toBe(1)
    expect(output.autoPlay).toEqual([{ delayBeats: 0, events: [left] }])
    expect(output.feedback).toBe('none')
  })

  it('finishes immediately when every step is automatic', () => {
    const first = event({ startBeat: 0, hand: 'left', midis: [48] })
    const second = event({ startBeat: 2, hand: 'left', midis: [50] })
    const steps = [
      step({ index: 0, beat: 0, required: [], accompaniment: [first] }),
      step({ index: 1, beat: 2, required: [], accompaniment: [second] }),
    ]

    const output = startPractice(steps)

    expect(output.state.current).toBe(2)
    expect(output.feedback).toBe('finished')
    expect(output.autoPlay).toEqual([
      { delayBeats: 0, events: [first] },
      { delayBeats: 2, events: [second] },
    ])
  })
})

describe('handleNoteOn', () => {
  it('advances after the required single note and ignores repeated notes', () => {
    const steps = [
      step({ index: 0, beat: 0, required: [60] }),
      step({ index: 1, beat: 1, required: [62] }),
    ]
    const started = startPractice(steps).state

    const first = handleNoteOn(started, 60, 100)
    expect(first.feedback).toBe('step-complete')
    expect(first.state.current).toBe(1)
    expect(first.state.startedAt).toBe(100)

    const repeated = handleNoteOn(first.state, 60, 130)
    expect(repeated.feedback).toBe('wrong')
    expect(repeated.state.wrongCount).toBe(1)
  })

  it('counts wrong notes without moving forward', () => {
    const state = startPractice([step({ index: 0, beat: 0, required: [60], measure: 3 })], {
      loop: false,
    }).state

    const output = handleNoteOn(state, 61, 50)

    expect(output.feedback).toBe('wrong')
    expect(output.state.current).toBe(0)
    expect(output.state.hits).toEqual([])
    expect(output.state.wrongCount).toBe(1)
    expect(output.state.wrongByMeasure).toEqual({ 3: 1 })
    expect(output.state.startedAt).toBe(50)
  })

  it('does not double-count a repeated correct note inside one step', () => {
    const state = startPractice([step({ index: 0, beat: 0, required: [60, 64] })]).state
    const first = handleNoteOn(state, 60, 10)
    const repeated = handleNoteOn(first.state, 60, 20)

    expect(first.feedback).toBe('hit')
    expect(repeated.feedback).toBe('none')
    expect(repeated.state.hits).toEqual([60])
    expect(repeated.state.wrongCount).toBe(0)
  })

  it('completes a chord in any order and emits the step accompaniment', () => {
    const left = event({ startBeat: 0, hand: 'left', midis: [48] })
    const steps = [
      step({ index: 0, beat: 0, required: [60, 64, 67], accompaniment: [left] }),
      step({ index: 1, beat: 1, required: [72] }),
    ]
    let state = startPractice(steps).state

    const after64 = handleNoteOn(state, 64, 10)
    expect(after64.feedback).toBe('hit')
    const after60 = handleNoteOn(after64.state, 60, 20)
    expect(after60.feedback).toBe('hit')
    const after67 = handleNoteOn(after60.state, 67, 30)

    expect(after67.feedback).toBe('step-complete')
    expect(after67.state.current).toBe(1)
    expect(after67.state.hits).toEqual([])
    expect(after67.autoPlay).toEqual([{ delayBeats: 0, events: [left] }])
  })

  it('emits following automatic steps with relative delays', () => {
    const firstLeft = event({ startBeat: 0, hand: 'left', midis: [48] })
    const secondLeft = event({ startBeat: 1, hand: 'left', midis: [50] })
    const thirdLeft = event({ startBeat: 2, hand: 'left', midis: [52] })
    const steps = [
      step({ index: 0, beat: 0, required: [60], accompaniment: [firstLeft] }),
      step({ index: 1, beat: 1, required: [], accompaniment: [secondLeft] }),
      step({ index: 2, beat: 2, required: [], accompaniment: [thirdLeft] }),
      step({ index: 3, beat: 3, required: [62] }),
    ]
    const state = startPractice(steps).state

    const output = handleNoteOn(state, 60, 10)

    expect(output.feedback).toBe('step-complete')
    expect(output.state.current).toBe(3)
    expect(output.autoPlay).toEqual([
      { delayBeats: 0, events: [firstLeft] },
      { delayBeats: 1, events: [secondLeft] },
      { delayBeats: 2, events: [thirdLeft] },
    ])
  })

  it('finishes on the last required step without looping', () => {
    const ending = event({ startBeat: 1, hand: 'left', midis: [48] })
    const steps = [
      step({ index: 0, beat: 0, required: [60] }),
      step({ index: 1, beat: 1, required: [62], accompaniment: [ending] }),
    ]
    const state = startPractice(steps).state
    const middle = handleNoteOn(state, 60, 10)
    const output = handleNoteOn(middle.state, 62, 80)

    expect(output.feedback).toBe('finished')
    expect(output.state.current).toBe(2)
    expect(output.state.passes).toBe(1)
    expect(output.state.finishedAt).toBe(80)
    expect(output.autoPlay).toEqual([{ delayBeats: 0, events: [ending] }])
  })

  it('loops back to the first required step and delays opening cues by one beat', () => {
    const opening = event({ startBeat: 0, hand: 'left', midis: [48] })
    const middleAccompaniment = event({ startBeat: 1, hand: 'left', midis: [50] })
    const steps = [
      step({ index: 0, beat: 0, required: [], accompaniment: [opening] }),
      step({ index: 1, beat: 1, required: [60], accompaniment: [middleAccompaniment] }),
      step({ index: 2, beat: 2, required: [62] }),
    ]
    const started = startPractice(steps, { loop: true })
    expect(started.state.current).toBe(1)
    expect(started.autoPlay).toEqual([{ delayBeats: 0, events: [opening] }])

    const middle = handleNoteOn(started.state, 60, 10)
    const output = handleNoteOn(middle.state, 62, 20)

    expect(output.feedback).toBe('loop')
    expect(output.state.current).toBe(1)
    expect(output.state.passes).toBe(1)
    expect(output.state.finishedAt).toBeNull()
    expect(output.autoPlay).toEqual([{ delayBeats: 1, events: [opening] }])
  })

  it('does not mutate the state passed in', () => {
    const steps = [step({ index: 0, beat: 0, required: [60, 64] })]
    const state = startPractice(steps).state
    const snapshot = structuredClone(state)

    handleNoteOn(state, 60, 10)
    handleNoteOn(state, 61, 20)

    expect(state).toEqual(snapshot)
  })

  it('ignores notes after practice has finished', () => {
    const state: PracticeState = {
      ...startPractice([step({ index: 0, beat: 0, required: [60] })]).state,
      current: 1,
      finishedAt: 100,
    }

    const output = handleNoteOn(state, 60, 200)

    expect(output.feedback).toBe('none')
    expect(output.state).toBe(state)
    expect(output.autoPlay).toEqual([])
  })
})

describe('summarizePractice', () => {
  const state: PracticeState = {
    steps: [],
    current: 0,
    hits: [],
    loop: false,
    passes: 2,
    wrongCount: 10,
    wrongByMeasure: { 2: 2, 1: 2, 3: 1, 4: 0, 5: 5 },
    startedAt: 1000,
    finishedAt: null,
  }

  it('sorts and truncates the worst measures', () => {
    expect(summarizePractice(state, 3500)).toEqual({
      passes: 2,
      wrongCount: 10,
      elapsedMs: 2500,
      worstMeasures: [
        { measure: 5, count: 5 },
        { measure: 1, count: 2 },
        { measure: 2, count: 2 },
      ],
    })
  })

  it('uses the finish time when available and reports zero before starting', () => {
    expect(
      summarizePractice({ ...state, finishedAt: 2500 }, 9999).elapsedMs,
    ).toBe(1500)
    expect(summarizePractice({ ...state, startedAt: null }, 9999).elapsedMs).toBe(0)
  })
})
