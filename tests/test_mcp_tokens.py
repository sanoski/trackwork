import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app import mcp_tokens
from app.config import settings


def _sign(**claims):
    return jwt.encode(claims, settings.secret_key, algorithm="HS256")


def test_create_verify_revoke():
    token, rec = mcp_tokens.create_token("lead@example.com", "Claude on phone", 30)
    assert rec["email"] == "lead@example.com" and rec["revoked"] is False
    found = mcp_tokens.verify(token)
    assert found and found["id"] == rec["id"] and found["claims"]["sub"] == "lead@example.com"
    assert [r["id"] for r in mcp_tokens.list_tokens()] == [rec["id"]]
    mcp_tokens.revoke_token(rec["id"])
    assert mcp_tokens.verify(token) is None
    assert mcp_tokens.list_tokens()[0]["revoked"] is True
    with pytest.raises(LookupError):
        mcp_tokens.revoke_token("nope")


@pytest.mark.parametrize("args", [("bad", "x", 30), ("a@b.c", "", 30), ("a@b.c", "x", 0), ("a@b.c", "x", 400)])
def test_create_rejects(args):
    with pytest.raises(ValueError):
        mcp_tokens.create_token(*args)


def test_rejects_tampered_expired_wrong_audience_and_unknown():
    token, rec = mcp_tokens.create_token("lead@example.com", "x", 1)
    assert mcp_tokens.verify(token[:-2] + "zz") is None
    assert mcp_tokens.verify("") is None
    past = int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp())
    future = past + 200000
    assert mcp_tokens.verify(_sign(sub="lead@example.com", jti=rec["id"], aud=mcp_tokens.AUDIENCE, exp=past)) is None
    assert mcp_tokens.verify(_sign(sub="lead@example.com", jti=rec["id"], aud="other", exp=future)) is None
    assert mcp_tokens.verify(_sign(sub="lead@example.com", jti="ghost", aud=mcp_tokens.AUDIENCE, exp=future)) is None


def test_fastmcp_verifier_maps_a_token_to_an_access_token():
    from mcp_server.auth import TrackworkTokenVerifier
    token, _ = mcp_tokens.create_token("lead@example.com", "x", 5)
    verifier = TrackworkTokenVerifier()
    access = asyncio.run(verifier.verify_token(token))
    assert access is not None and access.client_id == "lead@example.com" and "mcp" in access.scopes
    assert asyncio.run(verifier.verify_token("not-a-token")) is None
