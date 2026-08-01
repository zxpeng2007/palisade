"""Application assembly.

    uvicorn murus.app:app --host 0.0.0.0 --port 8000

Environment: MURUS_DB (sqlite path, default ./murus.db),
MURUS_REVIEW_CHECKPOINT and MURUS_REVIEW_SIMS (the engine game review
speaks for, and how hard it thinks). If web/dist exists (built SPA), it is
served at the root; the API lives under /api and the browser socket at /ws
either way.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from murus import db, review, rules, ws
from murus.api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.connect()
    # Reconcile games interrupted by the previous shutdown: their live state
    # is gone, so the honest outcome is an abort (never a rating change).
    # Without this the rows sit 'active' forever, invisible on profiles and
    # wedging any bot that streams them waiting for a result.
    n = db.run("""UPDATE games SET status = 'aborted', reason = 'abort',
                  finished = datetime('now') WHERE status = 'active'""")
    if n:
        print(f"murus: aborted {n} game(s) interrupted by restart")
    db.run("DELETE FROM sessions WHERE created < datetime('now', '-30 days')")
    rules.warmup()
    # One worker for the whole process, draining reviews one at a time; it also
    # re-queues any review the last shutdown interrupted.
    reviewer = review.start()
    try:
        yield
    finally:
        # Ask the analysis to stand down at its next position, then drop the
        # worker. Cancelling alone would not do it: the search runs in a
        # thread, and a thread cannot be interrupted from out here.
        review.stop()
        reviewer.cancel()
        await asyncio.gather(reviewer, return_exceptions=True)


app = FastAPI(title="Murus", docs_url=None, redoc_url=None, lifespan=lifespan)

# Session cookies are marked Secure in production, so a visitor who arrives
# over plain http would sign in and appear to be ignored -- the browser simply
# drops the cookie. Redirect instead. Requires --proxy-headers so the scheme
# reflects the client's connection to the edge, not the tunnel's to us.
FORCE_HTTPS = os.environ.get("MURUS_FORCE_HTTPS", "") not in ("", "0")


@app.middleware("http")
async def https_redirect(request: Request, call_next):
    # Only requests that actually came through the proxy are redirected, and
    # the forwarded header is read directly rather than trusting uvicorn's
    # --proxy-headers flag to be set. A request with no forwarded scheme
    # reached the loopback socket directly -- a local bot or a health check --
    # and must be left alone; redirecting those sends them to https://127.0.0.1,
    # where nothing is listening.
    if FORCE_HTTPS and request.headers.get("x-forwarded-proto") == "http":
        return RedirectResponse(
            str(request.url.replace(scheme="https")), status_code=308)
    return await call_next(request)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)


app.include_router(router)


@app.websocket("/ws")
async def websocket(socket: WebSocket):
    await ws.handle(socket)


class _SpaFiles(StaticFiles):
    """Static files with the cache policy a hashed-asset build needs.

    Vite fingerprints everything under /assets, so those files are immutable
    and can be cached for a year. index.html names them, so it must never be
    cached: a browser holding yesterday's index.html asks for yesterday's
    bundle and a deploy silently fails to reach anyone who has visited before.
    """

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        # Starlette normalises with os.sep, so this is "assets/x.js" on the
        # server and "assets\\x.js" when the suite runs on Windows.
        if path.replace("\\", "/").startswith("assets/"):
            response.headers["cache-control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["cache-control"] = "no-cache"
        return response


_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
if _dist.is_dir():
    app.mount("/", _SpaFiles(directory=str(_dist), html=True), name="web")
else:
    @app.get("/")
    async def root():
        return {"murus": "API is up; web client not built (see web/README)"}
