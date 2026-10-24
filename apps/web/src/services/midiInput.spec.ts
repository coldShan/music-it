import { describe, expect, it, vi } from 'vitest'

import {
  connectMidi,
  MidiUnavailableError,
  parseMidiMessage,
  type MidiConnection,
  type MidiNoteMessage,
} from './midiInput'

class FakeMidiInput extends EventTarget {
  readonly id: string
  readonly name: string

  constructor(id: string, name = id) {
    super()
    this.id = id
    this.name = name
  }

  emit(data: number[]): void {
    const event = new Event('midimessage')
    Object.defineProperty(event, 'data', { value: Uint8Array.from(data) })
    this.dispatchEvent(event)
  }
}

class FakeMidiAccess extends EventTarget {
  readonly inputs = new Map<string, FakeMidiInput>()

  addInput(input: FakeMidiInput): void {
    this.inputs.set(input.id, input)
    this.dispatchEvent(new Event('statechange'))
  }

  notifyStateChange(): void {
    this.dispatchEvent(new Event('statechange'))
  }
}

function navigatorFor(access: FakeMidiAccess): Navigator {
  return {
    requestMIDIAccess: vi.fn().mockResolvedValue(access),
  } as unknown as Navigator
}

describe('parseMidiMessage', () => {
  it('parses note on messages and channel numbers', () => {
    expect(parseMidiMessage([0x90, 60, 100])).toEqual({
      type: 'noteon',
      midi: 60,
      velocity: 100,
      channel: 1,
    })
    expect(parseMidiMessage([0x9f, 72, 64])).toEqual({
      type: 'noteon',
      midi: 72,
      velocity: 64,
      channel: 16,
    })
  })

  it('treats a note on with zero velocity as note off', () => {
    expect(parseMidiMessage([0x93, 60, 0])).toEqual({
      type: 'noteoff',
      midi: 60,
      velocity: 0,
      channel: 4,
    })
  })

  it('parses explicit note off messages', () => {
    expect(parseMidiMessage([0x82, 64, 50])).toEqual({
      type: 'noteoff',
      midi: 64,
      velocity: 50,
      channel: 3,
    })
  })

  it('returns null for non-note messages and short messages', () => {
    expect(parseMidiMessage([0xb0, 7, 100])).toBeNull()
    expect(parseMidiMessage([0xe0, 1, 2])).toBeNull()
    expect(parseMidiMessage([0x90, 60])).toBeNull()
    expect(parseMidiMessage([])).toBeNull()
  })
})

describe('connectMidi', () => {
  it('rejects insecure contexts', async () => {
    const error = await connectMidi({
      navigator: navigatorFor(new FakeMidiAccess()),
      isSecureContext: false,
    }).catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(MidiUnavailableError)
    expect((error as MidiUnavailableError).reason).toBe('insecure')
    expect((error as Error).message).toContain('HTTPS')
  })

  it('rejects browsers without Web MIDI support', async () => {
    const error = await connectMidi({
      navigator: {} as Navigator,
      isSecureContext: true,
    }).catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(MidiUnavailableError)
    expect((error as MidiUnavailableError).reason).toBe('unsupported')
    expect((error as Error).message).toContain('Chrome')
  })

  it('rejects when MIDI access is denied', async () => {
    const navigator = {
      requestMIDIAccess: vi.fn().mockRejectedValue(new Error('denied')),
    } as unknown as Navigator
    const error = await connectMidi({ navigator, isSecureContext: true }).catch(
      (caught: unknown) => caught,
    )

    expect(error).toBeInstanceOf(MidiUnavailableError)
    expect((error as MidiUnavailableError).reason).toBe('denied')
    expect((error as Error).message).toContain('权限')
  })

  it('lists inputs and reports input changes', async () => {
    const access = new FakeMidiAccess()
    access.addInput(new FakeMidiInput('a', '键盘 A'))
    const connection = await connectMidi({ navigator: navigatorFor(access), isSecureContext: true })
    const changes: string[][] = []
    connection.onInputsChange((inputs) => changes.push(inputs.map((input) => input.id)))

    expect(connection.inputs()).toEqual([{ id: 'a', name: '键盘 A' }])
    access.addInput(new FakeMidiInput('b', '键盘 B'))

    expect(changes).toEqual([['a', 'b']])
    connection.close()
  })

  it("listens to all current and future inputs with listen('all')", async () => {
    const access = new FakeMidiAccess()
    const first = new FakeMidiInput('a')
    access.addInput(first)
    const connection = await connectMidi({ navigator: navigatorFor(access), isSecureContext: true })
    const messages: MidiNoteMessage[] = []
    connection.listen('all', (message) => messages.push(message))

    first.emit([0x90, 60, 100])
    first.emit([0xb0, 1, 2])
    const second = new FakeMidiInput('b')
    access.addInput(second)
    second.emit([0x80, 60, 0])

    expect(messages).toEqual([
      { type: 'noteon', midi: 60, velocity: 100, channel: 1 },
      { type: 'noteoff', midi: 60, velocity: 0, channel: 1 },
    ])
    connection.close()
  })

  it('stops callbacks after unsubscribe and close', async () => {
    const access = new FakeMidiAccess()
    const input = new FakeMidiInput('a')
    access.addInput(input)
    const connection = await connectMidi({ navigator: navigatorFor(access), isSecureContext: true })
    const callback = vi.fn()
    const unsubscribe = connection.listen('a', callback)

    input.emit([0x90, 60, 100])
    expect(callback).toHaveBeenCalledOnce()

    unsubscribe()
    input.emit([0x90, 62, 100])
    expect(callback).toHaveBeenCalledOnce()

    const secondConnection: MidiConnection = await connectMidi({
      navigator: navigatorFor(access),
      isSecureContext: true,
    })
    secondConnection.listen('all', callback)
    secondConnection.close()
    input.emit([0x90, 64, 100])

    expect(callback).toHaveBeenCalledOnce()
    connection.close()
  })
})
