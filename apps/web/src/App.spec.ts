import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const playerMocks = vi.hoisted(() => ({
  playScore: vi.fn().mockResolvedValue([]),
  stopScore: vi.fn(),
  filterPlaybackEvents: vi.fn((events) => events),
}))

const apiMocks = vi.hoisted(() => ({
  recognizeScore: vi.fn(),
  listCatalogEntries: vi.fn(),
  getCatalogEntry: vi.fn(),
  updateCatalogEntry: vi.fn(),
  deleteCatalogEntry: vi.fn(),
  resetCatalog: vi.fn(),
}))

vi.mock('./services/player', () => playerMocks)
vi.mock('./services/api', () => apiMocks)

import App from './App.vue'

async function flush() {
  await Promise.resolve()
  await Promise.resolve()
}

function getByTestId(testId: string): HTMLElement {
  const element = document.body.querySelector(`[data-testid="${testId}"]`)
  if (!element) {
    throw new Error(`Cannot find element: ${testId}`)
  }
  return element as HTMLElement
}

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    )
    vi.clearAllMocks()
    apiMocks.listCatalogEntries.mockResolvedValue([])
    apiMocks.updateCatalogEntry.mockResolvedValue({})
    apiMocks.deleteCatalogEntry.mockResolvedValue(undefined)
    apiMocks.resetCatalog.mockResolvedValue({ reset: true, removedEntries: 0 })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('recognizes score via dialog and syncs default title from filename', async () => {
    apiMocks.recognizeScore.mockResolvedValue({
      tempo: 90,
      timeSignature: '4/4',
      notes: [
        {
          pitch: 'G4',
          midi: 67,
          startBeat: 0,
          durationBeat: 1,
          gateBeat: 0.92,
          phraseBreakAfter: false,
          articulation: 'normal',
          sourceMeasure: 1,
        },
      ],
      playbackEvents: [
        {
          startBeat: 0,
          durationBeat: 1,
          gateBeat: 0.92,
          pitches: ['G4'],
          midis: [67],
          hand: 'right',
          staff: '1',
          voice: '1',
          sourceMeasure: 1,
        },
      ],
      meta: { engine: 'audiveris', inputType: 'png', warnings: [] },
      catalogEntryId: 'entry-1',
      catalogTitle: 'server-title',
      melodyInstrument: 'piano',
      leftHandInstrument: 'piano',
      isReused: false,
    })

    const wrapper = mount(App, { attachTo: document.body })
    await flush()

    await wrapper.get('[data-testid="open-recognize-dialog"]').trigger('click')
    await flush()

    const file = new File(['score'], 'my-song.png', { type: 'image/png' })
    const input = getByTestId('recognize-file-input') as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    input.dispatchEvent(new Event('change'))
    await flush()

    getByTestId('recognize-submit').click()
    await flush()

    expect(apiMocks.recognizeScore).toHaveBeenCalledWith(file)
    expect(apiMocks.updateCatalogEntry).toHaveBeenCalledWith('entry-1', { title: 'my-song' })
    expect(document.body.textContent).toContain('识别中，请稍候...')
    expect(getByTestId('recognize-dialog')).toBeTruthy()
    expect(wrapper.text()).toContain('G4')
  })

  it('supports inline rename with Enter save and Esc cancel', async () => {
    apiMocks.listCatalogEntries.mockResolvedValue([
      {
        id: 'entry-2',
        title: '目录曲目',
        imagePath: 'storage/catalog/images/entry-2.png',
        inputType: 'png',
        tempo: 88,
        timeSignature: '4/4',
        noteCount: 1,
        createdAt: '2026-02-14T12:00:00+00:00',
        updatedAt: '2026-02-14T12:00:00+00:00',
        imageHash: 'entry-2',
        melodyInstrument: 'piano',
        leftHandInstrument: 'piano',
      },
    ])

    const wrapper = mount(App, { attachTo: document.body })
    await flush()

    await wrapper.get('[data-testid="catalog-menu-entry-2"]').trigger('click')
    await flush()
    await wrapper.get('[data-testid="catalog-rename-entry-2"]').trigger('click')
    await flush()

    const input = wrapper.get('[data-testid="catalog-rename-input-entry-2"]')
    await input.setValue('新的曲目名')
    await input.trigger('keydown.enter')
    await flush()

    expect(apiMocks.updateCatalogEntry).toHaveBeenCalledWith('entry-2', { title: '新的曲目名' })

    await wrapper.get('[data-testid="catalog-menu-entry-2"]').trigger('click')
    await flush()
    await wrapper.get('[data-testid="catalog-rename-entry-2"]').trigger('click')
    await flush()

    const inputForEsc = wrapper.get('[data-testid="catalog-rename-input-entry-2"]')
    await inputForEsc.setValue('不会保存')
    await inputForEsc.trigger('keydown.esc')
    await flush()

    expect(apiMocks.updateCatalogEntry).toHaveBeenCalledTimes(1)
  })

  it('opens confirm dialog before resetting catalog', async () => {
    const wrapper = mount(App, { attachTo: document.body })
    await flush()

    await wrapper.get('[data-testid="catalog-reset"]').trigger('click')
    await flush()
    expect(apiMocks.resetCatalog).not.toHaveBeenCalled()

    getByTestId('confirm-dialog-confirm').click()
    await flush()

    expect(apiMocks.resetCatalog).toHaveBeenCalledWith('WIPE_CATALOG')
  })

  it('changes playback mode and instrument through headless controls', async () => {
    apiMocks.listCatalogEntries.mockResolvedValue([
      {
        id: 'entry-2',
        title: '目录曲目',
        imagePath: 'storage/catalog/images/entry-2.png',
        inputType: 'png',
        tempo: 88,
        timeSignature: '4/4',
        noteCount: 1,
        createdAt: '2026-02-14T12:00:00+00:00',
        updatedAt: '2026-02-14T12:00:00+00:00',
        imageHash: 'entry-2',
        melodyInstrument: 'piano',
        leftHandInstrument: 'piano',
      },
    ])
    apiMocks.getCatalogEntry.mockResolvedValue({
      id: 'entry-2',
      title: '目录曲目',
      imagePath: 'storage/catalog/images/entry-2.png',
      inputType: 'png',
      tempo: 88,
      timeSignature: '4/4',
      noteCount: 1,
      createdAt: '2026-02-14T12:00:00+00:00',
      updatedAt: '2026-02-14T12:00:00+00:00',
      imageHash: 'entry-2',
      melodyInstrument: 'piano',
      leftHandInstrument: 'piano',
      result: {
        tempo: 88,
        timeSignature: '4/4',
        notes: [
          {
            pitch: 'A4',
            midi: 69,
            startBeat: 0,
            durationBeat: 1,
            gateBeat: 0.92,
            phraseBreakAfter: false,
            articulation: 'normal',
            sourceMeasure: 1,
          },
        ],
        playbackEvents: [
          {
            startBeat: 0,
            durationBeat: 1,
            gateBeat: 0.92,
            pitches: ['A4'],
            midis: [69],
            hand: 'right',
            staff: '1',
            voice: '1',
            sourceMeasure: 1,
          },
        ],
        meta: { engine: 'audiveris', inputType: 'png', warnings: [] },
      },
    })

    const wrapper = mount(App, { attachTo: document.body })
    await flush()

    await wrapper.get('[data-testid="catalog-play-entry-2"]').trigger('click')
    await flush()

    getByTestId('playback-mode-left').click()
    await flush()

    await wrapper.get('[data-testid="main-play"]').trigger('click')
    await flush()

    expect(playerMocks.playScore).toHaveBeenLastCalledWith(
      expect.objectContaining({
        mode: 'left',
      }),
    )

    getByTestId('melody-instrument-button').click()
    await flush()
    getByTestId('melody-instrument-option-violin').click()
    await flush()

    expect(apiMocks.updateCatalogEntry).toHaveBeenCalledWith('entry-2', {
      melodyInstrument: 'violin',
      leftHandInstrument: 'piano',
    })
  })
})
