"""Auth for the MCP server, chosen by MCP_AUTH_PROVIDER.

token  = per-user tokens issued by the app (app/mcp_tokens.py). Works with Claude Code, the
         Claude desktop app, and any client that sends a bearer header. Needs no outside account.
azure | google | github = sign in through that provider (FastMCP's OAuth proxy). This is what
         claude.ai web connectors need, because they register themselves dynamically.
none   = no auth. Local development only, never on the internet.
"""
from __future__ import annotations

from urllib.parse import urlparse

from fastmcp.server.auth import AccessToken, TokenVerifier

from app import mcp_tokens
from app.config import settings


class TrackworkTokenVerifier(TokenVerifier):
    """Accepts tokens created in Users & Settings (or with `cli token create`)."""

    async def verify_token(self, token: str) -> AccessToken | None:
        rec = mcp_tokens.verify(token)
        if rec is None:
            return None
        return AccessToken(
            token=token, client_id=rec["email"], scopes=["mcp"],
            expires_at=rec["claims"].get("exp"), subject=rec["email"],
            claims={"label": rec["label"], "jti": rec["id"]},
        )


def _need(*names: str) -> None:
    missing = [n.upper() for n in names if not getattr(settings, n)]
    if missing:
        raise RuntimeError(
            f"MCP_AUTH_PROVIDER={settings.mcp_auth_provider} needs these settings: {', '.join(missing)}")


def build_auth():
    """The auth provider for FastMCP, or None for no auth."""
    provider = (settings.mcp_auth_provider or "token").strip().lower()
    if provider == "none":
        return None
    if provider == "token":
        return TrackworkTokenVerifier()
    _need("mcp_base_url", "mcp_oauth_client_id", "mcp_oauth_client_secret")
    if provider == "azure":
        _need("mcp_oauth_tenant")
        from fastmcp.server.auth.providers.azure import AzureProvider
        return AzureProvider(
            client_id=settings.mcp_oauth_client_id, client_secret=settings.mcp_oauth_client_secret,
            tenant_id=settings.mcp_oauth_tenant, required_scopes=["User.Read"],
            base_url=settings.mcp_base_url)
    if provider == "google":
        from fastmcp.server.auth.providers.google import GoogleProvider
        return GoogleProvider(
            client_id=settings.mcp_oauth_client_id, client_secret=settings.mcp_oauth_client_secret,
            base_url=settings.mcp_base_url)
    if provider == "github":
        from fastmcp.server.auth.providers.github import GitHubProvider
        return GitHubProvider(
            client_id=settings.mcp_oauth_client_id, client_secret=settings.mcp_oauth_client_secret,
            base_url=settings.mcp_base_url)
    raise RuntimeError(
        f"unknown MCP_AUTH_PROVIDER '{provider}' (use token, azure, google, github, or none)")


def allowed_hosts() -> list[str]:
    """Host names the MCP endpoint answers for: the public URL's host plus localhost."""
    hosts = ["localhost", "127.0.0.1"]
    if settings.mcp_base_url:
        host = urlparse(settings.mcp_base_url).hostname
        if host and host not in hosts:
            hosts.append(host)
    return hosts
