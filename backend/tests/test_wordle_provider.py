from datetime import date
from typing import Self

import httpx
import pytest

from app.services import wordle_provider
from app.services.wordle_provider import ProviderError, fetch_puzzle


@pytest.mark.asyncio
async def test_fetch_puzzle_parses_provider_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "solution": "crane",
                "print_date": "2025-01-02",
                "days_since_launch": 1093,
                "editor": "Editor",
            }

    class FakeClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, url: str) -> FakeResponse:
            assert url.endswith("2025-01-02.json")
            return FakeResponse()

    monkeypatch.setattr(wordle_provider.httpx, "AsyncClient", FakeClient)
    puzzle = await fetch_puzzle(date(2025, 1, 2))
    assert puzzle == {
        "print_date": date(2025, 1, 2),
        "solution": "crane",
        "days_since_launch": 1093,
        "editor": "Editor",
    }


@pytest.mark.asyncio
async def test_invalid_provider_date_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"solution": "crane", "print_date": "2025-01-03"}

    class FakeClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, _: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(wordle_provider.httpx, "AsyncClient", FakeClient)
    with pytest.raises(ProviderError):
        await fetch_puzzle(date(2025, 1, 2))


@pytest.mark.asyncio
async def test_provider_retries_network_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    class FakeClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, _: str) -> None:
            nonlocal attempts
            attempts += 1
            raise httpx.ConnectError("offline")

    monkeypatch.setattr(wordle_provider.httpx, "AsyncClient", FakeClient)
    with pytest.raises(ProviderError):
        await fetch_puzzle(date(2025, 1, 2))
    assert attempts == 3
