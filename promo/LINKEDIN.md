# LinkedIn kit — murus.net

Everything here is true and checkable. Numbers come from the training logs,
the measurement scripts in `tools/`, and the live site. Nothing is rounded up.

---

## Post A — the main one (recommended)

> I lost a game of Quoridor to a wall I never saw coming. Then I found out my
> engine hadn't seen it either — and fixing that turned into a whole website.
>
> Over the last few days I trained an AlphaZero engine for Quoridor from
> scratch, and then built murus.net: an open arena where people and engines
> play on the same ladder.
>
> The interesting part wasn't the training. It was one lost game.
>
> The engine had been winning consistently, then dropped a ranked game to a
> single wall move. I assumed it hadn't searched deeply enough. It had — the
> move was there, and the search had rejected it. At 600,000 simulations the
> engine gave that move 0.01% of its attention and ranked it 29th. More search
> made it *more* confident it was wrong.
>
> The value network was mis-scoring the position that move creates by 0.76 —
> and self-play couldn't fix it, because every label in that loop comes from
> the same network holding the same misconception. Six generations shared the
> blind spot.
>
> So I mined positions where the raw network and a deep search disagree,
> labelled them with the search, and trained on those. Held-out value error
> fell from 0.930 to 0.242. The move that beat me is now the engine's first
> choice, at 99.6% of its search.
>
> Then I built somewhere to play it:
>
> → Humans and engines on one ladder, Glicko-2 rated, engines declared
> → A lichess-style bot API — any engine, any language, ~30 lines to connect
> → Post-game review: every move graded, accuracy scored, engine's move shown
> → FIDE titles at FIDE's real thresholds (nobody has one yet, and that's the
>   point)
>
> Play it, or point your own engine at it: murus.net
> Everything is open: github.com/zxpeng2007/murus
>
> #MachineLearning #ReinforcementLearning #AlphaZero #OpenSource #GameDev

**Why this shape:** the hook is a failure, not a feature list. The technical
audience on LinkedIn has read a thousand "I built an X" posts; almost none of
them admit the thing broke. The blind-spot story is the most interesting thing
here and it is genuinely non-obvious — *more search made it worse* is a claim
people will stop scrolling for.

**Image:** `og.png`, or `game.png` if you want the product visible.

---

## Post B — shorter, product-first

> murus.net is live: an open arena for Quoridor where humans and engines play
> on the same ladder.
>
> Most game sites treat bots as the enemy. This one gives them accounts,
> ratings, and a documented API — because "was that a human?" is a question
> worth answering honestly rather than policing.
>
> • Lichess-style bot API — any language, ~30 lines to connect
> • Post-game review: every move graded against an AlphaZero engine I trained
>   from scratch
> • Glicko-2 ratings, FIDE-threshold titles, full game replay
> • Open source, engine weights included
>
> The house bot is running a deliberately weakened generation so it's beatable.
> Come take a rating point off it: murus.net
>
> #OpenSource #GameDev #MachineLearning

---

## Post C — for a hiring audience

> Solo, over the past week: trained an AlphaZero engine from scratch, found and
> fixed a systematic flaw in it, then designed, built, deployed and now operate
> the website it plays on.
>
> murus.net — an open arena for Quoridor where people and engines share a
> ladder.
>
> The engine: 3.4M-parameter policy/value ResNet, PUCT search, trained by
> self-play on a single GPU. Numba-jitted rules core, CUDA graph capture for
> batch-1 inference, ~22k simulations/second.
>
> The site: FastAPI + SQLite + Svelte, server-authoritative clocks and legality,
> Glicko-2, ndjson streams for bots, 163 tests. One process, no queue, no cache
> layer. Runs on a €4.50/month box behind a Cloudflare tunnel.
>
> The part I'd actually put on a CV: a ranked loss traced to a value-network
> blind spot that more search made worse, then repaired by mining
> shallow-vs-deep disagreements. Held-out error 0.930 → 0.242.
>
> Code and weights: github.com/zxpeng2007/murus
>
> #MachineLearning #SoftwareEngineering #ReinforcementLearning

---

## Comment to post under your own thread

Posting a link in a LinkedIn comment rather than the body avoids the reach
penalty on outbound links. If you use Post A without the URL, add this first
comment:

> Play here → https://murus.net
> Engine, weights and site are open → https://github.com/zxpeng2007/murus
> If you want to point a bot at it, the whole API is one page:
> https://github.com/zxpeng2007/murus/blob/main/API.md

---

## Images

| file | size | use |
|---|---|---|
| `og.png` | 1200×630 | The link preview. Already live at murus.net/og.png — LinkedIn will pull it automatically. Also fine as the post image. |
| `game.png` | 2400×1800 | A finished game with review on: graded moves, the verdict, the result. The best single "what is this" image. |
| `lobby.png` | 2400×1800 | The lobby: mode switch, seeks, top games, leaderboard. |
| `engines.png` | 2400×1800 | Engine mode with the API quickstart. Use with Post B or the API comment. |
| `intro.png` | 2400×1600 | The newcomer's introduction — good for showing the game's rules in one frame. |
| `phone.png` | 1170×2532 | Mobile. Use if you post about the drag-to-place walls. |

For a carousel, the order that tells the story: `intro` → `game` → `engines`.

---

## Before you post

1. **Check the preview.** Paste https://murus.net into the LinkedIn post box
   and wait for the card. It should show the board image and the title. If
   LinkedIn has cached an older empty version, the Post Inspector at
   linkedin.com/post-inspector/ forces a refresh.
2. **The house bot is gen-10 on a 2-core VPS**, roughly 3,000 simulations a
   move. It is beatable, which is the point — but do not describe it as the
   strong engine. The strong one (gen-24) is in the repo and would need a GPU
   to run at full strength.
3. **Nobody holds a title.** If someone asks why the titles page is empty,
   that is the honest answer: the thresholds are FIDE's real ones and the pool
   is four accounts old.

## Claims in these posts, and where they come from

| claim | source |
|---|---|
| 0.01% of search, 29th rank at 600k sims | `tools/` measurement, run on the losing position |
| value error 0.76 on that position | raw net +0.354 vs deep search −0.408 |
| held-out 0.930 → 0.242 | `checkpoints/history.json`, `gate_value_mae`, iterations 17–24 |
| 99.6% of search after the repair | re-measured on the same position with gen-24 |
| six generations shared the blind spot | gen-010 through gen-016, ranks 14th–36th |
| 3.4M parameters, ~22k sims/s | model summary; benchmark on the training GPU |
| 163 tests | `python -m pytest -q` |
| €4.50/month | Hetzner CX22 list price |
