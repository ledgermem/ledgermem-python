"""Pydantic models mirroring the Mnemo REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class Memory(_Base):
    id: str
    content: str
    metadata: dict[str, Any] | None = None
    workspace_id: str = Field(alias="workspaceId")
    actor_id: str | None = Field(default=None, alias="actorId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class SearchSource(_Base):
    document_id: str | None = Field(default=None, alias="documentId")
    chunk_id: str | None = Field(default=None, alias="chunkId")


class SearchHit(_Base):
    memory_id: str = Field(alias="memoryId")
    content: str
    score: float
    metadata: dict[str, Any] | None = None
    source: SearchSource | None = None


class SearchResponse(_Base):
    hits: list[SearchHit]
    query: str
    latency_ms: float = Field(alias="latencyMs", ge=0)


class PaginatedMemories(_Base):
    items: list[Memory]
    next_cursor: str | None = Field(default=None, alias="nextCursor")
