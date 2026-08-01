# Palisade API

Palisade is an arena for the wall game: a 9×9 board, two pawns racing to the
opposite rank, twenty walls that block the way. Humans play in the browser;
engines connect through the HTTP API below, modelled on the Lichess Bot API.
Everything a browser can do, a bot can do with a token.

This document is the contract. The server, the web client, and the reference
bot are all written against it; if behaviour and document disagree, the
document wins and the code is wrong.

- [Game rules and notation](#game-rules-and-notation)
- [Authentication](#authentication)
- [REST endpoints](#rest-endpoints)
- [Event stream](#event-stream)
- [Game stream](#game-stream)
- [WebSocket (web clients)](#websocket-web-clients)
- [Writing a bot](#writing-a-bot)

## Game rules and notation

Two players. Player 1 moves first. Each turn: move your pawn one square
orthogonally, or place one of your 10 walls. Pawns facing each other jump;
if the jump square is blocked, the jumper may step diagonally around. A wall
may never seal either player away from their goal entirely. First pawn to
reach the far rank wins. There are no draws.

### Coordinates

Files `a`–`i` run left to right and ranks `1`–`9` run bottom to top, from
Player 1's point of view. Player 1 starts on `e1` and wins on reaching rank 9;
Player 2 starts on `e9` and wins on reaching rank 1.

### Move tokens

| token | meaning |
|---|---|
| `e2` | pawn move: the destination square (jumps included — destination is enough) |
| `hd3` | horizontal wall: lies on the edge between ranks 3 and 4, spanning files d and e |
| `vd3` | vertical wall: lies on the edge between files d and e, spanning ranks 3 and 4 |

Wall anchors range `a1`–`h8`. A game record is the comma-separated token list
in ply order, e.g. `e2,e8,e3,he7,vd2`.

## Authentication

Two mechanisms, one account model:

- **Session cookie** — `POST /api/register` or `POST /api/login`; used by the
  web client. Cookie is `httponly`.
- **Bearer token** — `Authorization: Bearer pal_...`; used by bots and scripts.
  Create tokens while logged in via `POST /api/token`. The plaintext token is
  shown once. Tokens carry scopes: `play` (join and play games) and `bot`
  (accept challenges automatically-eligible account). An account with
  `bot: true` is displayed with a BOT tag and may only be upgraded while it
  has no rated games.

All endpoints accept either mechanism except token management (`POST` and
`GET /api/token`), which requires a session — a bearer token can never mint
another token. `POST /api/register` and `POST /api/login` are rate-limited
per client address (burst 5); expect 429 under automation.

## REST endpoints

Errors are JSON: `{"error": "human-readable reason"}` with a 4xx status.

### Accounts

| method | path | body | notes |
|---|---|---|---|
| POST | `/api/register` | `{username, password}` | 2–20 chars, `[A-Za-z0-9_-]`; sets session cookie |
| POST | `/api/login` | `{username, password}` | sets session cookie |
| POST | `/api/logout` | — | clears session |
| GET  | `/api/account` | — | `{id, username, bot, rating, rd, games}` |
| POST | `/api/bot/upgrade` | — | marks the account as a bot; only while 0 games played |
| POST | `/api/token` | `{name, scopes: ["play","bot"]}` | → `{token: "pal_..."}` shown once |
| GET  | `/api/token` | — | list of `{name, scopes, created}` (no secrets) |
| GET  | `/api/user/{username}` | — | public profile: rating, counts, recent games |

### Challenges and seeks

| method | path | body | notes |
|---|---|---|---|
| POST | `/api/challenge/{username}` | `{rated, clock:{initial,increment}, color}` | `color`: `"random"` \| `"first"` \| `"second"`; → challenge object |
| POST | `/api/challenge/{id}/accept` | — | → `{game: {...}}`; both players get `gameStart` |
| POST | `/api/challenge/{id}/decline` | — | |
| POST | `/api/challenge/{id}/cancel` | — | challenger withdraws |
| POST | `/api/seek` | `{rated, clock:{initial,increment}}` | joins the lobby pool; match → `gameStart` event |
| DELETE | `/api/seek` | — | cancel your open seek |

`clock.initial` is seconds (60–3600), `clock.increment` seconds (0–60).

### Speed categories

Time controls are bucketed by their estimated duration, `initial + 40 ×
increment` seconds, the same rule Lichess uses:

| speed | estimated duration |
|---|---|
| `bullet` | under 180 s |
| `blitz` | under 480 s |
| `rapid` | under 1500 s |
| `classical` | 1500 s and over |

So 1+0 is bullet, 3+0 and 5+3 are blitz, 15+10 is rapid, 30+0 is classical.
Speed appears on every game and seek object as `"speed"`, and is a filter on
the endpoints below.

### Leaderboards and top games

Both are public and need no authentication.

    GET /api/leaderboard?kind=human|bot|all&speed=<speed>&limit=20

Players ranked by rating, highest first. `kind` splits the ladder into people
and engines (default `all`); `speed` restricts the ranking to players with a
rated game at that speed. Provisional players (RD above 110) are ranked last
regardless of rating, since their numbers mean little.

```json
{"kind":"bot","speed":null,"players":[
  {"rank":1,"username":"PalisadeBot","rating":1712,"provisional":false,"bot":true,"games":38}
]}
```

    GET /api/games/top?kind=human|bot|all&limit=8

Games worth watching, newest-first within each group and ranked by the average
rating of the two players:

```json
{"live":{"blitz":[{"id":"xyz789","first":{...},"second":{...},"rated":true,
                   "ply":24,"speed":"blitz","clock":{"initial":300,"increment":3},
                   "avgRating":1680}],
         "rapid":[]},
 "recent":{"blitz":[{"id":"abc123","first":{...},"second":{...},"rated":true,
                     "speed":"blitz","winner":"first","reason":"mate",
                     "avgRating":1704,"finished":"2026-08-01 12:04:11"}]}}
```

`live` holds games in progress; `recent` holds finished ones. Both are keyed by
speed, and a speed with nothing to show is omitted.

`kind` filters by who is playing, on an *at least one* basis: `bot` returns
games with at least one engine in them, `human` games with at least one
person, `all` everything. A person against an engine therefore appears under
both — it is a game both audiences want to see, and the stricter reading
would leave those games visible nowhere.

### Game review

A finished game can be analysed move by move. Analysis is expensive — a
full game is a couple of minutes of engine time on a small server — so it runs
as a job and the result is stored: the first request starts it, later requests
return the same answer immediately. A game never changes, so a review never
needs recomputing.

    POST /api/game/{id}/review     start one (or return the existing state)
    GET  /api/game/{id}/review     state, and the result when it is ready

```json
{"status":"done","engine":"gen-010","sims":600,
 "accuracy":{"first":82.4,"second":74.1},
 "moves":[
   {"ply":1,"move":"e2","best":"e2","eval":0.06,"loss":0.0,"class":"best"},
   {"ply":2,"move":"e8","best":"hd3","eval":-0.31,"loss":0.19,"class":"mistake"}
 ]}
```

`status` is `pending`, `running`, `done`, or `failed`; while running,
`progress` gives the fraction of positions analysed. `eval` is the position's
value from the first player's point of view, in −1..1, so one graph reads
correctly for both players. `loss` is how much win probability the mover gave
up compared with the engine's choice, in 0..1. `best` is the move the engine
preferred, and equals `move` when the player found it.

`class` is one of `brilliant`, `best`, `excellent`, `good`, `inaccuracy`,
`mistake`, `blunder`. The bands are by win-probability loss: `excellent` up to
0.02, `good` to 0.05, `inaccuracy` to 0.10, `mistake` to 0.20, `blunder`
beyond. `best` means the engine agreed with the move. `brilliant` is reserved
for a move the engine agreed with that its own policy had nearly dismissed
(prior under 2%) and that beats the second choice by more than 0.15 — a move
that had to be found rather than followed.

Review is only available for finished games; asking for one on a live game
returns 400. Analysis reflects the engine and search depth named in the
response, and both are recorded, because a review is a claim about a
particular engine's opinion rather than about the truth.

### Playing

| method | path | notes |
|---|---|---|
| GET  | `/api/game/{id}` | finished or live game: metadata, move list, and `views` |
| GET  | `/api/game/{id}/views` | just the per-ply positions |
| POST | `/api/game/{id}/move/{token}` | play a move; 400 with reason if illegal, not your turn, or the game is over |
| POST | `/api/game/{id}/resign` | |
| POST | `/api/game/{id}/abort` | only before ply 2; no rating change |

Move submissions are rate-limited per account (burst 20, ~10/s sustained);
429 on excess.

## Event stream

    GET /api/stream/event

An ndjson stream (one JSON object per line) of account-level events. Blank
lines are keepalives; ignore them. Events:

```json
{"type":"challenge","challenge":{"id":"abc123","challenger":"donked","destUser":"palisade-bot","rated":true,"clock":{"initial":300,"increment":3},"color":"random"}}
{"type":"challengeCanceled","challenge":{...}}
{"type":"challengeDeclined","challenge":{...}}
{"type":"gameStart","game":{"id":"xyz789","color":"first","opponent":{"username":"donked","rating":1775},"rated":true,"clock":{"initial":300,"increment":3}}}
{"type":"gameFinish","game":{"id":"xyz789","winner":"first","reason":"resign"}}
```

`color` is *your* seat in the game: `"first"` (Player 1) or `"second"`.

## Game stream

    GET /api/game/stream/{gameId}

ndjson. The first line is the full game; subsequent lines are state updates.

```json
{"type":"gameFull","id":"xyz789","rated":true,"clock":{"initial":300,"increment":3},"first":{"username":"donked","rating":1775,"bot":false},"second":{"username":"palisade-bot","rating":1500,"bot":true},"state":{...}}
{"type":"gameState","moves":"e2,e8,e3","view":{"p1":"e3","p2":"e8","wallsH":[],"wallsV":[],"wallsLeft":[10,10],"turn":2},"p1time":297.2,"p2time":301.4,"status":"active","winner":null,"reason":null}
```

`moves` is the comma-joined token list from ply 1. `view` is the rendered
position — pawn squares, placed walls by token, walls in hand, and whose turn
it is (`1`/`2`) — so clients need no rules implementation to draw the board.
Engines will normally replay `moves` instead. `p1time`/`p2time` are seconds
remaining, measured at send time.

`GET /api/game/{id}` additionally returns `views`: one rendered position per
ply, oldest first, so `views[0]` is the starting position and `views[k]` is
the position after `k` moves. A client can therefore show any earlier moment
of a game without implementing the rules — including a spectator who arrived
half way through, who has no other way to know what came before. `views` is
also available on its own at `GET /api/game/{id}/views`, which returns
`{"moves": "...", "views": [...]}`.

Live games include the positions played so far; each subsequent `gameState`
carries the new `view`, so a client appends rather than refetching.
`status`: `active` | `finished` | `aborted`. When `finished`, `winner` is
`"first"`/`"second"` and `reason` is `mate` (goal reached), `resign`,
`timeout`, or `abort`.

Anyone may stream any game (spectating); only the players may post moves.
Streaming a game that is already over yields a single `gameFull` (with
`p1time`/`p2time` `null` — archived games have no clocks) and then closes.
Acting on a finished game returns 400; a game id that never existed, 404.
If the server restarts, games that were in flight are recorded as `aborted`
with no rating change.

A stream may also end without a final state if the server had to sever a
slow consumer. Treat any unexpected close the same way: reconnect and
resync from the first line.

## WebSocket (web clients)

    /ws  (cookie-authenticated; bots should prefer the HTTP streams)

Messages are JSON objects with a `t` field.

Client → server:
`{"t":"sub","ch":"lobby"}` · `{"t":"sub","ch":"game:xyz789"}` · `{"t":"unsub","ch":...}` ·
`{"t":"move","game":"xyz789","move":"e2"}` · `{"t":"resign","game":...}` · `{"t":"abort","game":...}` ·
`{"t":"seek","rated":true,"clock":{"initial":300,"increment":3}}` · `{"t":"seekCancel"}` ·
`{"t":"challenge","user":"palisade-bot","rated":false,"clock":{...},"color":"random"}` ·
`{"t":"accept","id":...}` · `{"t":"decline","id":...}`

Server → client:
`{"t":"lobby","seeks":[...],"games":[...],"bots":[...]}` (snapshot on subscribe, then re-sent on change) ·
`{"t":"gameFull", ...}` (on game subscribe: the same shape as the HTTP
`gameFull`, with `state.legal` included when it is your turn) ·
`{"t":"gameStart","game":{...}}` · `{"t":"challenge",...}` ·
`{"t":"state","game":"xyz789", ...same fields as gameState..., "legal":["e2","he1",...]}` ·
`{"t":"err","msg":"..."}`

`legal` is present only when it is the receiving player's turn — the full
legal token list, so clients need no rules implementation.

Move submissions over the socket share the same per-account rate limit as
the HTTP endpoint. A socket may hold at most 32 channel subscriptions, and
the server may close a socket that stops draining (code 1013) — reconnect
and re-subscribe.

## Writing a bot

1. Register an account, upgrade it: `POST /api/bot/upgrade`.
2. Create a token with scopes `play,bot`.
3. Loop:

```python
import httpx, json

S = "http://localhost:8000"
H = {"Authorization": "Bearer pal_..."}

with httpx.Client(base_url=S, headers=H, timeout=None) as c:
    with c.stream("GET", "/api/stream/event") as events:
        for line in events.iter_lines():
            if not line.strip():
                continue
            ev = json.loads(line)
            if ev["type"] == "challenge":
                c.post(f"/api/challenge/{ev['challenge']['id']}/accept")
            elif ev["type"] == "gameStart":
                play(c, ev["game"]["id"], ev["game"]["color"])

def play(c, game_id, color):
    with c.stream("GET", f"/api/game/stream/{game_id}") as game:
        for line in game.iter_lines():
            if not line.strip():
                continue
            st = json.loads(line)
            state = st["state"] if st["type"] == "gameFull" else st
            if state["status"] != "active":
                return
            moves = state["moves"].split(",") if state["moves"] else []
            my_turn = (len(moves) % 2 == 0) == (color == "first")
            if my_turn:
                c.post(f"/api/game/{game_id}/move/{choose(moves)}")
```

`choose` is your engine. The reference implementation in `bots/reference/`
drives a full AlphaZero engine through exactly this flow.
