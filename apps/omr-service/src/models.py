from pydantic import BaseModel, Field


class RecognizedNote(BaseModel):
    pitch: str
    midi: int
    startBeat: float
    durationBeat: float
    sourceMeasure: int


class ResponseMeta(BaseModel):
    engine: str = "audiveris"
    inputType: str
    warnings: list[str] = Field(default_factory=list)


class RecognizeResponse(BaseModel):
    tempo: int
    timeSignature: str
    notes: list[RecognizedNote]
    meta: ResponseMeta
