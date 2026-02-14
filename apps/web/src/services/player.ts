import * as Tone from 'tone'
import type { PlaybackEvent } from '@music-it/shared-types'

export type PlaybackMode = 'both' | 'right' | 'left'
type PlaybackOptions = {
  tempo: number
  playbackEvents: PlaybackEvent[]
  mode?: PlaybackMode
}

let part: Tone.Part | null = null
let synth: Tone.PolySynth | null = null

export function filterPlaybackEvents(
  events: PlaybackEvent[],
  mode: PlaybackMode = 'both',
): PlaybackEvent[] {
  if (mode === 'both') {
    return events
  }
  return events.filter((event) => event.hand === mode)
}

export async function playScore(options: PlaybackOptions): Promise<void> {
  const { tempo, playbackEvents, mode = 'both' } = options
  const targetEvents = filterPlaybackEvents(playbackEvents, mode)

  if (!targetEvents.length) {
    return
  }

  await Tone.start()

  if (!synth) {
    synth = new Tone.PolySynth(Tone.Synth, {
      oscillator: {
        type: 'triangle8',
      },
      envelope: {
        attack: 0.01,
        decay: 0.3,
        sustain: 0.2,
        release: 0.8,
      },
      volume: -8,
    }).toDestination()
  }

  stopScore()

  Tone.getTransport().bpm.value = tempo

  const events = targetEvents.map((event) => ({
    time: (event.startBeat * 60) / tempo,
    notes: event.pitches,
    durationSeconds: (event.gateBeat * 60) / tempo,
  }))

  part = new Tone.Part((time, event) => {
    synth?.triggerAttackRelease(event.notes, event.durationSeconds, time)
  }, events)

  part.start(0)
  Tone.getTransport().start('+0.05')
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
