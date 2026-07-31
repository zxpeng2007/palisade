# Reference bot

The palisade equivalent of lichess-bot: a single-file client (`bot.py`) that
connects an AlphaZero engine to a Palisade server through the public HTTP API
only — no server internals, no rules re-implementation. It also runs as the
house bot.

## Setup

Requires Python 3.11+ and a checkpoint trained by the engine repo.

```sh
# 1. The palisade package (used only for move notation).
pip install -e /path/to/palisade

# 2. The rules engine + network (the `quoridor` package).
pip install git+https://github.com/zxpeng2007/quoridor-alphazero.git
#    ...or, for development, an editable install of a local clone:
# pip install -e /path/to/quoridor-alphazero

# 3. PyTorch — pick the build matching your CUDA from pytorch.org, e.g.:
pip install torch --index-url https://download.pytorch.org/whl/cu121

# 4. The HTTP client.
pip install httpx
```

The bot runs fine on CPU (`--device cpu`), just with fewer simulations per
second; the clock-aware time budgeting adapts automatically.

## Creating a bot account and token

Everything goes through the API (see `API.md` at the repo root). With the
server on `http://localhost:8000`:

```sh
# Register (sets a session cookie; keep it in a jar for the next two calls).
curl -c jar.txt -H 'Content-Type: application/json' \
     -d '{"username":"house-bot","password":"a-long-password"}' \
     http://localhost:8000/api/register

# Flag the account as a bot. Only possible while it has 0 rated games.
curl -b jar.txt -X POST http://localhost:8000/api/bot/upgrade

# Create a token with the play and bot scopes. The plaintext is shown ONCE.
curl -b jar.txt -H 'Content-Type: application/json' \
     -d '{"name":"reference-bot","scopes":["play","bot"]}' \
     http://localhost:8000/api/token
# -> {"token":"pal_..."}

rm jar.txt
```

## Running

```sh
export PALISADE_TOKEN=pal_...        # or pass --token
python bot.py --server http://localhost:8000 \
              --checkpoint /path/to/checkpoints/best.pt \
              --seek 300+3
```

What it does:

- verifies the token against `GET /api/account` (and warns if the account is
  not flagged bot);
- streams `/api/stream/event`, reconnecting with backoff, and accepts or
  declines challenges per `--accept` (`all` | `casual` | `rated` | `none`);
- plays one game at a time: on `gameStart` it follows
  `/api/game/stream/{id}`, rebuilds the position by replaying the server's
  move list through the rules engine, searches, and POSTs the move;
- budgets think time as `min(--think, remaining/20)` seconds, converted to a
  simulation count using a running estimate of search throughput;
- with `--seek INITIAL+INCREMENT` given, keeps one seek open whenever idle
  and re-seeks after every game (rated by default; suffix `:casual` to seek
  casual, repeat the flag to rotate time controls).

Useful knobs: `--think` (target seconds per move, default 3), `--max-sims`
(simulation ceiling, default 200000 — this sizes the preallocated search
tree, ~0.5 GB), `--device auto|cuda|cpu`.

## Writing your own bot (any language)

Nothing here is Python-specific. The whole protocol is plain HTTP plus
newline-delimited JSON, documented in `API.md` at the repo root:

1. Register an account, `POST /api/bot/upgrade`, create a token with scopes
   `play,bot`.
2. Stream `GET /api/stream/event` (ndjson; blank lines are keepalives).
   Accept challenges with `POST /api/challenge/{id}/accept`.
3. On `gameStart`, stream `GET /api/game/stream/{id}`. Each state carries the
   full move list and both clocks. When it is your turn — you are `first` if
   your `color` in the `gameStart` event was `first`, and it is your move
   when the parity of the move count matches your seat — pick a move and
   `POST /api/game/{id}/move/{token}`.
4. Tokens are trivial: pawn moves by destination square (`e2`), walls by
   orientation + anchor (`hd3`, `vd3`). Illegal moves get a 400 with a
   reason, so a bot can even learn the rules by trial if it must.

`bot.py` is a complete, commented example of this flow, including the
awkward parts: stream reconnection, clock management, and declining
challenges while busy.
