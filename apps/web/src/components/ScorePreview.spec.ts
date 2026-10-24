import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { PlaybackEvent } from '@music-it/shared-types'

import ScorePreview from './ScorePreview.vue'

function event(
  overrides: Partial<PlaybackEvent> & Pick<PlaybackEvent, 'startBeat' | 'midis'>,
): PlaybackEvent {
  return {
    durationBeat: 1,
    gateBeat: 0.9,
    pitches: overrides.midis.map(String),
    hand: 'right',
    staff: '1',
    voice: '1',
    sourceMeasure: 1,
    ...overrides,
  }
}

const events = [
  event({ startBeat: 0, midis: [60] }),
  event({ startBeat: 1, midis: [62] }),
]

describe('ScorePreview practice markers', () => {
  it('does not render practice classes without a practice view', () => {
    const wrapper = mount(ScorePreview, { props: { events, beat: 1, mode: 'both' } })

    expect(wrapper.findAll('.note.target')).toHaveLength(0)
    expect(wrapper.findAll('.note.hit')).toHaveLength(0)
    expect(wrapper.find('.wrong-marker').exists()).toBe(false)
  })

  it('marks target notes of the current practice beat', () => {
    const wrapper = mount(ScorePreview, {
      props: {
        events,
        beat: 1,
        mode: 'both',
        practice: { beat: 0, target: [60], hits: [], wrong: null },
      },
    })

    const notes = wrapper.findAll('.note')
    expect(notes[0].classes()).toContain('target')
    expect(notes[0].classes()).not.toContain('hit')
    expect(notes[1].classes()).not.toContain('target')
  })

  it('marks hit notes with a solid class', () => {
    const wrapper = mount(ScorePreview, {
      props: {
        events,
        beat: 0,
        mode: 'both',
        practice: { beat: 0, target: [60], hits: [60], wrong: null },
      },
    })

    const notes = wrapper.findAll('.note')
    expect(notes[0].classes()).toContain('hit')
    expect(notes[0].classes()).not.toContain('target')
  })

  it('shows and hides the wrong marker', async () => {
    const wrapper = mount(ScorePreview, {
      props: {
        events,
        beat: 0,
        mode: 'both',
        practice: { beat: 0, target: [60], hits: [], wrong: 64 },
      },
    })

    expect(wrapper.find('.wrong-marker').exists()).toBe(true)

    await wrapper.setProps({ practice: { beat: 0, target: [60], hits: [], wrong: null } })
    expect(wrapper.find('.wrong-marker').exists()).toBe(false)

    await wrapper.setProps({ practice: null })
    expect(wrapper.find('.wrong-marker').exists()).toBe(false)
  })

  it('shows the playhead at beat zero only with a practice view', () => {
    const withoutPractice = mount(ScorePreview, { props: { events, beat: 0, mode: 'both' } })
    expect(withoutPractice.find('.playhead').exists()).toBe(false)

    const withPractice = mount(ScorePreview, {
      props: {
        events,
        beat: 0.5,
        mode: 'both',
        practice: { beat: 0, target: [], hits: [], wrong: null },
      },
    })
    expect(withPractice.find('.playhead').exists()).toBe(true)
    expect(withPractice.get('.playhead').attributes('d')).toContain('M50')
  })

  it('follows practice.beat for the playhead and paging window', async () => {
    const withPractice = mount(ScorePreview, {
      props: {
        events,
        beat: 0.5,
        mode: 'both',
        practice: { beat: 1.5, target: [], hits: [], wrong: null },
      },
    })
    const plain = mount(ScorePreview, { props: { events, beat: 1.5, mode: 'both' } })

    expect(withPractice.get('.playhead').attributes('d')).toBe(
      plain.get('.playhead').attributes('d'),
    )

    const long = [event({ startBeat: 0, midis: [60], durationBeat: 20 })]
    const paged = mount(ScorePreview, {
      props: {
        events: long,
        beat: 0,
        mode: 'both',
        practice: { beat: 17, target: [], hits: [], wrong: null },
      },
    })
    expect(paged.get('.preview-caption').text()).toContain('第 17–20 拍')
    expect(paged.get('.playhead').attributes('d')).toContain('M275')
  })
})
