"""Pydantic models for the Healf agent."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


Currency = Literal["GBP", "USD", "EUR"]


class Image(BaseModel):
    url: HttpUrl
    alt: str | None = None
    width: int | None = None
    height: int | None = None


class Review(BaseModel):
    review_id: str
    product_gid: str
    author: str | None = None
    rating: int = Field(ge=1, le=5)
    title: str | None = None
    body: str
    created_at: datetime | None = None
    verified: bool = False

    def polarity(self) -> Literal["positive", "neutral", "negative"]:
        if self.rating >= 4:
            return "positive"
        if self.rating == 3:
            return "neutral"
        return "negative"


class Product(BaseModel):
    url: HttpUrl
    handle: str
    title: str
    brand: str
    product_type: str
    description: str
    price_gbp: float
    currency: Currency
    sku: str
    gid: str
    images: list[Image] = Field(default_factory=list)
    ingredients: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    rating_value: float | None = None
    rating_count: int | None = None
    raw_jsonld: dict | None = None
    raw_metafields: dict | None = None

    @field_validator("handle")
    @classmethod
    def _handle_is_slug(cls, v: str) -> str:
        if not v or "/" in v or " " in v:
            raise ValueError("handle must be a URL slug")
        return v


class ReviewTheme(BaseModel):
    product_gid: str
    polarity: Literal["positive", "negative", "neutral"]
    label: str
    summary: str
    review_ids: list[str]
    weight: float


class RubricScore(BaseModel):
    axis: str
    score: int = Field(ge=1, le=5)
    rationale: str


class CorpusReference(BaseModel):
    handle: str
    title: str
    why: str


class EvalReport(BaseModel):
    product_handle: str
    scores: list[RubricScore]
    gaps: list[str]
    corpus_references: list[CorpusReference]

    def average(self) -> float:
        if not self.scores:
            return 0.0
        return sum(s.score for s in self.scores) / len(self.scores)


class ConsistencyFinding(BaseModel):
    kind: Literal["ingredient_mismatch", "claim_unsupported", "image_underrepresented", "label_ocr_conflict"]
    detail: str
    evidence: str


class ConsistencyReport(BaseModel):
    product_handle: str
    findings: list[ConsistencyFinding]


class HITLEntry(BaseModel):
    id: int | None = None
    product_handle: str
    original_description: str
    drafted_description: str
    gap_summary: str
    status: Literal["pending", "approved", "rejected", "edited"] = "pending"
    created_at: datetime | None = None


class Comparison(BaseModel):
    handles: list[str]
    rows: list[dict]
    summary: str
