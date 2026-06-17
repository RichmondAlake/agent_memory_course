"""Pydantic request bodies for the benchmark app."""
from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    message: str


class SessionRef(BaseModel):
    session_id: str


class BenchmarkRequest(BaseModel):
    turns: int | None = None       # how many scripted turns to run (defaults to settings)
    judge: bool = True             # run the LLM-as-judge pass at the end
