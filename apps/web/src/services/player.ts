import * as Tone from 'tone'
import * as Soundfont from 'soundfont-player'
import type { InstrumentId, PlaybackEvent } from '@music-it/shared-types'

export type PlaybackMode = 'both' | 'right' | 'left'
type PlaybackOptions = {
  tempo: number
  playbackEvents: PlaybackEvent[]
  mode?: PlaybackMode
  melodyInstrument: InstrumentId
  leftHandInstrument: InstrumentId
}

let part: Tone.Part | null = null
const instrumentCache = new Map<InstrumentId, Promise<Soundfont.Player>>()

export const SOUND_FONT_PROGRAMS = {
  piano: 'acoustic_grand_piano',
  guitar: 'acoustic_guitar_nylon',
  musicBox: 'music_box',
  violin: 'violin',
  trumpet: 'trumpet',
  saxophone: 'alto_sax',
  flute: 'flute',
} as const satisfies Record<InstrumentId, Parameters<typeof Soundfont.instrument>[1]>

export function filterPlaybackEvents(
  events: PlaybackEvent[],
  mode: PlaybackMode = 'both',
): PlaybackEvent[] {
  if (mode === 'both') {
    return events
  }
  return events.filter((event) => event.hand === mode)
}

async function loadInstrument(instrumentId: InstrumentId): Promise<Soundfont.Player> {
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
  instrumentId: InstrumentId,
  loader: (value: InstrumentId) => Promise<Soundfont.Player> = loadInstrument,
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

export async function playScore(options: PlaybackOptions): Promise<string[]> {
  const { tempo, playbackEvents, mode = 'both', melodyInstrument, leftHandInstrument } = options
  const targetEvents = filterPlaybackEvents(playbackEvents, mode)
  const warnings: string[] = []

  if (!targetEvents.length) {
    return warnings
  }

  await Tone.start()

  stopScore()

  Tone.getTransport().bpm.value = tempo

  const players = new Map<InstrumentId, Soundfont.Player>()
  const required = new Set<InstrumentId>(
    targetEvents.map((event) => resolveHandInstrument(event.hand, melodyInstrument, leftHandInstrument)),
  )

  for (const instrumentId of required) {
    const loaded = await loadInstrumentWithFallback(instrumentId)
    players.set(instrumentId, loaded.player)
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

export function stopScore(): void {
  if (part) {
    part.stop()
    part.dispose()
    part = null
  }
  Tone.getTransport().stop()
  Tone.getTransport().cancel(0)
}
