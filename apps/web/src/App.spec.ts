import { mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const playerMocks = vi.hoisted(() => ({
  playScore: vi.fn().mockResolvedValue([]),
  stopScore: vi.fn(),
  seekScore: vi.fn(),
  getPlaybackSeconds: vi.fn(() => 0),
  filterPlaybackEvents: vi.fn((events, mode = 'both') =>
    mode === 'both' ? events : events.filter((event: { hand: string }) => event.hand === mode),
  ),
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

const summary = (id: string, title: string) => ({
  id, title, imagePath: `storage/catalog/images/${id}.png`, inputType: 'png',
  tempo: 88, timeSignature: '4/4', noteCount: 1,
  createdAt: `2026-02-${id === 'first' ? '14' : '15'}T12:00:00+00:00`,
  updatedAt: '2026-02-15T12:00:00+00:00', imageHash: id,
  melodyInstrument: 'piano', leftHandInstrument: 'piano',
})
const event = (hand = 'right') => ({
  startBeat: 0, durationBeat: 1, gateBeat: 0.92, pitches: ['A4'], midis: [69],
  hand, staff: hand === 'left' ? '2' : '1', voice: '1', sourceMeasure: 1,
})
const detail = (id: string, title: string, events = [event()]) => ({
  ...summary(id, title),
  result: {
    tempo: 88, timeSignature: '4/4',
    notes: events.map((item) => ({
      pitch: item.pitches[0], midi: item.midis[0], startBeat: item.startBeat,
      durationBeat: item.durationBeat, gateBeat: item.gateBeat,
      phraseBreakAfter: false, articulation: 'normal', sourceMeasure: item.sourceMeasure,
    })),
    playbackEvents: events,
    meta: { engine: 'audiveris', inputType: 'png', warnings: [] },
  },
})

async function flush() {
  for (let index = 0; index < 10; index += 1) await Promise.resolve()
  await new Promise((resolve) => setTimeout(resolve, 0))
}
function byTestId(testId: string): HTMLElement {
  const element = document.body.querySelector(`[data-testid="${testId}"]`)
  if (!element) throw new Error(`Cannot find element: ${testId}`)
  return element as HTMLElement
}
function button(wrapper: VueWrapper, text: string) {
  const found = wrapper.findAll('button').find((candidate) => candidate.text().includes(text))
  if (!found) throw new Error(`Cannot find button containing: ${text}`)
  return found
}

describe('App', () => {
  let wrapper: VueWrapper | undefined

  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
    vi.stubGlobal('scrollTo', vi.fn())
    vi.clearAllMocks()
    playerMocks.playScore.mockResolvedValue([])
    playerMocks.getPlaybackSeconds.mockReturnValue(0)
    apiMocks.listCatalogEntries.mockResolvedValue([])
    apiMocks.updateCatalogEntry.mockResolvedValue({})
    apiMocks.deleteCatalogEntry.mockResolvedValue(undefined)
    apiMocks.resetCatalog.mockResolvedValue({ reset: true, removedEntries: 0 })
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('starts with the library only and hides unavailable management controls', async () => {
    wrapper = mount(App, { attachTo: document.body })
    await flush()

    expect(document.querySelector('[aria-label="播放器"]')).toBeNull()
    expect(document.querySelector('[data-testid="settings-toggle"]')).toBeNull()
    expect(document.querySelector('[data-testid="catalog-reset"]')).toBeNull()
  })

  it('clears a populated library only after opening management and confirming', async () => {
    apiMocks.listCatalogEntries.mockResolvedValue([summary('first', '目录曲目')])
    wrapper = mount(App, { attachTo: document.body })
    await flush()

    await wrapper.get('details.library-manage > summary').trigger('click')
    await wrapper.get('[data-testid="catalog-reset"]').trigger('click')
    await flush()
    expect(apiMocks.resetCatalog).not.toHaveBeenCalled()

    byTestId('confirm-dialog-confirm').click()
    await flush()
    expect(apiMocks.resetCatalog).toHaveBeenCalledWith('WIPE_CATALOG')
  })

  it('clears a search with no results', async () => {
    apiMocks.listCatalogEntries.mockResolvedValue([summary('first', '月光')])
    wrapper = mount(App, { attachTo: document.body })
    await flush()

    await wrapper.get('[data-testid="catalog-search"]').setValue('不存在')
    expect(wrapper.text()).toContain('没有找到「不存在」')
    await button(wrapper, '清除搜索').trigger('click')
    expect((wrapper.get('[data-testid="catalog-search"]').element as HTMLInputElement).value).toBe('')
    expect(wrapper.text()).toContain('月光')
  })

  it('renames inline with Enter and cancels with Escape', async () => {
    apiMocks.listCatalogEntries.mockResolvedValue([summary('first', '旧曲名')])
    wrapper = mount(App, { attachTo: document.body })
    await flush()

    await wrapper.get('[data-testid="catalog-menu-first"]').trigger('click')
    await flush()
    await wrapper.get('[data-testid="catalog-rename-first"]').trigger('click')
    const input = wrapper.get('[data-testid="catalog-rename-input-first"]')
    await input.setValue('新曲名')
    await input.trigger('keydown.enter')
    await flush()
    expect(apiMocks.updateCatalogEntry).toHaveBeenCalledWith('first', { title: '新曲名' })

    await wrapper.get('[data-testid="catalog-menu-first"]').trigger('click')
    await flush()
    await wrapper.get('[data-testid="catalog-rename-first"]').trigger('click')
    const cancelInput = wrapper.get('[data-testid="catalog-rename-input-first"]')
    await cancelInput.setValue('不保存')
    await cancelInput.trigger('keydown.esc')
    expect(apiMocks.updateCatalogEntry).toHaveBeenCalledTimes(1)
  })

  it.each([false, true])('imports files in filename order, force=%s', async (force) => {
    apiMocks.recognizeScore.mockResolvedValue({
      ...detail('new', 'server-title').result,
      catalogEntryId: 'new', catalogTitle: 'server-title',
      melodyInstrument: 'piano', leftHandInstrument: 'piano', isReused: false,
    })
    wrapper = mount(App, { attachTo: document.body })
    await flush()
    await wrapper.get('[data-testid="open-recognize-dialog"]').trigger('click')
    await flush()

    const page10 = new File(['10'], 'song-10.png', { type: 'image/png' })
    const page2 = new File(['2'], 'song-2.png', { type: 'image/png' })
    const input = byTestId('recognize-file-input') as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [page10, page2], configurable: true })
    input.dispatchEvent(new Event('change'))
    await flush()
    if (force) (document.querySelector('[data-testid="recognize-dialog"] input[type="checkbox"]') as HTMLInputElement).click()
    await flush()
    byTestId('recognize-submit').click()
    await flush()

    expect(apiMocks.recognizeScore).toHaveBeenCalledWith([page2, page10], force, expect.any(Function))
    if (force) expect(apiMocks.updateCatalogEntry).not.toHaveBeenCalled()
    else expect(apiMocks.updateCatalogEntry).toHaveBeenCalledWith('new', { title: 'song-2' })
    expect(playerMocks.playScore).not.toHaveBeenCalled()
    expect(document.querySelector('[data-testid="recognize-dialog"]')).toBeNull()
  })

  it('shows upload progress, waits for recognition, and resets after failure', async () => {
    let rejectImport!: (error: Error) => void
    apiMocks.recognizeScore.mockImplementation(() => new Promise((_, reject) => { rejectImport = reject }))
    wrapper = mount(App, { attachTo: document.body })
    await flush()
    await wrapper.get('[data-testid="open-recognize-dialog"]').trigger('click')
    await flush()
    const input = byTestId('recognize-file-input') as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [new File(['x'], 'score.png', { type: 'image/png' })] })
    input.dispatchEvent(new Event('change'))
    await flush()
    byTestId('recognize-submit').click()
    await flush()
    const progress = () => document.querySelector('[role="progressbar"]')!
    expect(progress().getAttribute('aria-valuenow')).toBe('0')
    const report = apiMocks.recognizeScore.mock.calls.at(-1)![2]
    report(42)
    await flush()
    expect(progress().getAttribute('aria-valuenow')).toBe('42')
    report(100)
    await flush()
    expect(progress().hasAttribute('aria-valuenow')).toBe(false)
    expect(document.body.textContent).toContain('正在识别谱面')
    rejectImport(new Error('识别失败'))
    await flush()
    expect(document.querySelector('[role="progressbar"]')).toBeNull()
    expect((byTestId('recognize-submit') as HTMLButtonElement).disabled).toBe(false)
    byTestId('recognize-submit').click()
    await flush()
    expect(progress().getAttribute('aria-valuenow')).toBe('0')
    rejectImport(new Error('识别失败'))
    await flush()
  })

  it('keeps the opened score when a later import fails', async () => {
    apiMocks.listCatalogEntries.mockResolvedValue([summary('first', '已打开曲目')])
    apiMocks.getCatalogEntry.mockResolvedValue(detail('first', '已打开曲目'))
    apiMocks.recognizeScore.mockRejectedValue(new Error('谱面无法识别'))
    wrapper = mount(App, { attachTo: document.body })
    await flush()
    await wrapper.get('[data-testid="catalog-select-first"]').trigger('click')
    await flush()
    await wrapper.get('[data-testid="open-recognize-dialog"]').trigger('click')
    await flush()

    const input = byTestId('recognize-file-input') as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [new File(['x'], 'bad.png', { type: 'image/png' })], configurable: true })
    input.dispatchEvent(new Event('change'))
    await flush()
    byTestId('recognize-submit').click()
    await flush()

    expect(document.body.textContent).toContain('谱面无法识别')
    expect(document.body.textContent).toContain('已打开曲目')
    expect(document.querySelector('[aria-label="播放器"]')).not.toBeNull()
  })

  it('opens a title silently, plays only from explicit controls, and reveals sound settings on demand', async () => {
    apiMocks.listCatalogEntries.mockResolvedValue([summary('first', '练习曲')])
    apiMocks.getCatalogEntry.mockResolvedValue(detail('first', '练习曲'))
    wrapper = mount(App, { attachTo: document.body })
    await flush()

    await wrapper.get('[data-testid="catalog-select-first"]').trigger('click')
    await flush()
    expect(playerMocks.playScore).not.toHaveBeenCalled()
    expect(document.querySelector('[data-testid="melody-instrument-button"]')).toBeNull()

    await wrapper.get('[data-testid="settings-toggle"]').trigger('click')
    expect(byTestId('melody-instrument-button').textContent).toContain('钢琴')
    byTestId('melody-instrument-button').click()
    await flush()
    byTestId('melody-instrument-option-toneSynth').click()
    await flush()
    expect(apiMocks.updateCatalogEntry).toHaveBeenCalledWith('first', {
      melodyInstrument: 'toneSynth',
      leftHandInstrument: 'piano',
    })

    await wrapper.get('[data-testid="main-play"]').trigger('click')
    await flush()
    expect(playerMocks.playScore).toHaveBeenCalledTimes(1)
    await wrapper.get('[data-testid="main-stop"]').trigger('click')
    await wrapper.get('[data-testid="main-play"]').trigger('click')
    await flush()
    expect(playerMocks.playScore).toHaveBeenCalledTimes(2)
    expect(playerMocks.stopScore).toHaveBeenCalled()
  })

  it('returns to idle after natural playback and ignores a cancelled preparation result', async () => {
    apiMocks.listCatalogEntries.mockResolvedValue([summary('first', '短曲')])
    apiMocks.getCatalogEntry.mockResolvedValue(detail('first', '短曲'))
    playerMocks.getPlaybackSeconds.mockReturnValue(1)
    wrapper = mount(App, { attachTo: document.body })
    await flush()
    await wrapper.get('[data-testid="catalog-select-first"]').trigger('click')
    await flush()

    await wrapper.get('[data-testid="main-play"]').trigger('click')
    await flush()
    await new Promise((resolve) => setTimeout(resolve, 120))
    await flush()
    expect(document.body.textContent).not.toContain('正在播放')
    expect(wrapper.find('[data-testid="main-play"]').exists()).toBe(true)

    let finishPreparing!: (warnings: string[]) => void
    playerMocks.playScore.mockImplementationOnce(() => new Promise((resolve) => { finishPreparing = resolve }))
    await wrapper.get('[data-testid="main-play"]').trigger('click')
    await flush()
    await button(wrapper, '取消').trigger('click')
    finishPreparing([])
    await flush()

    expect(document.body.textContent).not.toContain('正在播放')
    expect(wrapper.find('[data-testid="main-stop"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="main-play"]').exists()).toBe(true)
  })

  it('enables seeking only during playback and keeps playing after a seek', async () => {
    apiMocks.listCatalogEntries.mockResolvedValue([summary('first', '练习曲')])
    apiMocks.getCatalogEntry.mockResolvedValue(detail('first', '练习曲', [{ ...event(), durationBeat: 88 }]))
    wrapper = mount(App, { attachTo: document.body })
    await flush()
    await wrapper.get('[data-testid="catalog-select-first"]').trigger('click')
    await flush()
    const slider = wrapper.get('input[aria-label="播放进度"]')
    expect((slider.element as HTMLInputElement).disabled).toBe(true)
    await wrapper.get('[data-testid="main-play"]').trigger('click')
    await flush()
    expect((slider.element as HTMLInputElement).disabled).toBe(false)
    await slider.setValue('30')
    expect(playerMocks.seekScore).toHaveBeenLastCalledWith(30)
    expect(wrapper.get('.track-progress').text()).toContain('0:30')
    await slider.setValue('5')
    expect(playerMocks.seekScore).toHaveBeenLastCalledWith(5)
    expect(wrapper.find('[data-testid="main-stop"]').exists()).toBe(true)
    expect(playerMocks.playScore).toHaveBeenCalledTimes(1)
    await wrapper.get('[data-testid="main-stop"]').trigger('click')
    expect((slider.element as HTMLInputElement).disabled).toBe(true)
  })

  it('plays from the explicit library preview action', async () => {
    apiMocks.listCatalogEntries.mockResolvedValue([summary('first', '预览曲')])
    apiMocks.getCatalogEntry.mockResolvedValue(detail('first', '预览曲'))
    wrapper = mount(App, { attachTo: document.body })
    await flush()

    await wrapper.get('[data-testid="catalog-play-first"]').trigger('click')
    await flush()
    expect(playerMocks.playScore).toHaveBeenCalledTimes(1)
  })

  it('cancels deletion without calling the API', async () => {
    apiMocks.listCatalogEntries.mockResolvedValue([summary('first', '保留曲目')])
    wrapper = mount(App, { attachTo: document.body })
    await flush()
    await wrapper.get('[data-testid="catalog-menu-first"]').trigger('click')
    await flush()
    await wrapper.get('[data-testid="catalog-delete-first"]').trigger('click')
    await flush()
    byTestId('confirm-dialog-cancel').click()
    await flush()

    expect(apiMocks.deleteCatalogEntry).not.toHaveBeenCalled()
  })

  it('shows playback errors and reports an empty selected voice', async () => {
    apiMocks.listCatalogEntries.mockResolvedValue([summary('first', '单声部')])
    apiMocks.getCatalogEntry.mockResolvedValue(detail('first', '单声部'))
    playerMocks.playScore.mockRejectedValueOnce(new Error('音色加载失败'))
    wrapper = mount(App, { attachTo: document.body })
    await flush()
    await wrapper.get('[data-testid="catalog-select-first"]').trigger('click')
    await flush()

    await wrapper.get('[data-testid="main-play"]').trigger('click')
    await flush()
    expect(document.body.textContent).toContain('音色加载失败')

    byTestId('playback-mode-left').click()
    await flush()
    await wrapper.get('[data-testid="main-play"]').trigger('click')
    await flush()
    expect(document.body.textContent).toContain('这个声部没有可播放的音符')
    expect(playerMocks.playScore).toHaveBeenCalledTimes(1)
  })

  it('renders only the last score when open requests finish out of order', async () => {
    apiMocks.listCatalogEntries.mockResolvedValue([summary('first', '第一首'), summary('second', '第二首')])
    let resolveFirst!: (value: ReturnType<typeof detail>) => void
    let resolveSecond!: (value: ReturnType<typeof detail>) => void
    apiMocks.getCatalogEntry.mockImplementation((id: string) => new Promise((resolve) => {
      if (id === 'first') resolveFirst = resolve
      else resolveSecond = resolve
    }))
    wrapper = mount(App, { attachTo: document.body })
    await flush()

    await wrapper.get('[data-testid="catalog-select-first"]').trigger('click')
    await wrapper.get('[data-testid="catalog-select-second"]').trigger('click')
    resolveSecond(detail('second', '第二首'))
    await flush()
    resolveFirst(detail('first', '第一首'))
    await flush()

    expect(wrapper.get('.studio-heading h1').text()).toBe('第二首')
  })
})
