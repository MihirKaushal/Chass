"""Validated model-service contract. No ML runtime is imported by the game API."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PieceLabel = Literal[
    "white-king",
    "white-queen",
    "white-rook",
    "white-bishop",
    "white-knight",
    "white-pawn",
    "black-king",
    "black-queen",
    "black-rook",
    "black-bishop",
    "black-knight",
    "black-pawn",
]
Score = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Finite = Annotated[float, Field(allow_inf_nan=False)]
Text = Annotated[str, Field(max_length=2000)]
Count = Annotated[int, Field(ge=0)]
Milliseconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Rank = Annotated[list[PieceLabel | None], Field(min_length=8, max_length=8)]


class ContractModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class Alternative(ContractModel):
    label: PieceLabel
    score: Score


class Candidate(ContractModel):
    piece_class: PieceLabel = Field(alias="class")
    score: Score | None = None
    classifierScore: Score | None = None
    reasons: list[Text] = Field(default_factory=list, max_length=32)
    alternatives: list[Alternative] = Field(default_factory=list, max_length=12)


class Square(ContractModel):
    row: int = Field(ge=0, lt=8)
    col: int = Field(ge=0, lt=8)
    label: str | None = Field(default=None, pattern=r"^[a-h][1-8]$")

    @model_validator(mode="after")
    def consistent_label(self):
        if self.label is not None and self.label != f"{'abcdefgh'[self.col]}{8 - self.row}":
            raise ValueError("Square label does not match its coordinates")
        return self


class ReviewSquare(Square):
    reasons: list[Text] = Field(default_factory=list, max_length=32)


class CandidateSquare(Square):
    candidates: list[Candidate] = Field(max_length=100)


class Prediction(ContractModel):
    boxes: list[Annotated[list[Finite], Field(min_length=4, max_length=4)]] = Field(max_length=1000)
    labels: list[Annotated[int, Field(ge=1, le=12)]] = Field(max_length=1000)
    scores: list[Score] = Field(max_length=1000)
    detector_labels: list[Annotated[int, Field(ge=1, le=12)]] | None = None
    classifier_scores: list[Score] | None = None
    duplicate_counts: list[Count] | None = Field(default=None, max_length=1000)
    alternatives: list[Annotated[list[Alternative], Field(max_length=12)]] | None = None

    @model_validator(mode="after")
    def aligned_predictions(self):
        for name in (
            "labels",
            "scores",
            "detector_labels",
            "classifier_scores",
            "duplicate_counts",
            "alternatives",
        ):
            values = getattr(self, name)
            if values is not None and len(values) != len(self.boxes):
                raise ValueError("Prediction arrays must have matching lengths")
        if any(right <= left or bottom <= top for left, top, right, bottom in self.boxes):
            raise ValueError("Detection boxes must have positive area")
        return self


class Thresholds(ContractModel):
    classification: Score
    detection: Score


class ModelDigests(ContractModel):
    detector: Digest
    classifier: Digest


class Timings(ContractModel):
    prepareMs: Milliseconds = 0
    detectorMs: Milliseconds = 0
    postprocessMs: Milliseconds = 0
    cropMs: Milliseconds = 0
    classifierMs: Milliseconds = 0
    squareMappingMs: Milliseconds = 0
    proposals: Count = 0


class ScanResponse(ContractModel):
    board: list[Rank] = Field(min_length=8, max_length=8)
    reviewSquares: list[ReviewSquare] = Field(max_length=64)
    squareCandidates: list[CandidateSquare] = Field(default_factory=list, max_length=64)
    warnings: list[Text] = Field(default_factory=list, max_length=100)
    outsideDetections: Count = 0
    reviewThresholds: Thresholds | None = None
    prediction: Prediction | None = None
    pipeline: (
        Literal["combined", "detector", "baseline", "duplicates_only", "classifier_only"] | None
    ) = None
    runtime: Literal["onnx", "torch"] | None = None
    classificationScoresAreCalibrated: bool | None = None
    datasetFingerprint: Text | None = None
    modelSha256: ModelDigests | None = None
    rectified: bool | None = None
    inferenceMs: Milliseconds | None = None
    timings: Timings | None = None
    imageSha256: Digest | None = None
    imageWidth: int | None = Field(default=None, gt=0, le=2048)
    imageHeight: int | None = Field(default=None, gt=0, le=2048)

    @model_validator(mode="after")
    def unique_coordinates(self):
        for squares in (self.reviewSquares, self.squareCandidates):
            if len({(square.row, square.col) for square in squares}) != len(squares):
                raise ValueError("Square coordinates must be unique")
        return self
