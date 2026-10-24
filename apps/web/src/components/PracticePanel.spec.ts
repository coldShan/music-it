import { mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { PlaybackEvent } from '@music-it/shared-types'

import type { MidiInputInfo, MidiNoteMessage } from '../services/midiInput'

const midiMocks = vi.hoisted(() => ({
  connectMidi: vi.fn(),
  MidiUnavailableError: class extends Error {
    constructor(message = 'MIDI 不可用') {
      super(message)
      this.name = 'MidiUnavailableError'
    }
  },
}))

const playerMocks = vi.hoisted(() => ({
  preparePracticeInstruments: vi.fn(),
  playCueNow: vi.fn(),
  noteOnNow: vi.fn(),
  noteOffNow: vi.fn(),
  stopPracticeSounds: vi.fn(),
}))

vi.mock('../services/midiInput', () => midiMocks)
vi.mock('../services/player', () => playerMocks)

import PracticePanel from './PracticePanel.vue'

function event(
  overrides: Partial<PlaybackEvent> & Pick<PlaybackEvent, 'startBeat' | 'midis' | 'hand'>,
): PlaybackEvent {
  return {
    durationBeat: 1,
    gateBeat: 0.9,
    pitches: overrides.midis.map(String),
    staff: overrides.hand === 'right' ? '1' : '2',
    voice: '1',
    sourceMeasure: 1,
    ...overrides,
  }
}

const rightAtZero = event({ startBeat: 0, midis: [60], hand: 'right' })
const leftAtZero = event({ startBeat: 0, midis: [48], hand: 'left' })
const rightAtOne = event({ startBeat: 1, midis: [62], hand: 'right', sourceMeasure: 2 })
const leftAtOne = event({ startBeat: 1, midis: [50], hand: 'left', sourceMeasure: 2 })
const baseEvents = [rightAtZero, leftAtZero, rightAtOne]

function createProps(overrides: Record<string, unknown> = {}) {
  return {
    events: baseEvents,
    tempo: 60,
    mode: 'right' as const,
    measureCount: 2,
    melodyInstrument: 'violin' as const,
    leftHandInstrument: 'guitar' as const,
    ...overrides,
  }
}

function fakeConnection(inputs: MidiInputInfo[] = [{ id: 'kbd', name: '键盘 A' }]) {
  const listeners = new Set<(message: MidiNoteMessage) => void>()
  const changeCallbacks = new Set<(inputs: MidiInputInfo[]) => void>()
  let inputList = [...inputs]
  const unsubscribe = vi.fn(() => {
    listeners.clear()
  })

  return {
    listen: vi.fn((_id: string, callback: (message: MidiNoteMessage) => void) => {
      listeners.add(callback)
      return unsubscribe
    }),
    close: vi.fn(),
    inputs: () => [...inputList],
    onInputsChange: vi.fn((callback: (inputs: MidiInputInfo[]) => void) => {
      changeCallbacks.add(callback)
      return () => {
        changeCallbacks.delete(callback)
      }
    }),
    emitInputs(next: MidiInputInfo[]) {
      inputList = [...next]
      changeCallbacks.forEach((callback) => callback([...next]))
    },
    send(message: Pick<MidiNoteMessage, 'type' | 'midi'> & Partial<MidiNoteMessage>) {
      listeners.forEach((listener) =>
        listener({ velocity: 100, channel: 1, ...message }),
      )
    },
    unsubscribe,
  }
}

async function flush() {
  for (let index = 0; index < 12; index += 1) await Promise.resolve()
}

let wrapper: VueWrapper | undefined

async function mountConnected(
  inputs?: MidiInputInfo[],
  overrides: Record<string, unknown> = {},
) {
  const connection = fakeConnection(inputs)
  midiMocks.connectMidi.mockResolvedValueOnce(connection)
  wrapper = mount(PracticePanel, { props: createProps(overrides) })
  await wrapper.get('[data-testid="practice-connect"]').trigger('click')
  await flush()
  return connection
}

async function startPractice() {
  await wrapper!.get('[data-testid="practice-start"]').trigger('click')
  await flush()
}

function lastView() {
  const events = wrapper!.emitted('view') ?? []
  return events[events.length - 1]?.[0]
}

describe('PracticePanel', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    playerMocks.preparePracticeInstruments.mockResolvedValue([])
    midiMocks.connectMidi.mockReset()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    vi.useRealTimers()
  })

  it('shows the MIDI error message when connecting fails', async () => {
    midiMocks.connectMidi.mockRejectedValue(
      new midiMocks.MidiUnavailableError('浏览器拒绝了 MIDI 权限。'),
    )
    wrapper = mount(PracticePanel, { props: createProps() })

    await wrapper.get('[data-testid="practice-connect"]').trigger('click')
    await flush()

    expect(wrapper.get('[role="alert"]').text()).toBe('浏览器拒绝了 MIDI 权限。')
  })

  it('uses a generic message for unexpected connection errors', async () => {
    midiMocks.connectMidi.mockRejectedValue(new Error('boom'))
    wrapper = mount(PracticePanel, { props: createProps() })

    await wrapper.get('[data-testid="practice-connect"]').trigger('click')
    await flush()

    expect(wrapper.get('[role="alert"]').text()).toContain('连接 MIDI 设备失败，请重试。')
  })

  it('lists devices, falls back to all devices, and updates on input changes', async () => {
    const connection = await mountConnected([
      { id: 'a', name: '键盘 A' },
      { id: 'b', name: '' },
    ])

    const select = wrapper!.get('[data-testid="practice-device"]')
    expect(select.findAll('option').map((option) => option.text())).toEqual([
      '所有设备',
      '键盘 A',
      '未命名设备',
    ])
    expect((select.element as HTMLSelectElement).value).toBe('all')

    await select.setValue('b')
    expect((select.element as HTMLSelectElement).value).toBe('b')

    connection.emitInputs([{ id: 'a', name: '键盘 A' }])
    await flush()
    expect((select.element as HTMLSelectElement).value).toBe('all')
    expect(select.findAll('option').map((option) => option.text())).toEqual([
      '所有设备',
      '键盘 A',
    ])
  })

  it('explains when no MIDI device is available', async () => {
    await mountConnected([])

    expect(wrapper!.text()).toContain('没有检测到 MIDI 设备，插上电子琴后会自动出现。')
  })

  it('starts practice on the selected device and reports the first step', async () => {
    const connection = await mountConnected([{ id: 'kbd', name: '键盘 A' }])
    await wrapper!.get('[data-testid="practice-device"]').setValue('kbd')
    playerMocks.preparePracticeInstruments.mockResolvedValueOnce(['音色加载失败，已回退。'])

    await startPractice()

    expect(wrapper!.emitted('start')).toHaveLength(1)
    expect(playerMocks.preparePracticeInstruments).toHaveBeenCalledWith(['violin', 'guitar'])
    expect(connection.listen).toHaveBeenCalledWith('kbd', expect.any(Function))
    expect(wrapper!.get('[data-testid="practice-progress"]').text()).toContain(
      '第 1 / 2 步 · 第 1 小节 · 错音 0 次',
    )
    expect(wrapper!.text()).toContain('音色加载失败，已回退。')
    expect(lastView()).toEqual({ beat: 0, target: [60], hits: [], wrong: null })
  })

  it('advances on correct notes and clears the wrong marker after 400ms', async () => {
    const connection = await mountConnected()
    await startPractice()

    connection.send({ type: 'noteon', midi: 60 })
    await flush()
    expect(wrapper!.get('[data-testid="practice-progress"]').text()).toContain('第 2 / 2 步')
    expect(lastView()).toEqual({ beat: 1, target: [62], hits: [], wrong: null })

    connection.send({ type: 'noteon', midi: 61 })
    await flush()
    expect(wrapper!.get('[data-testid="practice-progress"]').text()).toContain('错音 1 次')
    expect(lastView()).toMatchObject({ beat: 1, target: [62], wrong: 61 })

    vi.advanceTimersByTime(400)
    await flush()
    expect(lastView()).toMatchObject({ beat: 1, wrong: null })
  })

  it('plays the other hand as accompaniment with the configured instruments', async () => {
    const connection = await mountConnected()
    await startPractice()

    connection.send({ type: 'noteon', midi: 60 })
    await flush()

    expect(playerMocks.playCueNow).toHaveBeenCalledWith(
      { delayBeats: 0, events: [leftAtZero] },
      { tempo: 60, melodyInstrument: 'violin', leftHandInstrument: 'guitar' },
    )
  })

  it('only echoes key presses when the echo setting is enabled', async () => {
    const connection = await mountConnected()
    await startPractice()
    connection.send({ type: 'noteon', midi: 60 })
    expect(playerMocks.noteOnNow).not.toHaveBeenCalled()

    await wrapper!.get('[data-testid="practice-echo"]').setValue(true)
    connection.send({ type: 'noteon', midi: 60, velocity: 90 })
    expect(playerMocks.noteOnNow).toHaveBeenCalledWith(60, 'violin', 90)
    connection.send({ type: 'noteoff', midi: 60 })
    expect(playerMocks.noteOffNow).toHaveBeenCalledWith(60)
  })

  it('uses the left-hand instrument for echo in left-hand mode', async () => {
    const connection = await mountConnected(undefined, {
      mode: 'left',
      events: [leftAtZero, leftAtOne],
    })
    await wrapper!.get('[data-testid="practice-echo"]').setValue(true)
    await startPractice()

    connection.send({ type: 'noteon', midi: 48, velocity: 77 })
    expect(playerMocks.noteOnNow).toHaveBeenCalledWith(48, 'guitar', 77)

    connection.send({ type: 'noteoff', midi: 48 })
    expect(playerMocks.noteOffNow).toHaveBeenCalledWith(48)
  })

  it('shows the summary without cutting sounds and keeps listening for note offs', async () => {
    const connection = await mountConnected(undefined, {
      events: [rightAtZero, rightAtOne, leftAtOne],
    })
    await wrapper!.get('[data-testid="practice-echo"]').setValue(true)
    await startPractice()

    connection.send({ type: 'noteon', midi: 60 })
    connection.send({ type: 'noteon', midi: 62 })
    await flush()

    const summary = wrapper!.get('[data-testid="practice-summary"]')
    expect(summary.text()).toContain('用时 0:00')
    expect(summary.text()).toContain('错音 0 次')
    expect(summary.text()).toContain('完成 1 遍')
    expect(summary.text()).toContain('没有错音')
    expect(playerMocks.stopPracticeSounds).not.toHaveBeenCalled()
    expect(connection.unsubscribe).not.toHaveBeenCalled()
    expect(wrapper!.find('[data-testid="practice-progress"]').exists()).toBe(false)
    expect(lastView()).toBeNull()
    expect(playerMocks.playCueNow).toHaveBeenLastCalledWith(
      { delayBeats: 0, events: [leftAtOne] },
      { tempo: 60, melodyInstrument: 'violin', leftHandInstrument: 'guitar' },
    )

    playerMocks.noteOnNow.mockClear()
    connection.send({ type: 'noteon', midi: 64 })
    expect(playerMocks.noteOnNow).not.toHaveBeenCalled()

    connection.send({ type: 'noteoff', midi: 62 })
    expect(playerMocks.noteOffNow).toHaveBeenCalledWith(62)

    ;(wrapper!.vm as unknown as { stop: () => void }).stop()
    expect(connection.unsubscribe).toHaveBeenCalled()
  })

  it('ignores a preparation result after stop() during loading', async () => {
    const connection = await mountConnected()
    let resolvePrepare!: (warnings: string[]) => void
    playerMocks.preparePracticeInstruments.mockImplementationOnce(
      () => new Promise((resolve) => { resolvePrepare = resolve }),
    )

    await wrapper!.get('[data-testid="practice-start"]').trigger('click')
    expect(
      (wrapper!.get('[data-testid="practice-start"]').element as HTMLButtonElement).disabled,
    ).toBe(true)

    ;(wrapper!.vm as unknown as { stop: () => void }).stop()
    await flush()
    expect(
      (wrapper!.get('[data-testid="practice-start"]').element as HTMLButtonElement).disabled,
    ).toBe(false)

    resolvePrepare([])
    await flush()

    expect(playerMocks.playCueNow).not.toHaveBeenCalled()
    expect(connection.listen).not.toHaveBeenCalled()
    expect((wrapper!.emitted('view') ?? []).every(([value]) => value === null)).toBe(true)
    expect(
      (wrapper!.get('[data-testid="practice-start"]').element as HTMLButtonElement).disabled,
    ).toBe(false)
  })

  it('ignores a preparation result after settings change during loading', async () => {
    const connection = await mountConnected()
    let resolvePrepare!: (warnings: string[]) => void
    playerMocks.preparePracticeInstruments.mockImplementationOnce(
      () => new Promise((resolve) => { resolvePrepare = resolve }),
    )

    await wrapper!.get('[data-testid="practice-start"]').trigger('click')
    await wrapper!.setProps({ mode: 'left' })

    resolvePrepare([])
    await flush()

    expect(connection.listen).not.toHaveBeenCalled()
    expect((wrapper!.emitted('view') ?? []).every(([value]) => value === null)).toBe(true)
    expect(
      (wrapper!.get('[data-testid="practice-start"]').element as HTMLButtonElement).disabled,
    ).toBe(false)
  })

  it('stops manually, keeps the summary, and clears the practice view', async () => {
    const connection = await mountConnected()
    await startPractice()
    connection.send({ type: 'noteon', midi: 60 })

    await wrapper!.get('[data-testid="practice-stop"]').trigger('click')
    await flush()

    expect(connection.unsubscribe).toHaveBeenCalled()
    expect(playerMocks.stopPracticeSounds).toHaveBeenCalled()
    expect(wrapper!.find('[data-testid="practice-summary"]').exists()).toBe(true)
    expect(lastView()).toBeNull()
  })

  it('keeps looping and reports the pass number', async () => {
    const connection = await mountConnected(undefined, {
      events: [rightAtZero, rightAtOne],
    })
    await wrapper!.get('[data-testid="practice-loop"]').setValue(true)
    await startPractice()

    connection.send({ type: 'noteon', midi: 60 })
    connection.send({ type: 'noteon', midi: 62 })
    await flush()

    expect(wrapper!.find('[data-testid="practice-summary"]').exists()).toBe(false)
    expect(connection.unsubscribe).not.toHaveBeenCalled()
    expect(wrapper!.get('[data-testid="practice-progress"]').text()).toContain(
      '第 1 / 2 步 · 第 1 小节 · 错音 0 次 · 第 2 遍',
    )
    expect(lastView()).toMatchObject({ beat: 0, target: [60], wrong: null })
  })

  it('disables starting when the start measure is after the end measure', async () => {
    await mountConnected()
    await wrapper!.get('[data-testid="practice-range-start"]').setValue('2')
    await wrapper!.get('[data-testid="practice-range-end"]').setValue('1')
    await flush()

    expect(wrapper!.text()).toContain('起始小节不能大于结束小节')
    expect(
      (wrapper!.get('[data-testid="practice-start"]').element as HTMLButtonElement).disabled,
    ).toBe(true)
  })

  it('stops the practice and its sounds when the mode changes', async () => {
    const connection = await mountConnected()
    await startPractice()

    await wrapper!.setProps({ mode: 'left' })
    await flush()

    expect(connection.unsubscribe).toHaveBeenCalled()
    expect(playerMocks.stopPracticeSounds).toHaveBeenCalled()
    expect(wrapper!.find('[data-testid="practice-progress"]').exists()).toBe(false)
    expect(wrapper!.find('[data-testid="practice-summary"]').exists()).toBe(false)
  })

  it('closes the connection when unmounted', async () => {
    const connection = await mountConnected()

    wrapper!.unmount()
    wrapper = undefined

    expect(connection.close).toHaveBeenCalled()
    expect(playerMocks.stopPracticeSounds).toHaveBeenCalled()
  })
})
