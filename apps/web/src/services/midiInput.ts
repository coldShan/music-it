export type MidiNoteMessage = {
  type: 'noteon' | 'noteoff'
  midi: number
  velocity: number
  channel: number
}

export type MidiInputInfo = { id: string; name: string }

export class MidiUnavailableError extends Error {
  readonly reason: 'unsupported' | 'insecure' | 'denied'

  constructor(reason: MidiUnavailableError['reason'], message?: string) {
    super(message ?? defaultMessage(reason))
    this.name = 'MidiUnavailableError'
    this.reason = reason
  }
}

export type MidiConnection = {
  inputs(): MidiInputInfo[]
  onInputsChange(callback: (inputs: MidiInputInfo[]) => void): () => void
  listen(inputId: string | 'all', callback: (message: MidiNoteMessage) => void): () => void
  close(): void
}

type MidiMessageEventLike = Event & { data?: ArrayLike<number> | null }
type MidiInputLike = EventTarget & { id: string; name?: string | null }
type MidiAccessLike = EventTarget & { inputs: Map<string, MidiInputLike> }
type MidiNavigatorLike = Navigator & { requestMIDIAccess?: () => Promise<MidiAccessLike> }

const NOTE_ON = 0x90
const NOTE_OFF = 0x80

function defaultMessage(reason: MidiUnavailableError['reason']): string {
  switch (reason) {
    case 'insecure':
      return 'MIDI 需要安全上下文：请通过 localhost 或 HTTPS 地址访问本页面后再连接电子琴。'
    case 'unsupported':
      return '当前浏览器不支持 Web MIDI，请改用 Chrome 或 Edge 浏览器后再连接电子琴。'
    case 'denied':
      return '浏览器拒绝了 MIDI 访问权限，请在地址栏的网站设置中允许 MIDI 后重试。'
  }
}

export function parseMidiMessage(data: ArrayLike<number>): MidiNoteMessage | null {
  if (data.length < 3) {
    return null
  }

  const status = data[0] & 0xf0
  const channel = (data[0] & 0x0f) + 1
  const midi = data[1]
  const velocity = data[2]

  if (status === NOTE_ON) {
    return {
      type: velocity > 0 ? 'noteon' : 'noteoff',
      midi,
      velocity,
      channel,
    }
  }

  if (status === NOTE_OFF) {
    return { type: 'noteoff', midi, velocity, channel }
  }

  return null
}

function toInputInfo(input: MidiInputLike): MidiInputInfo {
  return { id: input.id, name: input.name ?? '' }
}

function listInputs(access: MidiAccessLike): MidiInputInfo[] {
  return Array.from(access.inputs.values()).map(toInputInfo)
}

class MidiConnectionImpl implements MidiConnection {
  private readonly access: MidiAccessLike
  private readonly cleanups = new Set<() => void>()
  private closed = false

  constructor(access: MidiAccessLike) {
    this.access = access
  }

  inputs(): MidiInputInfo[] {
    return listInputs(this.access)
  }

  onInputsChange(callback: (inputs: MidiInputInfo[]) => void): () => void {
    if (this.closed) {
      return () => undefined
    }

    const handleStateChange = () => {
      if (!this.closed) {
        callback(listInputs(this.access))
      }
    }

    this.access.addEventListener('statechange', handleStateChange)
    const remove = () => {
      this.access.removeEventListener('statechange', handleStateChange)
      this.cleanups.delete(remove)
    }
    this.cleanups.add(remove)
    return remove
  }

  listen(inputId: string | 'all', callback: (message: MidiNoteMessage) => void): () => void {
    if (this.closed) {
      return () => undefined
    }

    const attached = new Set<MidiInputLike>()

    const handleMidi = (event: Event) => {
      if (this.closed) return
      const data = (event as MidiMessageEventLike).data
      if (!data) return
      const message = parseMidiMessage(data)
      if (message) {
        callback(message)
      }
    }

    const attach = (input: MidiInputLike) => {
      if (attached.has(input)) return
      attached.add(input)
      input.addEventListener('midimessage', handleMidi)
    }

    const attachInputs = () => {
      for (const input of this.access.inputs.values()) {
        if (inputId === 'all' || input.id === inputId) {
          attach(input)
        }
      }
    }

    attachInputs()
    this.access.addEventListener('statechange', attachInputs)

    const remove = () => {
      this.access.removeEventListener('statechange', attachInputs)
      for (const input of attached) {
        input.removeEventListener('midimessage', handleMidi)
      }
      attached.clear()
      this.cleanups.delete(remove)
    }
    this.cleanups.add(remove)
    return remove
  }

  close(): void {
    if (this.closed) return
    this.closed = true
    for (const cleanup of Array.from(this.cleanups)) {
      cleanup()
    }
    this.cleanups.clear()
  }
}

export async function connectMidi(
  env: { navigator?: Navigator; isSecureContext?: boolean } = {},
): Promise<MidiConnection> {
  const navigatorLike = (env.navigator ?? (globalThis as { navigator?: Navigator }).navigator) as
    | MidiNavigatorLike
    | undefined
  const isSecureContext =
    env.isSecureContext ?? (globalThis as { isSecureContext?: boolean }).isSecureContext

  if (isSecureContext === false) {
    throw new MidiUnavailableError('insecure')
  }

  const requestMidiAccess = navigatorLike?.requestMIDIAccess
  if (typeof requestMidiAccess !== 'function') {
    throw new MidiUnavailableError('unsupported')
  }

  let access: MidiAccessLike
  try {
    access = await requestMidiAccess.call(navigatorLike)
  } catch {
    throw new MidiUnavailableError('denied')
  }

  return new MidiConnectionImpl(access)
}
