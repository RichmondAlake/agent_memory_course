"""Request bodies."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SuiteStart(BaseModel):
    size: Literal["quick", "full"] = "quick"
    tasks: list[str] | None = Field(default=None, description="agent suite only: run just these task ids")
    k: int | None = Field(default=None, ge=1, le=5, description="agent suite only: attempts per task")
    sessions: bool | None = Field(default=None, description="agent suite only: include the session checks")


class TryCheck(BaseModel):
    kind: Literal["states_fact", "abstains", "supported"]
    question: str | None = Field(default=None, max_length=2000)
    answer: str | None = Field(default=None, max_length=4000)
    fact: str | None = Field(default=None, max_length=1000)
    passage: str | None = Field(default=None, max_length=6000)
    claim: str | None = Field(default=None, max_length=1000)
