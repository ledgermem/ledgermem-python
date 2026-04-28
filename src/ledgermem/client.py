"""Sync + async LedgerMem clients.

Both clients share the same surface; the async one is suitable for use inside
LangGraph nodes, FastAPI routes, or any other event-loop-friendly codebase.
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from typing import Any, Awaitable, Callable, TypeVar

import httpx
from typing_extensions import Self

from .errors import LedgerMemHTTPError
from .models import Memory, PaginatedMemories, SearchResponse

_DEFAULT_BASE_URL = "https://api.proofly.dev"
_DEFAULT_TIMEOUT = 30.0
_USER_AGENT = "ledgermem-python/0.1.0"
_DEFAULT_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 0.2
_RETRY_MAX_DELAY = 5.0

T = TypeVar("T")


def _retry_delay(attempt: int) -> float:
    """Exponential backoff with full jitter."""
    capped = min(_RETRY_BASE_DELAY * (2**attempt), _RETRY_MAX_DELAY)
    return random.uniform(0, capped)


def _is_retryable_status(status: int) -> bool:
    return status == 429 or 500 <= status < 600


def _send_with_retries(
    fn: Callable[[], httpx.Response],
    max_retries: int,
) -> httpx.Response:
    attempt = 0
    while True:
        try:
            resp = fn()
        except (httpx.TransportError, httpx.TimeoutException):
            if attempt >= max_retries:
                raise
            time.sleep(_retry_delay(attempt))
            attempt += 1
            continue
        if _is_retryable_status(resp.status_code) and attempt < max_retries:
            time.sleep(_retry_delay(attempt))
            attempt += 1
            continue
        return resp


async def _send_with_retries_async(
    fn: Callable[[], Awaitable[httpx.Response]],
    max_retries: int,
) -> httpx.Response:
    attempt = 0
    while True:
        try:
            resp = await fn()
        except (httpx.TransportError, httpx.TimeoutException):
            if attempt >= max_retries:
                raise
            await asyncio.sleep(_retry_delay(attempt))
            attempt += 1
            continue
        if _is_retryable_status(resp.status_code) and attempt < max_retries:
            await asyncio.sleep(_retry_delay(attempt))
            attempt += 1
            continue
        return resp


def _resolve(value: str | None, env_var: str, label: str) -> str:
    resolved = value or os.environ.get(env_var)
    if not resolved:
        raise ValueError(
            f"{label} is required. Pass it explicitly or set ${env_var}.",
        )
    return resolved


def _headers(api_key: str, workspace_id: str, actor_id: str | None) -> dict[str, str]:
    h = {
        "authorization": f"Bearer {api_key}",
        "x-workspace-id": workspace_id,
        "user-agent": _USER_AGENT,
        "content-type": "application/json",
    }
    if actor_id is not None:
        h["x-actor-id"] = actor_id
    return h


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.is_success:
        return
    body: Any
    try:
        body = resp.json()
        message = body.get("message") if isinstance(body, dict) else str(body)
    except ValueError:
        body = resp.text
        message = body or resp.reason_phrase
    raise LedgerMemHTTPError(message or "Unknown error", resp.status_code, body)


class LedgerMem:
    """Synchronous LedgerMem Memory client.

    All public methods make a single HTTP round-trip and return typed Pydantic
    models. The underlying httpx.Client is created on first use and reused.
    """

    def __init__(
        self,
        api_key: str | None = None,
        workspace_id: str | None = None,
        *,
        actor_id: str | None = None,
        base_url: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        client: httpx.Client | None = None,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ) -> None:
        self._api_key = _resolve(api_key, "LEDGERMEM_API_KEY", "api_key")
        self._workspace_id = _resolve(workspace_id, "LEDGERMEM_WORKSPACE_ID", "workspace_id")
        self._actor_id = actor_id or os.environ.get("LEDGERMEM_ACTOR_ID")
        self._base_url = (base_url or os.environ.get("LEDGERMEM_API_URL") or _DEFAULT_BASE_URL).rstrip("/")
        self._owns_client = client is None
        self._max_retries = max(0, int(max_retries))
        self._client = client or httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            headers=_headers(self._api_key, self._workspace_id, self._actor_id),
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # ----- public API -----

    def search(
        self,
        query: str,
        *,
        limit: int = 8,
        actor_id: str | None = None,
    ) -> SearchResponse:
        payload: dict[str, Any] = {"query": query, "limit": limit}
        if actor_id is not None:
            payload["actorId"] = actor_id
        resp = _send_with_retries(
            lambda: self._client.post("/v1/search", json=payload),
            self._max_retries,
        )
        _raise_for_status(resp)
        return SearchResponse.model_validate(resp.json())

    def add(
        self,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
        actor_id: str | None = None,
    ) -> Memory:
        payload: dict[str, Any] = {"content": content}
        if metadata is not None:
            payload["metadata"] = metadata
        if actor_id is not None:
            payload["actorId"] = actor_id
        resp = _send_with_retries(
            lambda: self._client.post("/v1/memories", json=payload),
            self._max_retries,
        )
        _raise_for_status(resp)
        return Memory.model_validate(resp.json())

    def update(
        self,
        memory_id: str,
        *,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Memory:
        payload: dict[str, Any] = {}
        if content is not None:
            payload["content"] = content
        if metadata is not None:
            payload["metadata"] = metadata
        if not payload:
            raise ValueError("update() requires at least one of content/metadata")
        resp = _send_with_retries(
            lambda: self._client.patch(f"/v1/memories/{memory_id}", json=payload),
            self._max_retries,
        )
        _raise_for_status(resp)
        return Memory.model_validate(resp.json())

    def delete(self, memory_id: str) -> None:
        resp = _send_with_retries(
            lambda: self._client.delete(f"/v1/memories/{memory_id}"),
            self._max_retries,
        )
        _raise_for_status(resp)

    def list(
        self,
        *,
        limit: int = 20,
        cursor: str | None = None,
        actor_id: str | None = None,
    ) -> PaginatedMemories:
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        if actor_id is not None:
            params["actorId"] = actor_id
        resp = _send_with_retries(
            lambda: self._client.get("/v1/memories", params=params),
            self._max_retries,
        )
        _raise_for_status(resp)
        return PaginatedMemories.model_validate(resp.json())


class AsyncLedgerMem:
    """Asynchronous variant of :class:`LedgerMem`.

    Use as an async context manager so the underlying connection pool is
    closed deterministically.
    """

    def __init__(
        self,
        api_key: str | None = None,
        workspace_id: str | None = None,
        *,
        actor_id: str | None = None,
        base_url: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ) -> None:
        self._api_key = _resolve(api_key, "LEDGERMEM_API_KEY", "api_key")
        self._workspace_id = _resolve(workspace_id, "LEDGERMEM_WORKSPACE_ID", "workspace_id")
        self._actor_id = actor_id or os.environ.get("LEDGERMEM_ACTOR_ID")
        self._base_url = (base_url or os.environ.get("LEDGERMEM_API_URL") or _DEFAULT_BASE_URL).rstrip("/")
        self._owns_client = client is None
        self._max_retries = max(0, int(max_retries))
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers=_headers(self._api_key, self._workspace_id, self._actor_id),
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search(
        self,
        query: str,
        *,
        limit: int = 8,
        actor_id: str | None = None,
    ) -> SearchResponse:
        payload: dict[str, Any] = {"query": query, "limit": limit}
        if actor_id is not None:
            payload["actorId"] = actor_id
        resp = await _send_with_retries_async(
            lambda: self._client.post("/v1/search", json=payload),
            self._max_retries,
        )
        _raise_for_status(resp)
        return SearchResponse.model_validate(resp.json())

    async def add(
        self,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
        actor_id: str | None = None,
    ) -> Memory:
        payload: dict[str, Any] = {"content": content}
        if metadata is not None:
            payload["metadata"] = metadata
        if actor_id is not None:
            payload["actorId"] = actor_id
        resp = await _send_with_retries_async(
            lambda: self._client.post("/v1/memories", json=payload),
            self._max_retries,
        )
        _raise_for_status(resp)
        return Memory.model_validate(resp.json())

    async def update(
        self,
        memory_id: str,
        *,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Memory:
        payload: dict[str, Any] = {}
        if content is not None:
            payload["content"] = content
        if metadata is not None:
            payload["metadata"] = metadata
        if not payload:
            raise ValueError("update() requires at least one of content/metadata")
        resp = await _send_with_retries_async(
            lambda: self._client.patch(f"/v1/memories/{memory_id}", json=payload),
            self._max_retries,
        )
        _raise_for_status(resp)
        return Memory.model_validate(resp.json())

    async def delete(self, memory_id: str) -> None:
        resp = await _send_with_retries_async(
            lambda: self._client.delete(f"/v1/memories/{memory_id}"),
            self._max_retries,
        )
        _raise_for_status(resp)

    async def list(
        self,
        *,
        limit: int = 20,
        cursor: str | None = None,
        actor_id: str | None = None,
    ) -> PaginatedMemories:
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        if actor_id is not None:
            params["actorId"] = actor_id
        resp = await _send_with_retries_async(
            lambda: self._client.get("/v1/memories", params=params),
            self._max_retries,
        )
        _raise_for_status(resp)
        return PaginatedMemories.model_validate(resp.json())
