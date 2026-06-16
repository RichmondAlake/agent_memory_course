"""Pydantic request bodies for the API."""
from __future__ import annotations

from pydantic import BaseModel


class AssistantRequest(BaseModel):
    session_id: str
    message: str


class WorkflowRequest(BaseModel):
    applicant_id: str = "A-001"


class ResearchRequest(BaseModel):
    question: str
