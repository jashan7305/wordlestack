import asyncio
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import RequestResponseEndpoint

from app.api.routes import router
from app.core.config import settings
from app.core.security import hash_password
from app.db import SessionLocal
from app.models import Role, User
from app.services.wordle_provider import ProviderError, sync_puzzle

logger = logging.getLogger(__name__)


def bootstrap_admin() -> None:
    with SessionLocal() as db:
        db.execute(
            insert(User)
            .values(
                username=settings.ADMIN_USERNAME.lower(),
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role=Role.ADMIN,
            )
            .on_conflict_do_nothing(index_elements=["username"])
        )
        db.commit()


async def puzzle_sync_loop() -> None:
    while True:
        try:
            with SessionLocal() as db:
                # A PostgreSQL advisory lock prevents duplicate fetches across app workers.
                acquired = db.scalar(text("SELECT pg_try_advisory_lock(73120421)"))
                if acquired:
                    try:
                        day = datetime.now(ZoneInfo(settings.TIMEZONE)).date()
                        await sync_puzzle(db, day)
                    finally:
                        db.execute(text("SELECT pg_advisory_unlock(73120421)"))
        except (ProviderError, SQLAlchemyError):
            # Cached puzzles remain playable when the external provider is unavailable.
            logger.warning(
                "Puzzle synchronization failed; cached puzzles remain available"
            )
        await asyncio.sleep(900)


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_admin()
    task = asyncio.create_task(puzzle_sync_loop())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
app.include_router(router)

_rate_limits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_RATE_WINDOWS = {"auth": (10, 900.0), "invitations": (20, 3600.0)}


@app.middleware("http")
async def rate_limit_sensitive_routes(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    path = request.url.path
    category = (
        "auth"
        if path in {"/api/v1/auth/register", "/api/v1/auth/login"}
        else "invitations"
        if path.startswith("/api/v1/invitations/")
        else None
    )
    if category:
        maximum, window = _RATE_WINDOWS[category]
        address = request.client.host if request.client else "unknown"
        bucket = _rate_limits[(category, address)]
        now = time.monotonic()
        while bucket and now - bucket[0] >= window:
            bucket.popleft()
        if len(bucket) >= maximum:
            retry_after = max(1, int(window - (now - bucket[0])))
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Try again later."},
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)
        if len(_rate_limits) > 10_000:
            _rate_limits.pop(next(iter(_rate_limits)))
    return await call_next(request)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "wordlestack"}


static_dir = Path("static")
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str, request: Request):
        candidate = static_dir / path
        if (
            path
            and candidate.is_file()
            and static_dir.resolve() in candidate.resolve().parents
        ):
            return FileResponse(candidate)
        return FileResponse(static_dir / "index.html")
