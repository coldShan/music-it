from pydantic import BaseModel, Field
from typing import Literal

InstrumentId = Literal["piano", "guitar", "musicBox", "violin", "trumpet", "saxophone", "flute"]
SUPPORTED_INSTRUMENTS = ("piano", "guitar", "musicBox", "violin", "trumpet", "saxophone", "flute")


class RecognizedNote(BaseModel):
    pitch: str
    midi: int
    startBeat: float
    durationBeat: float
    gateBeat: float
    phraseBreakAfter: bool
    articulation: Literal["normal", "slur", "staccato", "tie"]
    sourceMeasure: int


class PlaybackEvent(BaseModel):
    startBeat: float
    durationBeat: float
    gateBeat: float
    pitches: list[str]
    midis: list[int]
    hand: Literal["right", "left"]
    staff: str
    voice: str
    sourceMeasure: int


class ResponseMeta(BaseModel):
    engine: str = "audiveris"
    inputType: str
    warnings: list[str] = Field(default_factory=list)


class RecognizeResponse(BaseModel):
    tempo: int
    timeSignature: str
    notes: list[RecognizedNote]
    playbackEvents: list[PlaybackEvent] = Field(default_factory=list)
    meta: ResponseMeta


class CatalogEntrySummary(BaseModel):
    id: str
    title: str
    imagePath: str
    inputType: str
    tempo: int
    timeSignature: str
    noteCount: int
    createdAt: str
    updatedAt: str
    imageHash: str
    melodyInstrument: InstrumentId
    leftHandInstrument: InstrumentId


class CatalogEntryDetail(CatalogEntrySummary):
    result: RecognizeResponse


class RecognizeApiResponse(RecognizeResponse):
    catalogEntryId: str
    catalogTitle: str
    melodyInstrument: InstrumentId
    leftHandInstrument: InstrumentId
    isReused: bool


class UpdateCatalogEntryRequest(BaseModel):
    title: str | None = None
    melodyInstrument: str | None = None
    leftHandInstrument: str | None = None
