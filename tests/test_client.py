"""Smoke tests for the LedgerMem client.

These tests use httpx's MockTransport so they run offline. Real-API smoke
tests live in tests/integration/ and are gated by LEDGERMEM_RUN_INTEGRATION=1.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest

from ledgermem import AsyncLedgerMem, LedgerMem, LedgerMemHTTPError

ISO = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc).isoformat()


def _memory_response(memory_id: str = "mem_123") -> dict[str, Any]:
    return {
        "id": memory_id,
        "content": "User prefers Japanese rice.",
        "metadata": {"source": "test"},
        "workspaceId": "ws_test",
        "actorId": None,
        "createdAt": ISO,
        "updatedAt": ISO,
    }


def _mock(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(
        base_url="http://test",
        transport=handler,
        headers={"authorization": "Bearer test"},
    )


def test_search_returns_typed_hits() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/search"
        body = json.loads(req.content)
        assert body["query"] == "rice"
        assert body["limit"] == 5
        return httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "memoryId": "mem_1",
                        "content": "User prefers Japanese rice.",
                        "score": 0.91,
                        "metadata": {},
                        "source": {"documentId": "doc_1", "chunkId": "ck_1"},
                    }
                ],
                "query": "rice",
                "latencyMs": 42,
            },
        )

    client = LedgerMem(
        api_key="test",
        workspace_id="ws_test",
        client=_mock(httpx.MockTransport(handler)),
    )
    res = client.search("rice", limit=5)
    assert res.latency_ms == 42
    assert len(res.hits) == 1
    assert res.hits[0].score == 0.91
    assert res.hits[0].source is not None
    assert res.hits[0].source.document_id == "doc_1"


def test_add_memory_returns_typed_memory() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert req.url.path == "/v1/memories"
        return httpx.Response(200, json=_memory_response())

    client = LedgerMem(
        api_key="test",
        workspace_id="ws_test",
        client=_mock(httpx.MockTransport(handler)),
    )
    mem = client.add("User prefers Japanese rice.", metadata={"source": "test"})
    assert mem.id == "mem_123"
    assert mem.workspace_id == "ws_test"


def test_http_error_includes_status_and_body() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "invalid api key"})

    client = LedgerMem(
        api_key="test",
        workspace_id="ws_test",
        client=_mock(httpx.MockTransport(handler)),
    )
    with pytest.raises(LedgerMemHTTPError) as ei:
        client.search("anything")
    assert ei.value.status == 401
    assert "invalid api key" in str(ei.value)


def test_update_requires_at_least_one_field() -> None:
    client = LedgerMem(
        api_key="test",
        workspace_id="ws_test",
        client=_mock(httpx.MockTransport(lambda _r: httpx.Response(200, json=_memory_response()))),
    )
    with pytest.raises(ValueError):
        client.update("mem_1")


@pytest.mark.asyncio
async def test_async_search_round_trips() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/search"
        return httpx.Response(
            200,
            json={"hits": [], "query": "anything", "latencyMs": 1},
        )

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(base_url="http://test", transport=transport)
    async with AsyncLedgerMem(
        api_key="test", workspace_id="ws_test", client=async_client
    ) as m:
        res = await m.search("anything")
    assert res.hits == []
