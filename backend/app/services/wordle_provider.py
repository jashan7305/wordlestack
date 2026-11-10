from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Puzzle

BASE_URL = "https://www.nytimes.com/svc/wordle/v2/{puzzle_date}.json"


class ProviderError(RuntimeError):
    pass


async def fetch_puzzle(puzzle_date: date) -> dict[str, object]:
    """Fetch and validate a NYT daily puzzle with bounded retries."""
    async with httpx.AsyncClient(
        timeout=8.0, headers={"User-Agent": "WordleStack/1.0"}
    ) as client:
        for attempt in range(3):
            try:
                response = await client.get(
                    BASE_URL.format(puzzle_date=puzzle_date.isoformat())
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ProviderError("Puzzle provider returned invalid data")
                solution = payload.get("solution")
                provider_date = date.fromisoformat(payload.get("print_date", ""))
                if (
                    not isinstance(solution, str)
                    or len(solution) != 5
                    or not solution.isascii()
                    or not solution.isalpha()
                    or provider_date != puzzle_date
                ):
                    raise ProviderError("Puzzle provider returned invalid data")
                return {
                    "print_date": provider_date,
                    "solution": solution.lower(),
                    "days_since_launch": payload.get("days_since_launch"),
                    "editor": payload.get("editor"),
                }
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                if attempt == 2:
                    raise ProviderError("Daily puzzle provider is unavailable") from exc
        raise ProviderError("Daily puzzle provider is unavailable")


async def sync_puzzle(db: Session, puzzle_date: date) -> Puzzle:
    cached = db.scalar(select(Puzzle).where(Puzzle.print_date == puzzle_date))
    if cached:
        return cached
    data = await fetch_puzzle(puzzle_date)
    statement = (
        insert(Puzzle)
        .values(**data)
        .on_conflict_do_nothing(index_elements=["print_date"])
    )
    db.execute(statement)
    db.commit()
    return db.scalar(select(Puzzle).where(Puzzle.print_date == puzzle_date))  # type: ignore[return-value]
