"""Pydantic request bodies for the API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64, description="Client-generated conversation id")
    message: str = Field(..., min_length=1, max_length=8000)


class RagRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    technique: Literal["vector", "keyword", "hybrid", "graph"] = "vector"
    k: int = Field(4, ge=1, le=17)          # the policy has 17 sections
    rerank: bool = False                    # stage 2: re-order 8 candidates with the cross-encoder


class HnswQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)


class SpaceRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    k: int = Field(4, ge=1, le=17)
    category: str | None = Field(None, max_length=64)
    mode: Literal["pre", "in", "post"] = "pre"
    accuracy: int = Field(90, ge=50, le=100)


class PolicyBulletinRequest(BaseModel):
    bulletin_id: str = Field(..., max_length=40)


class PolicyUpdateRequest(BaseModel):
    doc_id: str = Field(..., max_length=64)
    content: str = Field(..., min_length=20, max_length=1500)
    reason: str = Field("", max_length=300)


class WorkflowRequest(BaseModel):
    email: str = Field(..., min_length=20, max_length=8000)
    max_revisions: int = Field(1, ge=0, le=2)


class WorkflowBatchRequest(BaseModel):
    samples: list[str] = Field(..., min_length=1, max_length=6)   # keys of SAMPLE_APPLICATIONS


class UnderwriterRequest(BaseModel):
    application_id: str = Field(..., max_length=36)
    outcome: Literal["approve", "decline"]
    note: str = Field("", max_length=1000)


class AgentRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    session_id: str | None = Field(None, max_length=64)      # resume this session
    fork: bool = False                                       # ...as a new session (what-if)


class BranchRequest(BaseModel):
    session_id: str = Field(..., max_length=64)
    message_uuid: str = Field(..., max_length=64)


class SessionLabelRequest(BaseModel):
    title: str | None = Field(None, max_length=120)
    tag: str | None = Field(None, max_length=60)


class BuilderChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    session_id: str | None = Field(None, max_length=64)      # resume; empty starts a new session


class AutomationSaveRequest(BaseModel):
    name: str = Field("automation", max_length=60)
    command: str = Field("", max_length=500)


class ScheduleRequest(BaseModel):
    type: Literal["manual", "once", "interval", "daily"] = "manual"
    every_minutes: int = Field(5, ge=1, le=1440)
    delay_minutes: int = Field(5, ge=0, le=1440)
    at: str = Field("08:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")   # HH:MM for daily
