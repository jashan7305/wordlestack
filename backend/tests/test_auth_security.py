import pytest
from fastapi import HTTPException

from app.api.deps import admin_user, csrf_check
from app.core.security import decode_token, hash_password, issue_token, verify_password
from app.models import Role, User


def test_password_hash_and_jwt_round_trip() -> None:
    encoded = hash_password("very-secure-test-password")
    assert encoded != "very-secure-test-password"
    assert verify_password("very-secure-test-password", encoded)
    assert not verify_password("wrong-password", encoded)
    assert decode_token(issue_token(42)) == 42


def test_only_admin_role_passes_admin_guard() -> None:
    user = User(username="player", password_hash="unused", role=Role.USER)
    with pytest.raises(HTTPException) as error:
        admin_user(user)
    assert error.value.status_code == 403

    admin = User(username="root", password_hash="unused", role=Role.ADMIN)
    assert admin_user(admin) is admin


def test_csrf_requires_matching_cookie_and_header() -> None:
    csrf_check("same-token", "same-token")
    with pytest.raises(HTTPException) as error:
        csrf_check("header-token", "cookie-token")
    assert error.value.status_code == 403
