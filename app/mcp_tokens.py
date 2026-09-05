"""Per-user access tokens for the MCP (AI assistant) server.

Each token is a signed JWT tied to one account, with a label, an expiry, and a revocation
switch, so an admin can hand a field lead a token for Claude and take it back later. Records
(never the token string itself) live in DATA_DIR/mcp_tokens.json. This is not a static shared
secret: every token is individual, expires, and can be revoked.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from . import storage
from .config import settings

AUDIENCE = "trackwork-mcp"
ALGORITHM = "HS256"
MAX_DAYS = 365


def _records() -> list[dict]:
    return storage.load_json(settings.mcp_tokens_file, []) or []


def _save(records: list[dict]) -> None:
    storage.save_json(settings.mcp_tokens_file, records)


def list_tokens() -> list[dict]:
    """Token records: id, email, label, created, expires, revoked. Never the token string."""
    return _records()


def create_token(email: str, label: str, days: int = 90) -> tuple[str, dict]:
    """Mint a token for one account. Returns (token, record). The token is shown once."""
    if not settings.secret_key:
        raise RuntimeError("SECRET_KEY must be set before tokens can be issued")
    email = (email or "").strip()
    label = (label or "").strip()
    if not email or "@" not in email:
        raise ValueError("a valid email address is required")
    if not label:
        raise ValueError("a label is required (what this token is for)")
    try:
        days = int(days)
    except (TypeError, ValueError):
        raise ValueError("days must be a number")
    if not 1 <= days <= MAX_DAYS:
        raise ValueError(f"days must be between 1 and {MAX_DAYS}")
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=days)
    jti = secrets.token_urlsafe(12)
    record = {
        "id": jti, "email": email, "label": label,
        "created": now.isoformat(timespec="seconds"),
        "expires": exp.isoformat(timespec="seconds"),
        "revoked": False,
    }
    token = jwt.encode(
        {"sub": email, "jti": jti, "aud": AUDIENCE, "iat": int(now.timestamp()),
         "exp": int(exp.timestamp()), "scope": "mcp"},
        settings.secret_key, algorithm=ALGORITHM,
    )
    records = _records()
    records.append(record)
    _save(records)
    return token, record


def revoke_token(jti: str) -> dict:
    records = _records()
    rec = next((r for r in records if r["id"] == jti), None)
    if rec is None:
        raise LookupError(f"No token with id '{jti}'")
    rec["revoked"] = True
    _save(records)
    return rec


def verify(token: str) -> Optional[dict]:
    """The record for a valid token (signed by us, right audience, not expired, not revoked),
    with the decoded claims under 'claims'. None for anything else."""
    if not settings.secret_key or not token:
        return None
    try:
        claims = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM], audience=AUDIENCE)
    except JWTError:
        return None
    rec = next((r for r in _records() if r["id"] == claims.get("jti")), None)
    if rec is None or rec.get("revoked"):
        return None
    return {**rec, "claims": claims}
