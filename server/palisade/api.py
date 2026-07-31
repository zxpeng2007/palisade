"""REST + ndjson streaming routes. The contract is API.md; keep them in step."""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from palisade import auth, db, rules
from palisade.events import hub, presence_dec, presence_inc
from palisade.games import GameError, Player, SEAT_NAMES, manager
from palisade.lobby import check_clock, lobby

router = APIRouter(prefix="/api")

KEEPALIVE = 6.0


def _player(user: dict) -> Player:
    return Player.from_row(user)


def _account_json(user: dict) -> dict:
    fresh = db.one("SELECT * FROM users WHERE id = ?", (user["id"],))
    u = dict(fresh)
    return {"id": u["id"], "username": u["username"], "bot": bool(u["is_bot"]),
            "rating": round(u["rating"]), "rd": round(u["rd"]),
            "games": u["rated_games"]}


async def _body(request: Request) -> dict:
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, "request body must be JSON")
    if not isinstance(data, dict):
        raise HTTPException(400, "request body must be a JSON object")
    return data


# -- accounts ---------------------------------------------------------------

@router.post("/register")
async def register(request: Request, response: Response):
    data = await _body(request)
    username = str(data.get("username", ""))
    password = str(data.get("password", ""))
    user_id = auth.create_user(username, password)
    sid = auth.create_session(user_id)
    response.set_cookie(auth.SESSION_COOKIE, sid, httponly=True,
                        samesite="lax", max_age=180 * 24 * 3600)
    return _account_json({"id": user_id})


@router.post("/login")
async def login(request: Request, response: Response):
    data = await _body(request)
    user = auth.check_login(str(data.get("username", "")),
                            str(data.get("password", "")))
    sid = auth.create_session(user["id"])
    response.set_cookie(auth.SESSION_COOKIE, sid, httponly=True,
                        samesite="lax", max_age=180 * 24 * 3600)
    return _account_json(user)


@router.post("/logout")
async def logout(request: Request, response: Response):
    sid = request.cookies.get(auth.SESSION_COOKIE)
    if sid:
        auth.drop_session(sid)
    response.delete_cookie(auth.SESSION_COOKIE)
    return {"ok": True}


@router.get("/account")
async def account(request: Request):
    return _account_json(auth.require(request))


@router.post("/bot/upgrade")
async def bot_upgrade(request: Request):
    user = auth.require(request)
    fresh = db.one("SELECT rated_games FROM users WHERE id = ?", (user["id"],))
    if fresh["rated_games"] > 0:
        raise HTTPException(400, "account already has rated games")
    db.execute("UPDATE users SET is_bot = 1 WHERE id = ?", (user["id"],))
    return _account_json(user)


@router.post("/token")
async def token_create(request: Request):
    user = auth.require(request)
    data = await _body(request)
    name = str(data.get("name", "token"))[:60]
    scopes = data.get("scopes", ["play"])
    if not isinstance(scopes, list):
        raise HTTPException(400, "scopes must be a list")
    return {"token": auth.create_token(user["id"], name, [str(s) for s in scopes])}


@router.get("/token")
async def token_list(request: Request):
    user = auth.require(request)
    rows = db.query(
        "SELECT name, scopes, created FROM tokens WHERE user_id = ? ORDER BY created",
        (user["id"],))
    return [{"name": r["name"], "scopes": r["scopes"].split(","),
             "created": r["created"]} for r in rows]


@router.get("/user/{username}")
async def user_profile(username: str):
    row = db.one("SELECT * FROM users WHERE username = ?", (username,))
    if row is None:
        raise HTTPException(404, "no such user")
    u = dict(row)
    games = db.query(
        """SELECT g.*, u1.username AS p1name, u2.username AS p2name
           FROM games g JOIN users u1 ON u1.id = g.p1 JOIN users u2 ON u2.id = g.p2
           WHERE (g.p1 = ? OR g.p2 = ?) AND g.status != 'active'
           ORDER BY g.created DESC LIMIT 15""",
        (u["id"], u["id"]))
    recent = []
    for g in games:
        recent.append({
            "id": g["id"], "p1": g["p1name"], "p2": g["p2name"],
            "rated": bool(g["rated"]), "status": g["status"],
            "winner": SEAT_NAMES[g["winner"]] if g["winner"] is not None else None,
            "reason": g["reason"], "created": g["created"],
        })
    return {"username": u["username"], "bot": bool(u["is_bot"]),
            "rating": round(u["rating"]), "provisional": u["rd"] > 110,
            "games": u["rated_games"], "recent": recent}


# -- challenges and seeks ---------------------------------------------------

@router.post("/challenge/{username}")
async def challenge_user(username: str, request: Request):
    user = auth.require(request, "play")
    dest = db.one("SELECT * FROM users WHERE username = ?", (username,))
    if dest is None:
        raise HTTPException(404, "no such user")
    data = await _body(request)
    initial, increment = check_clock(data.get("clock", {}))
    ch = lobby.challenge(_player(user), Player.from_row(dict(dest)),
                         bool(data.get("rated", False)), initial, increment,
                         str(data.get("color", "random")))
    return {"challenge": ch.public()}


@router.post("/challenge/{challenge_id}/accept")
async def challenge_accept(challenge_id: str, request: Request):
    user = auth.require(request, "play")
    game = lobby.accept(challenge_id, user["id"])
    return {"game": game.full_msg()}


@router.post("/challenge/{challenge_id}/decline")
async def challenge_decline(challenge_id: str, request: Request):
    user = auth.require(request, "play")
    lobby.decline(challenge_id, user["id"])
    return {"ok": True}


@router.post("/challenge/{challenge_id}/cancel")
async def challenge_cancel(challenge_id: str, request: Request):
    user = auth.require(request, "play")
    lobby.cancel(challenge_id, user["id"])
    return {"ok": True}


@router.post("/seek")
async def seek(request: Request):
    user = auth.require(request, "play")
    data = await _body(request)
    initial, increment = check_clock(data.get("clock", {}))
    game = lobby.add_seek(_player(user), bool(data.get("rated", False)),
                          initial, increment)
    return {"ok": True, "matched": game is not None}


@router.delete("/seek")
async def seek_cancel(request: Request):
    user = auth.require(request, "play")
    lobby.cancel_seek(user["id"])
    return {"ok": True}


# -- playing ----------------------------------------------------------------

class _Buckets:
    """Token bucket per account: burst 20, ~10 moves/second sustained."""

    def __init__(self, burst: float = 20.0, rate: float = 10.0):
        self.burst, self.rate = burst, rate
        self.state: dict[int, tuple[float, float]] = {}

    def take(self, key: int) -> bool:
        level, at = self.state.get(key, (self.burst, time.monotonic()))
        now = time.monotonic()
        level = min(self.burst, level + (now - at) * self.rate)
        if level < 1.0:
            self.state[key] = (level, now)
            return False
        self.state[key] = (level - 1.0, now)
        return True


_buckets = _Buckets()


def _db_game_full(game_id: str) -> dict | None:
    g = db.one(
        """SELECT g.*, u1.username AS p1name, u1.is_bot AS p1bot,
                  u2.username AS p2name, u2.is_bot AS p2bot
           FROM games g JOIN users u1 ON u1.id = g.p1 JOIN users u2 ON u2.id = g.p2
           WHERE g.id = ?""", (game_id,))
    if g is None:
        return None
    state = {
        "type": "gameState", "moves": g["moves"],
        "p1time": None, "p2time": None, "status": g["status"],
        "winner": SEAT_NAMES[g["winner"]] if g["winner"] is not None else None,
        "reason": g["reason"],
    }
    return {
        "type": "gameFull", "id": g["id"], "rated": bool(g["rated"]),
        "clock": {"initial": g["initial"], "increment": g["increment"]},
        "first": {"username": g["p1name"], "rating": round(g["p1_rating"]),
                  "bot": bool(g["p1bot"]), "delta": g["p1_delta"]},
        "second": {"username": g["p2name"], "rating": round(g["p2_rating"]),
                   "bot": bool(g["p2bot"]), "delta": g["p2_delta"]},
        "state": state,
    }


@router.get("/game/stream/{game_id}")
async def game_stream(game_id: str):
    live = manager.get(game_id)
    if live is None:
        full = _db_game_full(game_id)
        if full is None:
            raise HTTPException(404, "no such game")

        async def finished():
            yield json.dumps(full) + "\n"

        return StreamingResponse(finished(), media_type="application/x-ndjson")

    q = hub.subscribe(f"game:{game_id}")

    async def stream():
        try:
            yield json.dumps(live.full_msg()) + "\n"
            if live.status != "active":
                return
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), KEEPALIVE)
                except asyncio.TimeoutError:
                    yield "\n"
                    continue
                yield json.dumps(msg) + "\n"
                if msg.get("status") != "active":
                    return
        finally:
            hub.unsubscribe(f"game:{game_id}", q)

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@router.get("/game/{game_id}")
async def game_get(game_id: str):
    live = manager.get(game_id)
    if live is not None:
        full = live.full_msg()
        full["view"] = rules.view(live.st)
        return full
    full = _db_game_full(game_id)
    if full is None:
        raise HTTPException(404, "no such game")
    moves = full["state"]["moves"]
    full["view"] = rules.view(rules.replay(moves.split(",") if moves else []))
    return full


def _live_game(game_id: str):
    game = manager.get(game_id)
    if game is None:
        raise HTTPException(404, "no such live game")
    return game


@router.post("/game/{game_id}/move/{token}")
async def game_move(game_id: str, token: str, request: Request):
    user = auth.require(request, "play")
    if not _buckets.take(user["id"]):
        raise HTTPException(429, "slow down")
    try:
        await _live_game(game_id).move(user["id"], token)
    except GameError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@router.post("/game/{game_id}/resign")
async def game_resign(game_id: str, request: Request):
    user = auth.require(request, "play")
    try:
        await _live_game(game_id).resign(user["id"])
    except GameError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@router.post("/game/{game_id}/abort")
async def game_abort(game_id: str, request: Request):
    user = auth.require(request, "play")
    try:
        await _live_game(game_id).abort(user["id"])
    except GameError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


# -- event stream -----------------------------------------------------------

@router.get("/stream/event")
async def event_stream(request: Request):
    user = auth.require(request)
    q = hub.subscribe(f"user:{user['id']}")
    presence_inc(user["id"])
    hub.publish("lobby", {"type": "lobbyChanged"})

    async def stream():
        try:
            yield "\n"
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), KEEPALIVE)
                except asyncio.TimeoutError:
                    yield "\n"
                    continue
                yield json.dumps(msg) + "\n"
        finally:
            hub.unsubscribe(f"user:{user['id']}", q)
            presence_dec(user["id"])
            hub.publish("lobby", {"type": "lobbyChanged"})

    return StreamingResponse(stream(), media_type="application/x-ndjson")
