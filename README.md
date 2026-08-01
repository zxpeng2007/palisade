# Murus

A self-hostable arena for the wall game: two pawns race across a 9×9 board
while twenty walls close the paths between them. Humans play in the browser;
engines connect through a lichess-style HTTP API and play on the same ladder.

Murus is the server, the web client, and a reference bot. The rules engine
is [quoridor-alphazero](https://github.com/zxpeng2007/quoridor-alphazero) —
the same package whose AlphaZero network plays here as the house bot.

## Why

Engines deserve a place to play where they are first-class citizens: declared
on the ladder, connectable with a token and thirty lines of code, measurable
against humans and each other. Lichess proved the model for chess. Murus
is that model for the wall game.

- **One ladder** — humans and bots share matchmaking and Glicko-2 ratings;
  bot accounts are tagged, never hidden.
- **A real bot API** — ndjson event and game streams plus simple POSTs,
  deliberately shaped like the Lichess Bot API ([API.md](API.md)). Any
  language, no SDK required.
- **Server-authoritative** — legality, clocks, and results are decided
  server-side by a rules engine differential-tested against a reference
  implementation and validated on real recorded games.
- **Boring to run** — one Python process, SQLite, static files. No queue, no
  cache layer, nothing to babysit.

## Run it

```
git clone https://github.com/zxpeng2007/murus
cd murus
pip install -e .[dev]
pip install git+https://github.com/zxpeng2007/quoridor-alphazero.git
uvicorn murus.app:app --port 8000
```

The API is now up. For the browser client:

```
cd web
npm install
npm run build        # server serves web/dist automatically
```

During development: `npm run dev` (Vite proxies `/api` and `/ws` to :8000).

Tests: `python -m pytest`.

## Connect an engine

```
curl -X POST localhost:8000/api/register -H 'content-type: application/json' \
     -d '{"username":"mybot","password":"..."}'
curl -X POST localhost:8000/api/bot/upgrade -b <session>
curl -X POST localhost:8000/api/token -b <session> \
     -d '{"name":"bot","scopes":["play","bot"]}'
```

Then stream `/api/stream/event`, accept challenges, stream your games, and
POST moves. The whole protocol — notation, streams, endpoints — is specified
in [API.md](API.md); a complete minimal bot fits in one screen of Python, and
a full AlphaZero client lives in [bots/reference](bots/reference).

## Notation

Squares `a1`–`i9` (Player 1 starts on `e1`, aiming for rank 9). Pawn moves
name the destination: `e2`. Walls name orientation and anchor: `he3` lies
between ranks 3 and 4 spanning files e–f; `ve3` between files e and f
spanning ranks 3–4. A game is a comma-joined token list — the whole record
format in one line.

## Status

Early. The core loop works end to end — accounts, seeks, challenges, live
games with increment clocks, ratings, spectating, bot streams — and the test
suite exercises it against a real recorded game. Expect rough edges beyond
that loop.

## License

MIT.
