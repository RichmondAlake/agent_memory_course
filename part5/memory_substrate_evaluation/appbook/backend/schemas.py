"""Request models for the Memory Substrate Evaluation API."""
from __future__ import annotations

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    k: int = 4


class AnswerRequest(BaseModel):
    query: str
    k: int = 3


class WriteRequest(BaseModel):
    title: str
    category: str = "custom"
    content: str
