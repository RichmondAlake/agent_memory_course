"""Pydantic request bodies for the evaluation API."""
from __future__ import annotations

from pydantic import BaseModel


class BeirRequest(BaseModel):
    k: int = 10
    dataset: str = "scifact"   # which BEIR seed: scifact | fiqa


class EvalRequest(BaseModel):
    model: str | None = None   # override the system-under-test model (e.g. a weaker Haiku)
