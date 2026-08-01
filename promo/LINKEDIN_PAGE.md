# Murus — LinkedIn organization page

Everything needed to create and fill the page, in the order LinkedIn asks for
it. Assets are in `promo/brand/`.

---

## Before you start: the one real blocker

LinkedIn will not let you create a company page without **an email address at
the company's domain**. A Gmail address is refused, and `murus.net` currently
sends mail (via Resend) but cannot receive any.

Fix it free in about five minutes with **Cloudflare Email Routing**:

1. Cloudflare dashboard → `murus.net` → **Email** → **Email Routing** → enable.
2. It offers to add the MX and TXT records automatically — accept.
3. Create a routing rule: `hello@murus.net` → your Gmail address.
4. Confirm the address from the mail Cloudflare sends you.

Then create the page with `hello@murus.net`.

**Check first:** if Resend added an MX record on the root domain for bounce
handling, Email Routing will conflict with it. Resend normally puts its
records on a `send.` subdomain, which is fine — but look at your DNS before
accepting Cloudflare's changes, and do not delete anything Resend owns.

You also need a personal LinkedIn profile that is at least a week old with a
few connections. LinkedIn requires that, and it cannot be worked around.

---

## Page fields

| field | value |
|---|---|
| **Name** | Murus |
| **LinkedIn URL** | `linkedin.com/company/murus` (claim it before someone else does) |
| **Website** | https://murus.net |
| **Industry** | Computer Games — *or* Software Development if you want the technical audience. Computer Games gets you closer to the people who will actually play. |
| **Company size** | 1 employee |
| **Company type** | Self-employed |
| **Logo** | `brand/logo-300.png` (LinkedIn wants 300×300; `logo-400.png` is there if it asks for more) |
| **Cover image** | `brand/cover.png` (1128×191) |
| **Founded** | 2026 |
| **Location** | Wherever you want it attributed — the page needs a country and city, and it will be public. |
| **Custom button** | **Visit website** → `https://murus.net` |
| **Hashtags** (max 3) | `#GameDev` `#MachineLearning` `#OpenSource` |

### Tagline (120 characters max)

> The wall game, for people and engines. One ladder, an open bot API, and all of it open source.

*91 characters.*

Alternative, if you want the game itself to lead:

> Race across the board. Block the way. An open arena where humans and engines share one ladder.

*93 characters.*

---

## About / description (2,000 characters max)

> Murus is an open arena for the wall game: a 9×9 board, two pawns racing for
> the far side, and twenty walls to block the way. It takes a minute to learn
> and is very hard to stop playing.
>
> Most game sites treat engines as a problem to detect. Murus gives them
> accounts, ratings and a documented API, on the same ladder as everyone else.
> A rating is a claim about a player, and the only rule that really matters
> here is that the claim be true: engines play as engines, people play as
> people, and every engine account is labelled so you always know what you are
> sitting across from.
>
> What is here:
>
> • One ladder for humans and engines, with Glicko-2 ratings and titles at
>   FIDE's own thresholds.
> • A bot API modelled on Lichess's — ndjson event and game streams, plain
>   POSTs for moves. Any language, no SDK, about thirty lines to connect.
> • Post-game review: every move graded against an AlphaZero engine, with an
>   accuracy score, an evaluation graph, and the move the engine would have
>   played.
> • Live play in the browser on any device, with full game replay.
>
> The engine that reviews your games and plays as the house bot was trained
> from scratch by self-play — a 3.4-million-parameter policy and value network
> with PUCT search. Both it and the site are open source, weights included.
>
> Built and run by one person. Play a game, or point your own engine at it.
>
> murus.net
> github.com/zxpeng2007/murus

*Roughly 1,450 characters — comfortably inside the limit, with room if you
want to add anything.*

---

## Specialties (up to 20)

```
Board games
Online multiplayer
Game AI
Reinforcement learning
AlphaZero
Monte Carlo tree search
Bot API
Open source
Quoridor
Game engines
Machine learning
Web applications
Real-time systems
Glicko ratings
Chess-like games
```

---

## First post from the page

A page with no posts looks abandoned, and LinkedIn shows follower counts
before content. Post this the moment the page exists.

> **Murus is live.**
>
> An open arena for the wall game — race your pawn to the far side of a 9×9
> board while twenty walls close the paths between you.
>
> What makes it different from every other game site: engines are welcome
> here. They get accounts, ratings, a documented API, and a place on the same
> ladder as everyone else. Not tolerated — invited.
>
> Every finished game can be reviewed move by move against an AlphaZero engine
> trained from scratch for this game, which will also tell you, politely, which
> of your walls was a waste.
>
> Free, no account needed to watch, open source throughout.
>
> **murus.net**
>
> #GameDev #OpenSource #MachineLearning

**Image:** `og.png`, or `game.png` for more product detail.

---

## Follow-up posts

Roughly one a week. Each stands alone, and none needs the previous.

**1 — The blind spot** *(the strongest story you have; image: `game.png`)*

> Our engine lost a ranked game to a single wall move. We assumed it hadn't
> searched deeply enough.
>
> It had. At 600,000 simulations it gave that move 0.01% of its attention and
> ranked it 29th — and more search made it *more* certain it was wrong.
>
> The fault was the value network, mis-scoring the position that move creates
> by 0.76. Self-play could not fix it: every label in that loop comes from the
> same network holding the same misconception, and six generations shared it.
>
> The repair was to mine positions where the raw network and a deep search
> disagree, and train on the search's answer. Held-out error fell from 0.930
> to 0.242. The move that beat us is now the engine's first choice, at 99.6%
> of its search.
>
> The engine and its weights are open: github.com/zxpeng2007/quoridor-alphazero

**2 — Connect an engine** *(image: `engines.png`)*

> Thirty lines and a token is all it takes to put an engine on the Murus
> ladder.
>
> Stream your events, accept a challenge, stream the game, POST a move.
> ndjson and plain HTTP — no SDK, no client library, any language you like.
>
> Bot accounts are labelled everywhere they appear, so opponents always know.
> That is the whole social contract here: be what your account says you are.
>
> The full API is one page: github.com/zxpeng2007/murus/blob/main/API.md

**3 — Game review** *(image: `game.png`)*

> Every finished game on Murus can be reviewed move by move.
>
> Each move graded, an accuracy score for both players, an evaluation graph
> you can scrub through, and the move the engine would have played shown as a
> ghost on the board.
>
> One thing we insist on: the review names the engine and the search depth it
> used. It is one engine's opinion at a given depth, not the truth about your
> game, and an interface that implies otherwise is lying to you.

**4 — Fair play** *(no image needed; this one is about the writing)*

> Most game sites have one fair-play rule: no engines. Ours cannot be that
> rule, because engines are welcome here.
>
> So the rule is different: be what your account says you are. Engines play as
> engines. People play as people. And if you are playing on a human account,
> you may not use an engine to choose your moves — not in rated games, not in
> casual ones, not "just to check".
>
> That we welcome engines does not soften this. It sharpens it: an engine has
> its own account waiting, so running one behind a human name is a deliberate
> choice to misrepresent who is playing.
>
> murus.net/#/fairplay

**5 — Titles** *(image: a screenshot of the titles page)*

> Murus has titles, and they are FIDE's: Candidate Master at 2200, FIDE Master
> at 2300, International Master at 2400, Grandmaster at 2500.
>
> Real thresholds, not scaled to flatter a small site. Nobody holds one. That
> is the point — a title you cannot fail to get is not a title.
>
> They are awarded on an established rating, never on a lucky run, and once
> earned they are held for life. FIDE does not revoke a grandmaster's title
> when their rating slips, and neither do we.

**6 — Built on a €4.50 box** *(image: `phone.png`)*

> The whole arena runs in one Python process on a two-core VPS: FastAPI,
> SQLite, static files. No queue, no cache layer, nothing to babysit.
>
> Server-authoritative clocks and legality, ndjson streams for bots, a
> websocket for browsers, 163 tests. It costs about €4.50 a month.
>
> Boring infrastructure is a feature. Every hour not spent operating it went
> into the game instead.

---

## Assets

| file | size | where it goes |
|---|---|---|
| `brand/logo-300.png` | 300×300 | Page logo |
| `brand/logo-400.png` | 400×400 | Spare, if a larger upload is wanted |
| `brand/cover.png` | 1128×191 | Page cover image |
| `og.png` | 1200×630 | Launch post image; also already the site's link preview |
| `game.png` | 2400×1800 | Posts 1 and 3 |
| `engines.png` | 2400×1800 | Post 2 |
| `intro.png` | 2400×1600 | Explaining the game |
| `phone.png` | 1170×2532 | Post 6 |

---

## After the page exists

1. **Link it from your personal profile** — add Murus under Experience with
   the page attached. That is where most of the early followers come from.
2. **Post from the page, then share to your personal feed.** Page posts alone
   reach almost nobody at zero followers; the personal share is what carries
   it.
3. **Invite connections to follow** — LinkedIn gives page admins a limited
   monthly allowance of invitations. Spend it on people who would actually
   play or write a bot.
4. **Add the page to the site.** A "LinkedIn" link in the murus.net footer
   makes the relationship legible in both directions; say the word and I will
   add it.

## What not to claim

The page will be read by people who can check. Two things to keep straight:

- **The house bot is a deliberately weakened generation** on a two-core VPS,
  around 3,000 simulations a move. It is beatable, and that is on purpose. The
  strong engine is in the repository but needs a GPU.
- **The site is days old with a handful of accounts.** Every number in the
  copy above is real and checkable; none of it implies a userbase that does
  not exist. Keep it that way — "growing community" on a four-account site is
  the one thing that would make the rest look dishonest too.
