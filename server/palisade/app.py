"""Application assembly.

    uvicorn palisade.app:app --host 0.0.0.0 --port 8000

Environment: PALISADE_DB (sqlite path, default ./palisade.db). If web/dist
exists (built SPA), it is served at the root; the API lives under /api and
the browser socket at /ws either way.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from palisade import db, rules, ws
from palisade.api import router


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
        print(f"palisade: aborted {n} game(s) interrupted by restart")
    db.run("DELETE FROM sessions WHERE created < datetime('now', '-30 days')")
    rules.warmup()
    yield


app = FastAPI(title="Palisade", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)


app.include_router(router)


@app.websocket("/ws")
async def websocket(socket: WebSocket):
    await ws.handle(socket)


_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="web")
else:
    @app.get("/")
    async def root():
        return {"palisade": "API is up; web client not built (see web/README)"}
