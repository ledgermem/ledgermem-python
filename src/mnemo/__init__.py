"""Mnemo Memory — Python SDK.

Quickstart:

    from getmnemo import Mnemo

    memory = Mnemo(api_key="lk_live_...", workspace_id="ws_...")
    memory.add("User prefers Japanese short-grain rice for onigiri.")
    response = memory.search("what kind of rice does the user like?")
    for hit in response.hits:
        print(hit.score, hit.content)

Async variant:

    import asyncio
    from getmnemo import AsyncMnemo

    async def main() -> None:
        async with AsyncMnemo(api_key="...", workspace_id="...") as m:
            await m.add("Trip to Costa Rica was 5 days, brought 7 shirts.")
            response = await m.search("how many shirts did I pack for Costa Rica?")
            print(response.hits[0].content)

    asyncio.run(main())
"""

from .client import AsyncMnemo, Mnemo
from .errors import MnemoError, MnemoHTTPError
from .models import Memory, SearchHit, SearchResponse

__all__ = [
    "AsyncMnemo",
    "Mnemo",
    "MnemoError",
    "MnemoHTTPError",
    "Memory",
    "SearchHit",
    "SearchResponse",
]

__version__ = "0.1.0"
