"""Pydantic request bodies for the API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ConversationRequest(BaseModel):
    session_id: str = Field(..., description="Client-generated conversation id")
    message: str


class SemanticRequest(BaseModel):
    session_id: str = Field(..., description="Client-generated conversation id")
    message: str


class KnowledgeRequest(BaseModel):
    query: str
    k: int = 4


class ProceduralRequest(BaseModel):
    message: str


class CoordinationRequest(BaseModel):
    prompt: str
