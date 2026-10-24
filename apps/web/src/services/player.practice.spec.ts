import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => {
  const polySynth = {
    triggerAttackRelease: vi.fn(),
    triggerAttack: vi.fn(),
    triggerRelease: vi.fn(),
    releaseAll: vi.fn(),
    toDestination: vi.fn(),
  }
  polySynth.toDestination.mockReturnValue(polySynth)

  return {
    players: new Map<string, { play: ReturnType<typeof vi.fn>; stop: ReturnType<typeof vi.fn> }>(),
    polySynth,
    instrument: vi.fn(),
    toneStart: vi.fn().mockResolvedValue(undefined),
    toneImmediate: vi.fn(() => 10),
    PolySynth: vi.fn(function () {
      return polySynth
    }),
    Synth: vi.fn(),
  }
})

vi.mock('tone', () => ({
  start: mocks.toneStart,
  immediate: mocks.toneImmediate,
  getContext: () => ({ rawContext: {} }),
  getTransport: () => ({
    bpm: { value: 120 },
    seconds: 0,
    start: vi.fn(),
    stop: vi.fn(),
    cancel: vi.fn(),
  }),
  Part: vi.fn(),
  Synth: mocks.Synth,
  PolySynth: mocks.PolySynth,
}))

vi.mock('soundfont-player', () => ({ instrument: mocks.instrument }))

const rightEvent = {
  startBeat: 0,
  durationBeat: 1,
  gateBeat: 0.5,
  pitches: ['C4'],
  midis: [60],
  hand: 'right' as const,
  staff: '1',
  voice: '1',
  sourceMeasure: 1,
}

const leftEvent = {
  startBeat: 0,
  durationBeat: 2,
  gateBeat: 1,
  pitches: ['C3', 'G3'],
  midis: [48, 55],
  hand: 'left' as const,
  staff: '2',
  voice: '1',
  sourceMeasure: 1,
}

describe('midiToPitch', () => {
  it('converts boundary midi values to scientific pitch names', async () => {
    const { midiToPitch } = await import('./player')

    expect(midiToPitch(21)).toBe('A0')
    expect(midiToPitch(60)).toBe('C4')
    expect(midiToPitch(61)).toBe('C#4')
    expect(midiToPitch(127)).toBe('G9')
  })
})

describe('practice playback helpers', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    mocks.players.clear()
    mocks.polySynth.toDestination.mockReturnValue(mocks.polySynth)
    mocks.toneImmediate.mockReturnValue(10)
    mocks.instrument.mockImplementation((_context: unknown, program: string) => {
      const player = { program, play: vi.fn(), stop: vi.fn() }
      mocks.players.set(program, player)
      return Promise.resolve(player)
    })
  })

  it('starts Tone and preloads the requested instruments', async () => {
    const { preparePracticeInstruments } = await import('./player')

    const warnings = await preparePracticeInstruments(['violin', 'toneSynth'])

    expect(warnings).toEqual([])
    expect(mocks.toneStart).toHaveBeenCalledOnce()
    expect(mocks.players.has('violin')).toBe(true)
    expect(mocks.PolySynth).toHaveBeenCalledOnce()
  })

  it('schedules cues with the right instruments, delay and durations', async () => {
    const { preparePracticeInstruments, playCueNow } = await import('./player')
    await preparePracticeInstruments(['violin', 'guitar'])

    playCueNow(
      { delayBeats: 2, events: [rightEvent, leftEvent] },
      { tempo: 60, melodyInstrument: 'violin', leftHandInstrument: 'guitar' },
    )

    expect(mocks.players.get('violin')?.play).toHaveBeenCalledWith('C4', 12, {
      duration: 0.5,
      gain: 1,
    })
    expect(mocks.players.get('acoustic_guitar_nylon')?.play).toHaveBeenCalledWith('C3', 12, {
      duration: 1,
      gain: 0.9,
    })
    expect(mocks.players.get('acoustic_guitar_nylon')?.play).toHaveBeenCalledWith('G3', 12, {
      duration: 1,
      gain: 0.9,
    })
  })

  it('triggers held synth notes at the immediate audio time', async () => {
    const { preparePracticeInstruments, noteOnNow } = await import('./player')
    await preparePracticeInstruments(['toneSynth'])
    mocks.toneImmediate.mockReturnValue(4.2)

    noteOnNow(60, 'toneSynth', 100)

    expect(mocks.polySynth.triggerAttack).toHaveBeenCalledWith('C4', 4.2, 100 / 127)
  })

  it('uses the built-in synth when the cue selects toneSynth', async () => {
    const { preparePracticeInstruments, playCueNow } = await import('./player')
    await preparePracticeInstruments(['toneSynth'])

    playCueNow(
      { delayBeats: 0, events: [rightEvent] },
      { tempo: 120, melodyInstrument: 'toneSynth', leftHandInstrument: 'piano' },
    )

    expect(mocks.polySynth.triggerAttackRelease).toHaveBeenCalledWith(['C4'], 0.25, 10)
  })

  it('skips cues whose instruments were not preloaded', async () => {
    const { preparePracticeInstruments, playCueNow } = await import('./player')
    await preparePracticeInstruments(['piano'])
    mocks.players.get('acoustic_grand_piano')!.play.mockClear()

    expect(() =>
      playCueNow(
        { delayBeats: 0, events: [rightEvent] },
        { tempo: 120, melodyInstrument: 'flute', leftHandInstrument: 'piano' },
      ),
    ).not.toThrow()
    expect(mocks.players.get('acoustic_grand_piano')!.play).not.toHaveBeenCalled()
  })

  it('holds note-on sounds until note-off and maps velocity to gain', async () => {
    const { preparePracticeInstruments, noteOnNow, noteOffNow } = await import('./player')
    await preparePracticeInstruments(['piano'])
    const player = mocks.players.get('acoustic_grand_piano')!
    const node = { stop: vi.fn() }
    player.play.mockReturnValue(node)

    noteOnNow(60, 'piano', 64)
    expect(player.play).toHaveBeenCalledWith('C4', undefined, { gain: 64 / 127 })

    noteOffNow(60)
    expect(node.stop).toHaveBeenCalledOnce()
  })

  it('stops all practice sounds', async () => {
    const { preparePracticeInstruments, noteOnNow, stopPracticeSounds } = await import('./player')
    await preparePracticeInstruments(['piano', 'toneSynth'])
    const player = mocks.players.get('acoustic_grand_piano')!

    noteOnNow(60, 'piano', 100)
    noteOnNow(62, 'toneSynth', 100)
    stopPracticeSounds()

    expect(player.stop).toHaveBeenCalled()
    expect(mocks.polySynth.releaseAll).toHaveBeenCalled()
  })
})
