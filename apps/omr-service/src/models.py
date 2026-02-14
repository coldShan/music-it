from pydantic import BaseModel, Field
from typing import Literal


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


class CatalogEntryDetail(CatalogEntrySummary):
    result: RecognizeResponse


class RecognizeApiResponse(RecognizeResponse):
    catalogEntryId: str
    catalogTitle: str
    isReused: bool


class UpdateCatalogTitleRequest(BaseModel):
    title: str
