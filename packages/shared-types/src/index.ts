export type RecognizedNote = {
  pitch: string
  midi: number
  startBeat: number
  durationBeat: number
  sourceMeasure: number
}

export type RecognizeResponse = {
  tempo: number
  timeSignature: string
  notes: RecognizedNote[]
  meta: {
    engine: string
    inputType: string
    warnings: string[]
  }
}
