"""Request bodies, with bounds so a page cannot send unbounded input."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from backend.core.session import THREADS


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    thread: str = Field(default="migration")
    budget: int = Field(default=8000, ge=200, le=20000)
    open_page: str | None = Field(default=None, max_length=300)
    cache_domain: str | None = Field(default=None, max_length=60, pattern=r"^[A-Za-z0-9_-]+$")
    data_version: str | None = Field(default=None, max_length=40, pattern=r"^[A-Za-z0-9._-]+$")

    @field_validator("thread")
    @classmethod
    def known_thread(cls, value: str) -> str:
        if value not in THREADS:
            raise ValueError(f"thread must be one of {THREADS}")
        return value

    def context(self) -> dict[str, Any]:
        context: dict[str, Any] = {}
        if self.open_page:
            context["open_page"] = self.open_page
        if self.cache_domain and self.data_version:
            context["cache_domain"] = self.cache_domain
            context["data_version"] = self.data_version
        return context


class ActionRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("params")
    @classmethod
    def bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(str(value)) > 6000:
            raise ValueError("params are too large")
        return value
