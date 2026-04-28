"""LedgerMem Memory — Python SDK.

Quickstart:

    from ledgermem import LedgerMem

    memory = LedgerMem(api_key="lk_live_...", workspace_id="ws_...")
    memory.add("User prefers Japanese short-grain rice for onigiri.")
    response = memory.search("what kind of rice does the user like?")
    for hit in response.hits:
        print(hit.score, hit.content)

Async variant:

    import asyncio
    from ledgermem import AsyncLedgerMem

    async def main() -> None:
        async with AsyncLedgerMem(api_key="...", workspace_id="...") as m:
            await m.add("Trip to Costa Rica was 5 days, brought 7 shirts.")
            response = await m.search("how many shirts did I pack for Costa Rica?")
            print(response.hits[0].content)

    asyncio.run(main())
"""

from .client import AsyncLedgerMem, LedgerMem
from .errors import LedgerMemError, LedgerMemHTTPError
from .models import Memory, SearchHit, SearchResponse

__all__ = [
    "AsyncLedgerMem",
    "LedgerMem",
    "LedgerMemError",
    "LedgerMemHTTPError",
    "Memory",
    "SearchHit",
    "SearchResponse",
]

__version__ = "0.1.0"
