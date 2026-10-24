import * as Tone from 'tone'
import * as Soundfont from 'soundfont-player'
import type { InstrumentId, PlaybackEvent } from '@music-it/shared-types'

import type { AutoPlayCue } from './practice'

export type PlaybackMode = 'both' | 'right' | 'left'
type PlaybackOptions = {
  tempo: number
  playbackEvents: PlaybackEvent[]
  mode?: PlaybackMode
  melodyInstrument: InstrumentId
  leftHandInstrument: InstrumentId
}

let playbackRequest = 0
const activePlayers = new Set<Soundfont.Player>()
let part: Tone.Part | null = null
let toneSynth: Tone.PolySynth | null = null
type SoundfontInstrumentId = Exclude<InstrumentId, 'toneSynth'>
const instrumentCache = new Map<SoundfontInstrumentId, Promise<Soundfont.Player>>()
const practicePlayers = new Map<InstrumentId, Soundfont.Player>()
type HeldSound =
  | { kind: 'synth' }
  | { kind: 'sample'; node?: { stop?: (when?: number) => void } | null }
const heldSounds = new Map<number, HeldSound[]>()
const PITCH_CLASSES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

export const SOUND_FONT_PROGRAMS = {
  piano: 'acoustic_grand_piano',
  guitar: 'acoustic_guitar_nylon',
  musicBox: 'music_box',
  violin: 'violin',
  trumpet: 'trumpet',
  saxophone: 'alto_sax',
  flute: 'flute',
  eightBit: 'lead_1_square',
} as const satisfies Record<SoundfontInstrumentId, Parameters<typeof Soundfont.instrument>[1]>

export function isToneSynthInstrument(instrumentId: InstrumentId): instrumentId is 'toneSynth' {
  return instrumentId === 'toneSynth'
}

export function filterPlaybackEvents(
  events: PlaybackEvent[],
  mode: PlaybackMode = 'both',
): PlaybackEvent[] {
  if (mode === 'both') {
    return events
  }
  return events.filter((event) => event.hand === mode)
}

async function loadInstrument(instrumentId: SoundfontInstrumentId): Promise<Soundfont.Player> {
  const cached = instrumentCache.get(instrumentId)
  if (cached) {
    return cached
  }

  const rawContext = Tone.getContext().rawContext as AudioContext
  const loading = Soundfont.instrument(rawContext, SOUND_FONT_PROGRAMS[instrumentId], {
    soundfont: 'MusyngKite',
    format: 'mp3',
  })
  instrumentCache.set(instrumentId, loading)

  try {
    return await loading
  } catch (error) {
    instrumentCache.delete(instrumentId)
    throw error
  }
}

export async function loadInstrumentWithFallback(
  instrumentId: SoundfontInstrumentId,
  loader: (value: SoundfontInstrumentId) => Promise<Soundfont.Player> = loadInstrument,
): Promise<{ player: Soundfont.Player; resolved: InstrumentId; warning?: string }> {
  try {
    const player = await loader(instrumentId)
    return { player, resolved: instrumentId }
  } catch {
    if (instrumentId === 'piano') {
      throw new Error('钢琴音色加载失败，请稍后重试。')
    }
    const fallback = await loader('piano')
    return {
      player: fallback,
      resolved: 'piano',
      warning: `音色 ${instrumentId} 加载失败，已回退为 piano。`,
    }
  }
}

export function resolveHandInstrument(
  hand: PlaybackEvent['hand'],
  melodyInstrument: InstrumentId,
  leftHandInstrument: InstrumentId,
): InstrumentId {
  return hand === 'left' ? leftHandInstrument : melodyInstrument
}

function currentAudioTime(): number {
  const immediate = (Tone as unknown as { immediate?: () => number }).immediate
  return typeof immediate === 'function' ? immediate.call(Tone) : 0
}

function ensureToneSynth(): Tone.PolySynth {
  toneSynth ??= new Tone.PolySynth(Tone.Synth, {
    oscillator: { type: 'triangle8' },
    envelope: { attack: 0.01, decay: 0.3, sustain: 0.2, release: 0.8 },
    volume: -8,
  }).toDestination()
  return toneSynth
}

export function midiToPitch(midi: number): string {
  const pitchClass = PITCH_CLASSES[((midi % 12) + 12) % 12]
  const octave = Math.floor(midi / 12) - 1
  return `${pitchClass}${octave}`
}

export async function preparePracticeInstruments(ids: InstrumentId[]): Promise<string[]> {
  const warnings: string[] = []
  await Tone.start()

  for (const instrumentId of new Set(ids)) {
    if (isToneSynthInstrument(instrumentId)) {
      ensureToneSynth()
      continue
    }

    const loaded = await loadInstrumentWithFallback(instrumentId)
    practicePlayers.set(loaded.resolved, loaded.player)
    if (loaded.resolved !== instrumentId) {
      practicePlayers.set(instrumentId, loaded.player)
    }
    if (loaded.warning) {
      warnings.push(loaded.warning)
    }
  }

  return warnings
}

function addHeldSound(midi: number, sound: HeldSound): void {
  const held = heldSounds.get(midi)
  if (held) {
    held.push(sound)
  } else {
    heldSounds.set(midi, [sound])
  }
}

export function playCueNow(
  cue: AutoPlayCue,
  options: {
    tempo: number
    melodyInstrument: InstrumentId
    leftHandInstrument: InstrumentId
  },
): void {
  const { tempo, melodyInstrument, leftHandInstrument } = options
  const time = currentAudioTime() + (cue.delayBeats * 60) / tempo

  for (const event of cue.events) {
    const selected = resolveHandInstrument(event.hand, melodyInstrument, leftHandInstrument)
    const durationSeconds = (event.gateBeat * 60) / tempo

    if (isToneSynthInstrument(selected)) {
      ensureToneSynth().triggerAttackRelease(event.pitches, durationSeconds, time)
      continue
    }

    const player = practicePlayers.get(selected)
    if (!player) continue

    for (const pitch of event.pitches) {
      player.play(pitch, time, {
        duration: durationSeconds,
        gain: event.hand === 'left' ? 0.9 : 1,
      })
    }
  }
}

export function noteOnNow(midi: number, instrumentId: InstrumentId, velocity: number): void {
  const gain = velocity / 127

  if (isToneSynthInstrument(instrumentId)) {
    ensureToneSynth().triggerAttack(midiToPitch(midi), currentAudioTime(), gain)
    addHeldSound(midi, { kind: 'synth' })
    return
  }

  const player = practicePlayers.get(instrumentId)
  if (!player) return

  const node = player.play(midiToPitch(midi), undefined, { gain }) as unknown as
    | { stop?: (when?: number) => void }
    | undefined
  addHeldSound(midi, { kind: 'sample', node })
}

export function noteOffNow(midi: number): void {
  const held = heldSounds.get(midi)
  if (!held) return

  for (const sound of held) {
    if (sound.kind === 'synth') {
      toneSynth?.triggerRelease(midiToPitch(midi))
    } else {
      sound.node?.stop?.()
    }
  }
  heldSounds.delete(midi)
}

export function stopPracticeSounds(): void {
  for (const player of new Set(practicePlayers.values())) {
    player.stop()
  }
  toneSynth?.releaseAll()
  heldSounds.clear()
}

export async function playScore(options: PlaybackOptions): Promise<string[]> {
  const { tempo, playbackEvents, mode = 'both', melodyInstrument, leftHandInstrument } = options
  const targetEvents = filterPlaybackEvents(playbackEvents, mode)
  const warnings: string[] = []

  if (!targetEvents.length) {
    return warnings
  }

  stopScore()
  const request = playbackRequest
  await Tone.start()
  if (request !== playbackRequest) return warnings

  Tone.getTransport().bpm.value = tempo

  const players = new Map<InstrumentId, Soundfont.Player>()
  const required = new Set<InstrumentId>(
    targetEvents.map((event) => resolveHandInstrument(event.hand, melodyInstrument, leftHandInstrument)),
  )

  for (const instrumentId of required) {
    if (isToneSynthInstrument(instrumentId)) {
      ensureToneSynth()
      continue
    }

    const loaded = await loadInstrumentWithFallback(instrumentId)
    if (request !== playbackRequest) return warnings
    players.set(instrumentId, loaded.player)
    activePlayers.add(loaded.player)
    if (loaded.warning) {
      warnings.push(loaded.warning)
    }
  }

  const events = targetEvents.map((event) => ({
    time: (event.startBeat * 60) / tempo,
    hand: event.hand,
    pitches: event.pitches,
    durationSeconds: (event.gateBeat * 60) / tempo,
  }))

  part = new Tone.Part((time, event) => {
    const selected = resolveHandInstrument(event.hand, melodyInstrument, leftHandInstrument)
    if (isToneSynthInstrument(selected)) {
      toneSynth?.triggerAttackRelease(event.pitches, event.durationSeconds, time)
      return
    }

    const player = players.get(selected) ?? players.get('piano')
    if (!player) {
      return
    }

    for (const pitch of event.pitches) {
      player.play(pitch, time, {
        duration: event.durationSeconds,
        gain: event.hand === 'left' ? 0.9 : 1,
      })
    }
  }, events)

  part.start(0)
  Tone.getTransport().start('+0.05')
  return warnings
}

export function getPlaybackSeconds(): number {
  return Tone.getTransport().seconds
}

export function seekScore(seconds: number): void {
  if (!part || !Number.isFinite(seconds)) return
  for (const player of activePlayers) player.stop()
  toneSynth?.releaseAll()
  Tone.getTransport().seconds = Math.max(0, seconds)
}

export function stopScore(): void {
  playbackRequest += 1
  for (const player of activePlayers) player.stop()
  activePlayers.clear()
  if (part) {
    part.stop()
    part.dispose()
    part = null
  }
  toneSynth?.releaseAll()
  Tone.getTransport().stop()
  Tone.getTransport().cancel(0)
}
