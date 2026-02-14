export type RecognizedNote = {
  pitch: string
  midi: number
  startBeat: number
  durationBeat: number
  gateBeat: number
  phraseBreakAfter: boolean
  articulation: 'normal' | 'slur' | 'staccato' | 'tie'
  sourceMeasure: number
}

export type PlaybackEvent = {
  startBeat: number
  durationBeat: number
  gateBeat: number
  pitches: string[]
  midis: number[]
  hand: 'right' | 'left'
  staff: string
  voice: string
  sourceMeasure: number
}

export type RecognizeResponse = {
  tempo: number
  timeSignature: string
  notes: RecognizedNote[]
  playbackEvents: PlaybackEvent[]
  meta: {
    engine: string
    inputType: string
    warnings: string[]
  }
}

export type CatalogEntrySummary = {
  id: string
  title: string
  imagePath: string
  inputType: string
  tempo: number
  timeSignature: string
  noteCount: number
  createdAt: string
  updatedAt: string
  imageHash: string
}

export type CatalogEntryDetail = CatalogEntrySummary & {
  result: RecognizeResponse
}

export type RecognizeApiResponse = RecognizeResponse & {
  catalogEntryId: string
  catalogTitle: string
  isReused: boolean
}
