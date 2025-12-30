from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Header, HTTPException
from pydantic import BaseModel

from edvmp.shared.config import Settings


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def issue_token(settings: Settings, *, subject: str, ttl_seconds: int = 3600) -> TokenResponse:
    now = datetime.now(UTC)
    payload = {
        "iss": settings.jwt_issuer,
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return TokenResponse(access_token=token, expires_in=ttl_seconds)


def make_get_current_user(settings: Settings) -> Callable[[str | None], str]:
    def get_current_user(
        authorization: str | None = Header(default=None),
    ) -> str:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")
        token = authorization.removeprefix("Bearer ").strip()
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        except Exception as err:
            raise HTTPException(status_code=401, detail="Invalid token") from err
        if payload.get("iss") != settings.jwt_issuer:
            raise HTTPException(status_code=401, detail="Invalid token issuer")
        return str(payload.get("sub") or "unknown")

    return get_current_user
