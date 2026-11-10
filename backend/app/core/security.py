import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return password_hash.verify(password, encoded)


def issue_token(user_id: int) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(days=14)},
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def decode_token(token: str) -> int:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    return int(payload["sub"])


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_invitation_token() -> str:
    return secrets.token_urlsafe(32)
