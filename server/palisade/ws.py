"""WebSocket endpoint for web clients.

One socket per browser tab. The client subscribes to channels ("lobby",
"game:<id>"); the server pushes snapshots and updates. All outbound traffic
funnels through a single queue so concurrent hub events never interleave a
send. Unauthenticated sockets may spectate (lobby + game channels) but not
act.

Translation layer: hub messages carry ``type``; the wire uses ``t``. Game
state messages gain the game id and, when it is the receiving user's turn,
the full legal-move list — the client needs no rules code.
"""

from __future__ import annotations

import asyncio
import hashlib
import json

from fastapi import WebSocket, WebSocketDisconnect

from palisade import auth, db, limits
from palisade.events import hub, is_closed, presence_dec, presence_inc
from palisade.games import GameError, Player, manager
from palisade.lobby import check_clock, lobby

# Channels one socket may hold open: lobby + a handful of games is normal use;
# anything past this is a subscription-exhaustion attempt.
MAX_CHANNELS = 32


def _ws_user(ws: WebSocket) -> dict | None:
    sid = ws.cookies.get(auth.SESSION_COOKIE)
    if not sid:
        return None
    row = db.one("SELECT user_id FROM sessions WHERE token = ?", (sid,))
    if row is None:
        return None
    u = db.one("SELECT * FROM users WHERE id = ?", (row["user_id"],))
    return dict(u) if u else None


class Connection:
    def __init__(self, ws: WebSocket, user: dict | None):
        self.ws = ws
        self.user = user
        self.out: asyncio.Queue = asyncio.Queue(maxsize=512)
        self.pumps: dict[str, asyncio.Task] = {}

    async def send_task(self):
        while True:
            msg = await self.out.get()
            await self.ws.send_text(json.dumps(msg))

    def _translate(self, channel: str, msg: dict) -> dict | None:
        t = msg.get("type")
        if channel == "lobby":
            # Any lobby change collapses to a fresh snapshot.
            snap = lobby.snapshot()
            return {"t": "lobby", "seeks": snap["seeks"],
                    "games": snap["games"], "bots": snap["bots"]}
        if channel.startswith("game:") and t == "gameState":
            out = {"t": "state", "game": channel[5:], **{
                k: v for k, v in msg.items() if k != "type"}}
            game = manager.get(channel[5:])
            if (game is not None and self.user is not None
                    and game.status == "active"
                    and game.seat_of(self.user["id"]) == game.mover()):
                out["legal"] = game.legal_tokens()
            return out
        if channel.startswith("user:"):
            return {"t": t, **{k: v for k, v in msg.items() if k != "type"}}
        return None

    async def _pump(self, channel: str, q: asyncio.Queue):
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), 6.0)
                except asyncio.TimeoutError:
                    if is_closed(q):
                        # Severed by the hub for not draining. Close the whole
                        # socket: the client auto-reconnects and replays its
                        # subscriptions, which resyncs every channel at once.
                        await self.ws.close(code=1013)
                        return
                    continue
                out = self._translate(channel, msg)
                if out is not None:
                    await self.out.put(out)
        except Exception:
            pass
        finally:
            hub.unsubscribe(channel, q)

    def subscribe(self, channel: str) -> bool:
        if channel in self.pumps:
            return True
        if len(self.pumps) >= MAX_CHANNELS:
            return False
        q = hub.subscribe(channel)
        self.pumps[channel] = asyncio.get_running_loop().create_task(
            self._pump(channel, q))
        return True

    def unsubscribe(self, channel: str):
        task = self.pumps.pop(channel, None)
        if task:
            task.cancel()

    def close(self):
        for task in self.pumps.values():
            task.cancel()


async def _initial_game_msg(conn: Connection, game_id: str):
    game = manager.get(game_id)
    if game is not None:
        full = game.full_msg()
        msg = {"t": "gameFull", **{k: v for k, v in full.items() if k != "type"}}
        if (conn.user is not None and game.status == "active"
                and game.seat_of(conn.user["id"]) == game.mover()):
            msg["state"] = dict(msg["state"])
            msg["state"]["legal"] = game.legal_tokens()
        await conn.out.put(msg)


async def handle(ws: WebSocket):
    await ws.accept()
    user = _ws_user(ws)
    sid = ws.cookies.get(auth.SESSION_COOKIE)
    conn = Connection(ws, user)
    sender = asyncio.get_running_loop().create_task(conn.send_task())
    if user:
        conn.subscribe(f"user:{user['id']}")
        presence_inc(user["id"])
        hub.publish("lobby", {"type": "lobbyChanged"})

    def player() -> Player:
        fresh = db.one("SELECT * FROM users WHERE id = ?", (user["id"],))
        return Player.from_row(dict(fresh))

    def session_live() -> bool:
        # The cookie is only read at the handshake; re-check before every
        # mutating action so logout actually revokes an open socket.
        return sid is not None and db.one(
            "SELECT 1 FROM sessions WHERE token = ?", (sid,)) is not None

    try:
        while True:
            try:
                data = json.loads(await ws.receive_text())
            except json.JSONDecodeError:
                await conn.out.put({"t": "err", "msg": "not JSON"})
                continue
            t = data.get("t")
            try:
                if t == "sub":
                    ch = str(data.get("ch", ""))
                    ok = True
                    if ch == "lobby":
                        ok = conn.subscribe("lobby")
                        if ok:
                            snap = lobby.snapshot()
                            await conn.out.put({"t": "lobby", **{
                                k: v for k, v in snap.items() if k != "type"}})
                    elif ch.startswith("game:"):
                        ok = conn.subscribe(ch)
                        if ok:
                            await _initial_game_msg(conn, ch[5:])
                    if not ok:
                        await conn.out.put(
                            {"t": "err", "msg": "too many subscriptions"})
                elif t == "unsub":
                    conn.unsubscribe(str(data.get("ch", "")))
                elif user is None:
                    await conn.out.put({"t": "err", "msg": "sign in to play"})
                elif not session_live():
                    await conn.out.put({"t": "err", "msg": "signed out"})
                    await ws.close(code=1008)
                    return
                elif t == "move":
                    if not limits.moves.take(user["id"]):
                        raise GameError("slow down")
                    await manager_action(
                        data, "move", user["id"], str(data.get("move", "")))
                elif t == "resign":
                    await manager_action(data, "resign", user["id"])
                elif t == "abort":
                    await manager_action(data, "abort", user["id"])
                elif t == "seek":
                    initial, increment = check_clock(data.get("clock", {}))
                    lobby.add_seek(player(), bool(data.get("rated", False)),
                                   initial, increment)
                elif t == "seekCancel":
                    lobby.cancel_seek(user["id"])
                elif t == "challenge":
                    dest = db.one("SELECT * FROM users WHERE username = ?",
                                  (str(data.get("user", "")),))
                    if dest is None:
                        raise GameError("no such user")
                    initial, increment = check_clock(data.get("clock", {}))
                    lobby.challenge(player(), Player.from_row(dict(dest)),
                                    bool(data.get("rated", False)),
                                    initial, increment,
                                    str(data.get("color", "random")))
                elif t == "accept":
                    lobby.accept(str(data.get("id", "")), user["id"])
                elif t == "decline":
                    lobby.decline(str(data.get("id", "")), user["id"])
            except GameError as e:
                await conn.out.put({"t": "err", "msg": str(e)})
            except Exception as e:  # HTTPException from lobby helpers
                detail = getattr(e, "detail", None)
                if detail is None:
                    raise
                await conn.out.put({"t": "err", "msg": str(detail)})
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        conn.close()
        if user:
            presence_dec(user["id"])
            hub.publish("lobby", {"type": "lobbyChanged"})


async def manager_action(data: dict, action: str, user_id: int, *args):
    game = manager.get(str(data.get("game", "")))
    if game is None:
        raise GameError("no such live game")
    await getattr(game, action)(user_id, *args)
