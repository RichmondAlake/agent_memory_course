"""Request bodies and query parameters."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Dataset = Literal["fiqa", "scifact", "arguana"]


class ExploreRequest(BaseModel):
    dataset: Dataset
    query_id: str | None = Field(default=None, max_length=100, description="a stored test or dev query")
    text: str | None = Field(default=None, max_length=4000, description="or a query of your own")
    run_id: str | None = Field(default=None, max_length=64)


class ScoreRequest(BaseModel):
    dataset: Dataset
    kind: Literal["weighted", "rrf", "graph"]
    alpha: float = Field(default=0.8, ge=0, le=1)
    k: float = Field(default=60, ge=1, le=200)
    w: float = Field(default=0.5, ge=0, le=1)
    depth: int = Field(default=50, ge=5, le=100)
    m: int = Field(default=10, ge=1, le=20)
    seeds: int = Field(default=10, ge=1, le=20)
    decay: float = Field(default=0.005, ge=0, le=0.5)
