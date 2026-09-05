from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from . import scheduler
from .config import settings
from .limiter import limiter
from .reporting.render import FONTS_DIR
from .routes import admin, api, auth, pages

_STATIC_DIR = Path(__file__).resolve().parent / "static"

# The MCP (AI assistant) server lives in the same process, served at /mcp, when enabled.
_mcp_app = None
if settings.mcp_enabled:
    from mcp_server.auth import allowed_hosts
    from mcp_server.server import mcp as _mcp
    _mcp_app = _mcp.http_app(path="/mcp", allowed_hosts=allowed_hosts())


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.secret_key:
        raise RuntimeError(
            "SECRET_KEY must be set in .env; generate one with: "
            "python -c \"import secrets; print(secrets.token_hex(32))\"")
    settings.projects_dir.mkdir(parents=True, exist_ok=True)
    settings.archived_dir.mkdir(parents=True, exist_ok=True)
    scheduler.start()
    try:
        if _mcp_app is not None:
            async with _mcp_app.lifespan(app):   # the MCP session manager needs its lifespan run
                yield
        else:
            yield
    finally:
        scheduler.stop()


app = FastAPI(
    title="MOW Tracker",
    description="Maintenance of Way production tracking and weekly reporting for railroad tie gangs.",
    version="2.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def _revalidate_modules(request, call_next):
    """ES modules are imported by relative path (no ?v= token), so tell browsers to revalidate
    them on every load. Unchanged files still come back as a cheap 304."""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/js/") or path == "/static/style.css":
        response.headers["Cache-Control"] = "no-cache"
    return response

app.include_router(auth.router)
app.include_router(api.router)
app.include_router(admin.router)
app.include_router(pages.router)

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
# Bundled Oswald TTFs for the wizard's live HTML preview (the PDF embeds them directly).
app.mount("/report-assets/fonts", StaticFiles(directory=str(FONTS_DIR)), name="report-fonts")

# Mounted last, at the root, so the MCP endpoint is exactly /mcp (no trailing-slash redirect)
# while every route and static mount above still wins for its own paths.
if _mcp_app is not None:
    app.mount("/", _mcp_app)
