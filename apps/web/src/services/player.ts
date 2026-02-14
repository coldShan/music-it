import * as Tone from 'tone'
import type { RecognizedNote } from '@music-it/shared-types'

type PlaybackOptions = {
  tempo: number
  notes: RecognizedNote[]
}

let part: Tone.Part | null = null
let synth: Tone.PolySynth | null = null

export async function playScore(options: PlaybackOptions): Promise<void> {
  const { tempo, notes } = options

  if (!notes.length) {
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

  const events = notes.map((note) => ({
    time: (note.startBeat * 60) / tempo,
    note: note.pitch,
    durationSeconds: (note.durationBeat * 60) / tempo,
  }))

  part = new Tone.Part((time, event) => {
    synth?.triggerAttackRelease(event.note, event.durationSeconds, time)
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
