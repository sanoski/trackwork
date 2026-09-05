"""Admin API: accounts, organisation settings, the weekly timer, and a mail check.

Thin wiring over app.users, app.app_settings, and app.scheduler. Every route requires the
admin role. Errors map like the rest of the API: LookupError is 404, ValueError is 409.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from starlette.concurrency import run_in_threadpool

from .. import app_settings, mcp_tokens, scheduler, users
from ..auth import require_admin
from ..config import settings
from ..limiter import limiter
from ..models import (
    McpTokenCreateRequest,
    SettingsUpdateRequest,
    TestEmailRequest,
    User,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from .common import service

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _user_out(u: User) -> UserResponse:
    return UserResponse(email=u.email, name=u.name, role=u.role)


# ── Accounts ──────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserResponse])
async def list_users():
    return [_user_out(u) for u in users.list_users()]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreateRequest):
    return _user_out(service(users.create_user, body.email, body.name, body.password, body.role))


@router.patch("/users/{email}", response_model=UserResponse)
async def update_user(email: str, body: UserUpdateRequest):
    return _user_out(service(users.update_user, email, name=body.name, role=body.role,
                             password=body.password))


@router.delete("/users/{email}")
async def delete_user(email: str):
    removed = service(users.delete_user, email)
    return {"deleted": removed.email}


# ── Organisation settings ─────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings():
    return app_settings.public_view()


@router.put("/settings")
async def update_settings(body: SettingsUpdateRequest):
    """Partial update. Saving a new day or time re-arms the weekly timer immediately."""
    updated = service(app_settings.update_settings, body.model_dump(exclude_none=True))
    scheduler.reschedule()
    return app_settings.public_view(updated)


@router.post("/settings/test-email")
@limiter.limit("4/minute")
async def test_email(request: Request, body: TestEmailRequest):
    try:
        sent = await run_in_threadpool(app_settings.test_email, str(body.to))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The test email could not be sent. Check the SMTP host, port, user, and password.",
        )
    return {"ok": True, "sent_to": sent}


# ── Weekly timer ──────────────────────────────────────────────────────────────

@router.get("/scheduler")
async def scheduler_status():
    return scheduler.status()


@router.post("/scheduler/run-now")
async def scheduler_run_now():
    """Send this week's report to the configured recipients right now."""
    return await run_in_threadpool(scheduler.run_now)


# ── AI assistant (MCP) tokens ──────────────────────────────────────────────────

@router.get("/mcp-tokens")
async def list_mcp_tokens():
    """Token records (never the token strings) plus how the MCP endpoint is configured."""
    base = settings.mcp_base_url.rstrip("/") if settings.mcp_base_url else ""
    return {
        "enabled": settings.mcp_enabled,
        "provider": settings.mcp_auth_provider,
        "url": f"{base}/mcp" if base else None,
        "tokens": mcp_tokens.list_tokens(),
    }


@router.post("/mcp-tokens", status_code=status.HTTP_201_CREATED)
async def create_mcp_token(body: McpTokenCreateRequest):
    """Mint a token for one existing account. The token is returned once and never stored."""
    service(users.find_user, body.email)
    try:
        token, record = mcp_tokens.create_token(body.email, body.label, body.days)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return {"token": token, "record": record}


@router.delete("/mcp-tokens/{jti}")
async def revoke_mcp_token(jti: str):
    return {"revoked": service(mcp_tokens.revoke_token, jti)}
