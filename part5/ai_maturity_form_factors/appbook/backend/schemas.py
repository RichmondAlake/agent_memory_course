"""Pydantic request bodies for the API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Client-generated conversation id")
    message: str


class RagRequest(BaseModel):
    query: str
    technique: str = "vector"   # vector | keyword | hybrid | graph
    k: int = 4


class WorkflowRequest(BaseModel):
    message: str
    max_revisions: int = 1


class WorkflowDecisionRequest(BaseModel):
    workflow_id: str
    approved: bool
    reason: str = ""            # human feedback used to redraft when declined


class AgentRequest(BaseModel):
    prompt: str


class BuilderRequest(BaseModel):
    task: str


class AutomationSaveRequest(BaseModel):
    name: str
    command: str


class ScheduleRequest(BaseModel):
    type: str = "manual"            # manual | once | interval | daily
    every_minutes: int = 5
    delay_minutes: int = 5
    at: str = "08:00"               # HH:MM for daily
