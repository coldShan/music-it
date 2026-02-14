import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

vi.mock('./services/player', () => ({
  playScore: vi.fn().mockResolvedValue(undefined),
  stopScore: vi.fn(),
}))

import App from './App.vue'

describe('App', () => {
  it('renders recognized notes after successful submit', async () => {
    const mockResponse = {
      tempo: 90,
      timeSignature: '4/4',
      notes: [
        { pitch: 'G4', midi: 67, startBeat: 0, durationBeat: 1, sourceMeasure: 1 },
      ],
      meta: { engine: 'audiveris', inputType: 'png', warnings: [] },
    }

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      }),
    )

    const wrapper = mount(App)
    const file = new File(['x'], 'score.png', { type: 'image/png' })
    const fileInput = wrapper.find('input[type="file"]')
    Object.defineProperty(fileInput.element, 'files', {
      value: [file],
      configurable: true,
    })
    await fileInput.trigger('change')

    await wrapper.find('form').trigger('submit.prevent')
    await Promise.resolve()

    expect(wrapper.text()).toContain('G4')
  })
})
