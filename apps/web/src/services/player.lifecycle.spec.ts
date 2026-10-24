import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => {
  const transport = {
    bpm: { value: 120 },
    seconds: 0,
    start: vi.fn(),
    stop: vi.fn(),
    cancel: vi.fn(),
  }
  const parts: Array<{ start: ReturnType<typeof vi.fn>; stop: ReturnType<typeof vi.fn>; dispose: ReturnType<typeof vi.fn> }> = []
  const Part = vi.fn(function () {
    const part = { start: vi.fn(), stop: vi.fn(), dispose: vi.fn() }
    parts.push(part)
    return part
  })

  return {
    transport,
    parts,
    Part,
    instrument: vi.fn(),
    toneStart: vi.fn().mockResolvedValue(undefined),
  }
})

vi.mock('tone', () => ({
  start: mocks.toneStart,
  getTransport: () => mocks.transport,
  getContext: () => ({ rawContext: {} }),
  Part: mocks.Part,
  Synth: vi.fn(),
  PolySynth: vi.fn(),
}))

vi.mock('soundfont-player', () => ({ instrument: mocks.instrument }))

const event = {
  startBeat: 0,
  durationBeat: 1,
  gateBeat: 0.9,
  pitches: ['C4'],
  midis: [60],
  hand: 'right' as const,
  staff: '1',
  voice: '1',
  sourceMeasure: 1,
}

const options = {
  tempo: 96,
  playbackEvents: [event],
  melodyInstrument: 'piano' as const,
  leftHandInstrument: 'piano' as const,
}

describe('player lifecycle', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    mocks.parts.length = 0
    mocks.transport.seconds = 0
  })

  it('stops active SoundFont audio and clears the scheduled transport', async () => {
    const player = { play: vi.fn(), stop: vi.fn() }
    mocks.instrument.mockResolvedValue(player)
    const { playScore, stopScore } = await import('./player')

    await playScore(options)
    const part = mocks.parts[0]
    stopScore()

    expect(player.stop).toHaveBeenCalledOnce()
    expect(part.stop).toHaveBeenCalledOnce()
    expect(part.dispose).toHaveBeenCalledOnce()
    expect(mocks.transport.stop).toHaveBeenCalled()
    expect(mocks.transport.cancel).toHaveBeenCalledWith(0)
  })

  it('does not schedule playback when a stopped instrument load later resolves', async () => {
    let resolveInstrument!: (player: { play: ReturnType<typeof vi.fn>; stop: ReturnType<typeof vi.fn> }) => void
    mocks.instrument.mockReturnValue(new Promise((resolve) => { resolveInstrument = resolve }))
    const { playScore, stopScore } = await import('./player')

    const playback = playScore(options)
    await vi.waitFor(() => expect(mocks.instrument).toHaveBeenCalledOnce())
    stopScore()
    resolveInstrument({ play: vi.fn(), stop: vi.fn() })
    await playback

    expect(mocks.Part).not.toHaveBeenCalled()
    expect(mocks.transport.start).not.toHaveBeenCalled()
  })

  it('seeks in both directions without discarding the score schedule', async () => {
    const player = { play: vi.fn(), stop: vi.fn() }
    mocks.instrument.mockResolvedValue(player)
    const { playScore, seekScore } = await import('./player')
    await playScore(options)
    vi.clearAllMocks()

    seekScore(12)
    expect(mocks.transport.seconds).toBe(12)
    seekScore(2)
    expect(mocks.transport.seconds).toBe(2)
    seekScore(Number.NaN)
    expect(mocks.transport.seconds).toBe(2)
    expect(player.stop).toHaveBeenCalledTimes(2)
    expect(mocks.parts[0].dispose).not.toHaveBeenCalled()
    expect(mocks.transport.cancel).not.toHaveBeenCalled()
  })

  it('reports the current transport position' , async () => {
    mocks.transport.seconds = 12.75
    const { getPlaybackSeconds } = await import('./player')

    expect(getPlaybackSeconds()).toBe(12.75)
  })
})
