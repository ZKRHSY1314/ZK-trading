from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

from app.public_opinion.service import CodexPublicOpinionService


router = APIRouter(prefix="/api/public-opinion", tags=["public-opinion"])


class CodexEvidenceItemInput(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    retrieved_at: datetime
    published_at_status: Literal["known", "unknown"]
    published_at: datetime | None = None
    title: str = Field(min_length=6, max_length=160)
    summary: str = Field(min_length=1, max_length=4000)
    source_name: str = Field(min_length=1, max_length=200)
    source_id: str | None = Field(default=None, max_length=120)
    source_tier: Literal["official", "primary_media", "market_media"] = "market_media"
    category: Literal["market", "policy", "sector"] = "market"
    sector_hints: list[str] = Field(default_factory=list, max_length=20)
    claims: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_publication_time(self) -> "CodexEvidenceItemInput":
        if self.published_at_status == "known" and self.published_at is None:
            raise ValueError("published_at is required when published_at_status=known")
        if self.published_at_status == "unknown" and self.published_at is not None:
            raise ValueError("published_at must be omitted when published_at_status=unknown")
        return self


class CodexEvidenceIngestInput(BaseModel):
    evidence: list[CodexEvidenceItemInput] = Field(min_length=1, max_length=300)
    persist: bool = True
    requested_by: str = Field(default="codex", min_length=1, max_length=120)


@router.post("/evidence/ingest")
def ingest_codex_public_opinion_evidence(input_data: CodexEvidenceIngestInput) -> dict:
    evidence = [item.model_dump(mode="json") for item in input_data.evidence]
    return CodexPublicOpinionService().ingest_evidence(
        evidence,
        persist=input_data.persist,
        requested_by=input_data.requested_by,
    )
