import { describe, expect, it } from 'vitest'
import type { InstrumentId } from '@music-it/shared-types'

import { filterPlaybackEvents, loadInstrumentWithFallback, resolveHandInstrument } from './player'

const sampleEvents = [
  {
    startBeat: 0,
    durationBeat: 1,
    gateBeat: 0.9,
    pitches: ['C4'],
    midis: [60],
    hand: 'right' as const,
    staff: '1',
    voice: '1',
    sourceMeasure: 1,
  },
  {
    startBeat: 0,
    durationBeat: 1,
    gateBeat: 0.9,
    pitches: ['C3', 'G3'],
    midis: [48, 55],
    hand: 'left' as const,
    staff: '2',
    voice: '1',
    sourceMeasure: 1,
  },
]

describe('filterPlaybackEvents', () => {
  it('keeps both hands by default', () => {
    expect(filterPlaybackEvents(sampleEvents).length).toBe(2)
  })

  it('keeps right hand only', () => {
    const filtered = filterPlaybackEvents(sampleEvents, 'right')
    expect(filtered).toHaveLength(1)
    expect(filtered[0].hand).toBe('right')
  })

  it('keeps left hand only', () => {
    const filtered = filterPlaybackEvents(sampleEvents, 'left')
    expect(filtered).toHaveLength(1)
    expect(filtered[0].hand).toBe('left')
  })
})

describe('resolveHandInstrument', () => {
  it('routes right hand to melody instrument', () => {
    expect(resolveHandInstrument('right', 'violin', 'guitar')).toBe('violin')
  })

  it('routes left hand to left-hand instrument', () => {
    expect(resolveHandInstrument('left', 'violin', 'guitar')).toBe('guitar')
  })
})

describe('loadInstrumentWithFallback', () => {
  it('falls back to piano when non-piano load fails', async () => {
    const fakePlayer = {
      play: () => null,
    } as any
    const loader = async (value: InstrumentId) => {
      if (value === 'guitar') {
        throw new Error('load failed')
      }
      return fakePlayer
    }

    const loaded = await loadInstrumentWithFallback('guitar', loader)
    expect(loaded.resolved).toBe('piano')
    expect(loaded.warning).toContain('guitar')
  })
})
