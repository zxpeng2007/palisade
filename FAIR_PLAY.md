# Fair play on murus.net

Most game sites have one fair-play rule: no engines. Ours cannot be that rule,
because engines are welcome here — they have their own accounts, their own
side of the site, and they play on the same ladder as everyone else. That
makes the line we draw a different one, and worth stating precisely.

**The rule is "be what your account says you are".** Engines play as engines.
People play as people. A rating is a claim about a player, and everything
below exists to keep that claim true.

Which means the oldest rule still applies, without exception:

> **If you are playing on a human account, you may not use an engine, a
> solver, an analysis board, or another player's advice to choose your moves.
> Not in rated games, not in casual games, not once, not "just to check".**

That we welcome engines elsewhere on the site changes nothing about this. It
makes it worse: an engine has its own account waiting for it, so running one
behind a human name is a deliberate choice to misrepresent who is playing.
This is the one thing here we will remove an account for without discussion.

## For people

**Play your own moves.** Every move in every game must be yours — your
reading of the position, in the time on your clock. No engine, no solver, no
analysis board open in another tab, no stronger player over your shoulder,
no "I only used it in the endgame". Casual games included; they are still
someone else's evening.

**Study freely when you are not playing.** Analyse your finished games with
any engine, including ours at full strength. Read openings, drill endgames,
have a bot show you what you missed. Learning between games is the point of
the site. It is only ever a violation while a clock is running.

**One account.** Extra accounts to farm rating, dodge opponents, or restart
after a bad run all corrupt the ladder. If you want to play an engine you
wrote, register it as an engine — that is what engine accounts are for, and
nobody will think less of you for it.

**Do not throw games.** Losing deliberately, abandoning a losing position to
timeout, or arranging results with an opponent are the same offence as
boosting, seen from the other end.

## For engine operators

**Declare the account.** Run `POST /api/bot/upgrade` before playing. Engine
accounts carry a BOT tag everywhere they appear, and opponents are entitled to
see it before they sit down. An undeclared engine is the one thing on this
site that is genuinely dishonest — it is a rating claim that is false by
construction.

**Do not play a human account with an engine.** The obvious corollary. If your
engine plays, it plays under its own name.

**A human may not take over mid-game.** Do not step in to fix a move your
engine got wrong, and do not play "assisted" games from a bot account. The
account is either the engine or it is not.

**Run whatever you like, on whatever hardware.** There is no restriction on
strength, search depth, opening books, endgame tables, hardware, or how much
of it you rent. A stronger engine is the point. Copying someone else's weights
is between you and their licence, not something we police.

**Multiple engines, multiple accounts** — encouraged. One account per engine
version, so ratings mean something. Say what the engine is in a way people can
find; nobody enjoys losing to `bot_47291` with no idea what it was.

**Be a good neighbour.** Do not open dozens of parallel seeks, hammer the
matchmaker, or ignore the rate limits. If your engine crashes mid-game,
resign rather than letting the clock run out on someone.

## Time and disconnection

Losing on time is a loss, including when your connection drops. Games
interrupted by a server restart are aborted with no rating change; that is our
fault, not yours. Games interrupted by *your* problems are not — run your bot
somewhere it can stay connected, and see the abort window in
[API.md](API.md) if you need to bail out of a game that has barely started.

## Enforcement

Every game is recorded in full — moves, the time spent on each one, and the
rating history around it. We compare human games against engine analysis, and
a person playing an engine's moves at an engine's tempo does not look like a
person playing. Accounts we are satisfied are using assistance have their
games voided, their rating removed, and the account closed.

We will also say what we cannot do, because a policy that overstates its
detection is a policy nobody believes. We are a small site. Careful, occasional
cheating is hard for anyone to catch and we will not pretend otherwise. So the
rule above is not primarily a dare to our detection — it is the condition for
this site being worth using at all.

And it costs you nothing to keep. If you want to know how a strong engine
plays, the engine is right there, declared, and will play you for free at any
time control for as long as you like. Nothing is gained by smuggling one onto
a human account that you cannot have openly, immediately, and with a better
opponent.

Reports go to an issue on
[the repository](https://github.com/zxpeng2007/palisade) or straight to the
operator. There is no appeals bureaucracy; there is a person reading them.
And we would far rather answer a question than close an account — if you are
unsure whether something is allowed (a training harness, a shared account for
a team engine, an unusual setup), ask first. Answers are cheap.

## In short

- **Human account: your own moves, always. No engine help during a game, ever.**
- Study with any engine you like between games.
- Engine account: declare it, then let it play. Any engine, any hardware.
- One account per player; one account per engine.
- Do not throw games or arrange results.
- An undeclared engine on a human account is the line, and it is not a fine one.

*Last updated 1 August 2026.*
