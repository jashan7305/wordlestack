from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db import get_db
from app.models import Role, User


def current_user(
    db: Session = Depends(get_db),
    wordlestack_session: str | None = Cookie(default=None),
) -> User:
    if not wordlestack_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in to continue"
        )
    try:
        user = db.get(User, decode_token(wordlestack_session))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="Account is unavailable")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


def csrf_check(
    x_csrf_token: str | None = Header(default=None),
    csrf_cookie: str | None = Cookie(default=None),
) -> None:
    if not csrf_cookie or not x_csrf_token or csrf_cookie != x_csrf_token:
        raise HTTPException(status_code=403, detail="CSRF validation failed")
