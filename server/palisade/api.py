"""REST + ndjson streaming routes. The contract is API.md; keep them in step."""

from __future__ import annotations

import asyncio
import json
import os

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from palisade import auth, db, limits, mail, rules, speed
from palisade.events import hub, is_closed, presence_dec, presence_inc
from palisade.games import GameError, Player, SEAT_NAMES, manager
from palisade.lobby import check_clock, lobby

router = APIRouter(prefix="/api")

KEEPALIVE = 6.0
# Cookies are httponly+lax always; Secure is opt-in because a LAN deployment
# over plain http would otherwise lose its session cookie silently.
COOKIE_SECURE = os.environ.get("PALISADE_SECURE_COOKIES", "") not in ("", "0")
COOKIE_MAX_AGE = 30 * 24 * 3600
# Behind Cloudflare (tunnel or proxied DNS) every TCP peer is the proxy, so
# rate limiting on request.client.host would put the whole internet in one
# bucket. Cloudflare strips CF-Connecting-IP from client requests and sets it
# to the real address, so it is trustworthy exactly when this flag says the
# only way in is through Cloudflare (the server binds 127.0.0.1 either way).
TRUST_CF_IP = os.environ.get("PALISADE_TRUST_CF_IP", "") not in ("", "0")
# One verification mail a minute per account. A full bucket of one means the
# first request always goes through and the next has to wait out the refill.
resend_limit = limits.Buckets(burst=1.0, rate=1 / 60.0)


def _client_key(request: Request) -> str:
    if TRUST_CF_IP:
        ip = request.headers.get("cf-connecting-ip")
        if ip:
            return ip
    return request.client.host if request.client else "unknown"


def _set_session(response: Response, sid: str) -> None:
    response.set_cookie(auth.SESSION_COOKIE, sid, httponly=True,
                        samesite="lax", secure=COOKIE_SECURE,
                        max_age=COOKIE_MAX_AGE)


def _player(user: dict) -> Player:
    return Player.from_row(user)


def _account_json(user: dict) -> dict:
    fresh = db.one("SELECT * FROM users WHERE id = ?", (user["id"],))
    u = dict(fresh)
    return {"id": u["id"], "username": u["username"], "bot": bool(u["is_bot"]),
            "rating": round(u["rating"]), "rd": round(u["rd"]),
            "games": u["rated_games"], "email": u["email"],
            "emailVerified": bool(u["email_verified"])}


async def _body(request: Request) -> dict:
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, "request body must be JSON")
    if not isinstance(data, dict):
        raise HTTPException(400, "request body must be a JSON object")
    return data


# -- accounts ---------------------------------------------------------------

async def _mail_verification(user_id: int, username: str, email: str,
                             changed: bool = False) -> None:
    """Mint a link and send it, or raise MailError for the caller to translate."""
    token = auth.issue_email_token(user_id)
    try:
        await mail.send_verification(email, username, token, changed=changed)
    except mail.MailError as e:
        # The provider's reason is for the operator's log; the response says
        # only that it did not go, so nothing about the account or the mail
        # infrastructure comes back over the wire.
        print(f"palisade: verification mail to {email} failed: {e}", flush=True)
        raise


@router.post("/register")
async def register(request: Request, response: Response):
    if not limits.credentials.take(_client_key(request)):
        raise HTTPException(429, "too many attempts; wait a moment")
    data = await _body(request)
    username = str(data.get("username", ""))
    password = str(data.get("password", ""))
    email = str(data.get("email", ""))
    # scrypt costs ~100ms by design; run it off the event loop.
    user_id = await asyncio.to_thread(auth.create_user, username, password, email)
    try:
        await _mail_verification(user_id, username, email)
    except mail.MailError:
        # The account is real and the password works, so deleting it to make
        # the failure tidy would only turn a retry into "username is taken".
        # Say what happened and point at the door that fixes it.
        raise HTTPException(502, "the account was created but the verification "
                                 "email could not be sent; sign in and ask for "
                                 "another")
    sid = auth.create_session(user_id)
    _set_session(response, sid)
    return _account_json({"id": user_id})


@router.post("/email/verify")
async def email_verify(request: Request):
    # Deliberately open: the link is the credential, and it is routinely opened
    # in a different browser from the one that signed up.
    data = await _body(request)
    user = auth.verify_email_token(str(data.get("token", "")))
    return {"ok": True, "username": user["username"]}


@router.post("/email/resend")
async def email_resend(request: Request):
    user = auth.require_session(request, "request a verification email")
    fresh = db.one("SELECT * FROM users WHERE id = ?", (user["id"],))
    if fresh["email_verified"]:
        # Nothing to do. 200 rather than an error so a client need not special
        # case the stale button on a page opened before the link was used.
        return {"ok": True, "sent": False}
    if not fresh["email"]:
        raise HTTPException(400, "this account has no email address")
    if not resend_limit.take(user["id"]):
        raise HTTPException(429, "a verification email was just sent; "
                                 "give it a minute")
    try:
        await _mail_verification(user["id"], fresh["username"], fresh["email"])
    except mail.MailError:
        raise HTTPException(502, "the verification email could not be sent; "
                                 "try again shortly")
    return {"ok": True, "sent": True}


@router.post("/email/change")
async def email_change(request: Request):
    user = auth.require_session(request, "change your email address")
    data = await _body(request)
    password = str(data.get("password", ""))
    await asyncio.to_thread(auth.verify_password, user["id"], password)
    email = auth.set_email(user["id"], str(data.get("email", "")))
    try:
        await _mail_verification(user["id"], user["username"], email, changed=True)
    except mail.MailError:
        # The address is already stored and unverified, which is the honest
        # state: the account asked to move and has not proved the new address.
        raise HTTPException(502, "the address was changed but the verification "
                                 "email could not be sent; ask for another")
    return _account_json(user)


@router.post("/login")
async def login(request: Request, response: Response):
    if not limits.credentials.take(_client_key(request)):
        raise HTTPException(429, "too many attempts; wait a moment")
    data = await _body(request)
    user = await asyncio.to_thread(
        auth.check_login, str(data.get("username", "")),
        str(data.get("password", "")))
    sid = auth.create_session(user["id"])
    _set_session(response, sid)
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
    auth.require_verified(user, "upgrading to a bot account")
    fresh = db.one("SELECT rated_games FROM users WHERE id = ?", (user["id"],))
    if fresh["rated_games"] > 0:
        raise HTTPException(400, "account already has rated games")
    db.execute("UPDATE users SET is_bot = 1 WHERE id = ?", (user["id"],))
    return _account_json(user)


@router.post("/token")
async def token_create(request: Request):
    # Session-only: if a bearer token could mint tokens, any leaked or
    # narrowly-scoped token could escalate itself to full scopes.
    user = auth.require_session(request)
    data = await _body(request)
    name = str(data.get("name", "token"))[:60]
    scopes = data.get("scopes", ["play"])
    if not isinstance(scopes, list):
        raise HTTPException(400, "scopes must be a list")
    return {"token": auth.create_token(user["id"], name, [str(s) for s in scopes])}


@router.get("/token")
async def token_list(request: Request):
    user = auth.require_session(request)
    rows = db.query(
        "SELECT name, scopes, created FROM tokens WHERE user_id = ? ORDER BY created",
        (user["id"],))
    return [{"name": r["name"], "scopes": r["scopes"].split(","),
             "created": r["created"]} for r in rows]


@router.get("/leaderboard")
async def leaderboard(kind: str = "all", speed_filter: str | None = None,
                      limit: int = 20, request: Request = None):
    # `speed` is the query name; FastAPI would shadow the imported module.
    want_speed = (request.query_params.get("speed") if request else None) or speed_filter
    if kind not in ("all", "human", "bot"):
        raise HTTPException(400, "kind must be all, human, or bot")
    if want_speed is not None and want_speed not in speed.ORDER:
        raise HTTPException(400, f"speed must be one of {list(speed.ORDER)}")
    limit = max(1, min(100, limit))

    where = ["u.rated_games > 0"]
    args: list = []
    if kind == "bot":
        where.append("u.is_bot = 1")
    elif kind == "human":
        where.append("u.is_bot = 0")
    rows = db.query(
        f"""SELECT u.* FROM users u WHERE {' AND '.join(where)}
            ORDER BY u.rd > 110, u.rating DESC LIMIT ?""",
        (*args, limit * 4 if want_speed else limit))

    players = []
    for r in rows:
        u = dict(r)
        if want_speed is not None:
            # Rank only players with a rated game at this speed. Cheap because
            # the game table is small; revisit if it ever is not.
            played = False
            for g in db.query(
                """SELECT initial, increment FROM games
                   WHERE rated = 1 AND status = 'finished'
                     AND (p1 = ? OR p2 = ?)""", (u["id"], u["id"])):
                if speed.category(g["initial"], g["increment"]) == want_speed:
                    played = True
                    break
            if not played:
                continue
        players.append({
            "rank": len(players) + 1,
            "username": u["username"],
            "rating": round(u["rating"]),
            "provisional": u["rd"] > 110,
            "bot": bool(u["is_bot"]),
            "games": u["rated_games"],
        })
        if len(players) >= limit:
            break
    return {"kind": kind, "speed": want_speed, "players": players}


@router.get("/games/top")
async def games_top(kind: str = "all", limit: int = 8):
    if kind not in ("all", "human", "bot"):
        raise HTTPException(400, "kind must be all, human, or bot")
    limit = max(1, min(30, limit))

    def keep(a_bot: bool, b_bot: bool) -> bool:
        # "At least one", not "both": a person against an engine is interesting
        # to both audiences, and under a stricter rule those games would be
        # invisible in every mode -- which is what happened on the live site,
        # where four of five games showed up nowhere.
        if kind == "bot":
            return a_bot or b_bot
        if kind == "human":
            return not a_bot or not b_bot
        return True

    live: dict[str, list] = {}
    for g in manager.live.values():
        a, b = g.players[0].public(), g.players[1].public()
        if not keep(a["bot"], b["bot"]):
            continue
        cat = speed.category(g.initial, g.increment)
        live.setdefault(cat, []).append({
            "id": g.id, "first": a, "second": b, "rated": g.rated,
            "ply": len(g.moves), "speed": cat,
            "clock": {"initial": g.initial, "increment": g.increment},
            "avgRating": round((a["rating"] + b["rating"]) / 2),
        })

    recent: dict[str, list] = {}
    for row in db.query(
        """SELECT g.*, u1.username AS p1name, u1.is_bot AS p1bot,
                  u2.username AS p2name, u2.is_bot AS p2bot
           FROM games g JOIN users u1 ON u1.id = g.p1 JOIN users u2 ON u2.id = g.p2
           WHERE g.status = 'finished'
           ORDER BY g.finished DESC LIMIT 300"""
    ):
        g = dict(row)
        if not keep(bool(g["p1bot"]), bool(g["p2bot"])):
            continue
        cat = speed.category(g["initial"], g["increment"])
        bucket = recent.setdefault(cat, [])
        if len(bucket) >= limit:
            continue
        r1 = g["p1_rating"] or 1500
        r2 = g["p2_rating"] or 1500
        bucket.append({
            "id": g["id"],
            "first": {"username": g["p1name"], "rating": round(r1),
                      "bot": bool(g["p1bot"])},
            "second": {"username": g["p2name"], "rating": round(r2),
                       "bot": bool(g["p2bot"])},
            "rated": bool(g["rated"]), "speed": cat,
            "winner": SEAT_NAMES[g["winner"]] if g["winner"] is not None else None,
            "reason": g["reason"],
            "clock": {"initial": g["initial"], "increment": g["increment"]},
            "avgRating": round((r1 + r2) / 2),
            "finished": g["finished"],
        })

    for bucket in live.values():
        bucket.sort(key=lambda x: -x["avgRating"])
        del bucket[limit:]
    return {"live": {k: v for k, v in live.items() if v},
            "recent": {k: v for k, v in recent.items() if v}}


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
    rated = bool(data.get("rated", False))
    if rated:
        auth.require_verified(user, "sending a rated challenge")
    ch = lobby.challenge(_player(user), Player.from_row(dict(dest)),
                         rated, initial, increment,
                         str(data.get("color", "random")))
    return {"challenge": ch.public()}


@router.post("/challenge/{challenge_id}/accept")
async def challenge_accept(challenge_id: str, request: Request):
    user = auth.require(request, "play")
    # A rated game makes a claim about both seats, so both have to be confirmed
    # accounts -- gating only the challenger would leave the obvious way round.
    pending = lobby.challenges.get(challenge_id)
    if pending is not None and pending.rated:
        auth.require_verified(user, "accepting a rated challenge")
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
    rated = bool(data.get("rated", False))
    if rated:
        auth.require_verified(user, "posting a rated seek")
    game = lobby.add_seek(_player(user), rated, initial, increment)
    return {"ok": True, "matched": game is not None}


@router.delete("/seek")
async def seek_cancel(request: Request):
    user = auth.require(request, "play")
    lobby.cancel_seek(user["id"])
    return {"ok": True}


# -- playing ----------------------------------------------------------------

def _db_game_full(game_id: str) -> dict | None:
    g = db.one(
        """SELECT g.*, u1.username AS p1name, u1.is_bot AS p1bot,
                  u2.username AS p2name, u2.is_bot AS p2bot
           FROM games g JOIN users u1 ON u1.id = g.p1 JOIN users u2 ON u2.id = g.p2
           WHERE g.id = ?""", (game_id,))
    if g is None:
        return None
    moves = g["moves"].split(",") if g["moves"] else []
    state = {
        "type": "gameState", "moves": g["moves"],
        "view": rules.view(rules.replay(moves)),
        "p1time": None, "p2time": None, "status": g["status"],
        "winner": SEAT_NAMES[g["winner"]] if g["winner"] is not None else None,
        "reason": g["reason"],
    }
    def _r(x):
        return round(x) if x is not None else None

    return {
        "type": "gameFull", "id": g["id"], "rated": bool(g["rated"]),
        "clock": {"initial": g["initial"], "increment": g["increment"]},
        "first": {"username": g["p1name"], "rating": _r(g["p1_rating"]),
                  "bot": bool(g["p1bot"]), "delta": g["p1_delta"]},
        "second": {"username": g["p2name"], "rating": _r(g["p2_rating"]),
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
                    if is_closed(q):
                        return
                    yield "\n"
                    continue
                yield json.dumps(msg) + "\n"
                if msg.get("status") != "active":
                    return
        finally:
            hub.unsubscribe(f"game:{game_id}", q)

    return StreamingResponse(stream(), media_type="application/x-ndjson")


def _moves_of(game_id: str) -> list[str] | None:
    live = manager.get(game_id)
    if live is not None:
        return list(live.moves)
    row = db.one("SELECT moves FROM games WHERE id = ?", (game_id,))
    if row is None:
        return None
    return row["moves"].split(",") if row["moves"] else []


@router.get("/game/{game_id}/views")
async def game_views(game_id: str):
    moves = _moves_of(game_id)
    if moves is None:
        raise HTTPException(404, "no such game")
    return {"moves": ",".join(moves), "views": rules.replay_views(moves)}


@router.get("/game/{game_id}")
async def game_get(game_id: str):
    live = manager.get(game_id)
    if live is not None:
        full = live.full_msg()
        full["view"] = rules.view(live.st)
        full["views"] = rules.replay_views(list(live.moves))
        return full
    full = _db_game_full(game_id)
    if full is None:
        raise HTTPException(404, "no such game")
    full["view"] = full["state"]["view"]
    moves = full["state"]["moves"]
    full["views"] = rules.replay_views(moves.split(",") if moves else [])
    return full


def _live_game(game_id: str):
    game = manager.get(game_id)
    if game is None:
        # A finished game is "over", not "missing" — the contract promises a
        # 400 for acting on it, and bots key their game-loop exit off that.
        if db.one("SELECT 1 FROM games WHERE id = ?", (game_id,)):
            raise HTTPException(400, "the game is over")
        raise HTTPException(404, "no such game")
    return game


@router.post("/game/{game_id}/move/{token}")
async def game_move(game_id: str, token: str, request: Request):
    user = auth.require(request, "play")
    if not limits.moves.take(user["id"]):
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
                    if is_closed(q):
                        # The hub severed this subscriber (queue overflow).
                        # End the stream so the client reconnects and resyncs
                        # instead of listening to keepalives forever.
                        return
                    yield "\n"
                    continue
                yield json.dumps(msg) + "\n"
        finally:
            hub.unsubscribe(f"user:{user['id']}", q)
            presence_dec(user["id"])
            hub.publish("lobby", {"type": "lobbyChanged"})

    return StreamingResponse(stream(), media_type="application/x-ndjson")
