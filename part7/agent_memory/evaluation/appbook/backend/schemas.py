"""Request bodies."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SuiteStart(BaseModel):
    size: Literal["quick", "full"] = "quick"
    per_type: int | None = Field(default=None, ge=1, le=10, description="longmemeval: answerable questions per type")
    abstention: int | None = Field(default=None, ge=0, le=10, description="longmemeval: unanswerable questions")
    questions: int | None = Field(default=None, ge=1, le=100, description="factconsolidation: questions")


class TryCheck(BaseModel):
    check: Literal["states_fact", "uses_old_value", "abstains"]
    question: str = Field(min_length=1, max_length=2000)
    answer: str = Field(min_length=1, max_length=6000)
    fact: str | None = Field(default=None, max_length=1000)
    old: str | None = Field(default=None, max_length=500)
