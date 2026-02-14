import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const playerMocks = vi.hoisted(() => ({
  playScore: vi.fn().mockResolvedValue(undefined),
  stopScore: vi.fn(),
}))

const apiMocks = vi.hoisted(() => ({
  recognizeScore: vi.fn(),
  listCatalogEntries: vi.fn(),
  getCatalogEntry: vi.fn(),
  renameCatalogEntry: vi.fn(),
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

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.listCatalogEntries.mockResolvedValue([])
    apiMocks.renameCatalogEntry.mockResolvedValue({})
    apiMocks.deleteCatalogEntry.mockResolvedValue(undefined)
    apiMocks.resetCatalog.mockResolvedValue({ reset: true, removedEntries: 0 })
  })

  it('renders recognized notes and renames catalog entry after submit', async () => {
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
      catalogTitle: 'score',
      isReused: false,
    })

    vi.spyOn(window, 'prompt').mockReturnValue('我的遇见')

    const wrapper = mount(App)
    await flush()

    const file = new File(['x'], 'score.png', { type: 'image/png' })
    const fileInput = wrapper.find('input[type="file"]')
    Object.defineProperty(fileInput.element, 'files', {
      value: [file],
      configurable: true,
    })
    await fileInput.trigger('change')

    await wrapper.find('form').trigger('submit.prevent')
    await flush()

    expect(wrapper.text()).toContain('G4')
    expect(apiMocks.renameCatalogEntry).toHaveBeenCalledWith('entry-1', '我的遇见')
    const playButton = wrapper.findAll('button').find((button) => button.text() === '播放')
    if (!playButton) {
      throw new Error('play button not found')
    }
    await playButton.trigger('click')
    await flush()
    expect(playerMocks.playScore).toHaveBeenLastCalledWith(
      expect.objectContaining({
        mode: 'both',
      }),
    )
  })

  it('plays selected catalog entry', async () => {
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

    const wrapper = mount(App)
    await flush()

    expect(wrapper.text()).toContain('目录曲目')

    await wrapper.get('[data-testid="catalog-play-entry-2"]').trigger('click')
    await flush()

    expect(apiMocks.getCatalogEntry).toHaveBeenCalledWith('entry-2')
    expect(wrapper.text()).toContain('A4')

    await wrapper.get('#playback-mode').setValue('left')
    const playButton = wrapper.findAll('button').find((button) => button.text() === '播放')
    if (!playButton) {
      throw new Error('play button not found')
    }
    await playButton.trigger('click')
    await flush()
    expect(playerMocks.playScore).toHaveBeenLastCalledWith(
      expect.objectContaining({
        mode: 'left',
      }),
    )
  })

  it('resets catalog and clears current result', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
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
    apiMocks.resetCatalog.mockResolvedValue({ reset: true, removedEntries: 1 })
    apiMocks.listCatalogEntries
      .mockResolvedValueOnce([
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
        },
      ])
      .mockResolvedValueOnce([])

    const wrapper = mount(App)
    await flush()
    await wrapper.get('[data-testid="catalog-play-entry-2"]').trigger('click')
    await flush()
    expect(wrapper.text()).toContain('A4')

    await wrapper.get('[data-testid="catalog-reset"]').trigger('click')
    await flush()

    expect(apiMocks.resetCatalog).toHaveBeenCalledWith('WIPE_CATALOG')
    expect(wrapper.text()).not.toContain('A4')
  })
})
