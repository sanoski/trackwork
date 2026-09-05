import hashlib
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["pages"])

_STATIC = Path(__file__).resolve().parent.parent / "static"   # not cwd-relative: works under Docker


def _versioned_files():
    """Every file whose change must bust the browser cache: the ES modules and the stylesheet."""
    return sorted((_STATIC / "js").glob("*.js")) + [_STATIC / "style.css"]


def _asset_version() -> str:
    """Short content hash of the cache-busted static assets.

    index.html references them as `/static/app.js?v=__ASSETVER__`; we replace the token with
    this hash so any edit to app.js/style.css yields a new URL, forcing a fresh fetch through
    any CDN or caching proxy in front of the app (they key on the full URL).
    """
    h = hashlib.sha1()
    for path in _versioned_files():
        try:
            h.update(path.read_bytes())
        except OSError:
            h.update(path.name.encode())
    return h.hexdigest()[:10]


@router.get("/", response_class=HTMLResponse)
async def index():
    html = (_STATIC / "index.html").read_text(encoding="utf-8")
    # The app shell must always be revalidated, otherwise a stale cached HTML keeps pointing at
    # the old `?v=` asset hash and the cache-busting above never takes effect (deploys look stale).
    return HTMLResponse(
        html.replace("__ASSETVER__", _asset_version()),
        headers={"Cache-Control": "no-cache"},
    )
