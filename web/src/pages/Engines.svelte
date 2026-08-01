<script lang="ts">
  import { onMount } from 'svelte';
  import { subscribe } from '../lib/ws';
  import { account } from '../lib/session';
  import Challenges from '../lib/Challenges.svelte';
  import CodeBlock from '../lib/CodeBlock.svelte';
  import EngineList from '../lib/EngineList.svelte';
  import Leaderboard from '../lib/Leaderboard.svelte';
  import NotationDiagram from '../lib/NotationDiagram.svelte';
  import RatedNote from '../lib/RatedNote.svelte';
  import Seeks from '../lib/Seeks.svelte';
  import TopGames from '../lib/TopGames.svelte';

  const REPO = 'https://github.com/zxpeng2007/murus';

  let seeks: any[] = [];
  let bots: any[] = [];

  $: me = $account ? $account.username : null;

  function onLobby(msg: any) {
    seeks = msg.seeks ?? [];
    bots = msg.bots ?? [];
  }

  // The quickstart is the real flow from API.md, against the live host, in the
  // order a new engine has to run it: token minting needs the session cookie
  // that registration hands out, which is why curl carries a cookie jar.
  const REGISTER = `curl -sX POST https://murus.net/api/register \\
  -H 'Content-Type: application/json' -c bot.cookies \\
  -d '{"username":"my-engine","password":"a long random password"}'`;

  const UPGRADE = `curl -sX POST https://murus.net/api/bot/upgrade -b bot.cookies`;

  const MINT = `curl -sX POST https://murus.net/api/token \\
  -H 'Content-Type: application/json' -b bot.cookies \\
  -d '{"name":"laptop","scopes":["play","bot"]}'
# {"token":"mur_..."}`;

  const BOT = `import json, httpx

SERVER, TOKEN = "https://murus.net", "mur_..."      # the token from step 3
c = httpx.Client(base_url=SERVER, timeout=None,
                 headers={"Authorization": f"Bearer {TOKEN}"})

def lines(path):                    # ndjson: one object per line, blanks are keepalives
    with c.stream("GET", path) as r:
        for line in r.iter_lines():
            if line.strip():
                yield json.loads(line)

def candidates(square, step):       # forward, the jump, then sideways
    f, r = square[0], int(square[1])
    for file, rank in ((f, r + step), (f, r + 2 * step),
                       (chr(ord(f) + 1), r), (chr(ord(f) - 1), r)):
        if "a" <= file <= "i" and 1 <= rank <= 9:
            yield f"{file}{rank}"

def play(game_id, seat):
    me, step = (1, 1) if seat == "first" else (2, -1)   # p1 climbs, p2 descends
    for msg in lines(f"/api/game/stream/{game_id}"):
        st = msg["state"] if msg["type"] == "gameFull" else msg
        if st["status"] != "active":
            return
        if st["view"]["turn"] != me:
            continue
        for token in candidates(st["view"][f"p{me}"], step):
            if c.post(f"/api/game/{game_id}/move/{token}").status_code == 200:
                break               # 400 only means illegal — try the next one

for ev in lines("/api/stream/event"):
    if ev["type"] == "challenge":
        c.post(f"/api/challenge/{ev['challenge']['id']}/accept")
    elif ev["type"] == "gameStart":
        play(ev["game"]["id"], ev["game"]["color"])`;

  const ENDPOINTS = [
    {
      group: 'Accounts',
      rows: [
        ['POST', '/api/register', 'Create an account; sets the session cookie'],
        ['POST', '/api/bot/upgrade', 'Mark the account an engine — only while it has no rated games'],
        ['POST', '/api/token', 'Mint a bearer token with scopes play and bot; session only'],
        ['GET', '/api/token', 'List your tokens (names and scopes, never secrets)'],
        ['GET', '/api/account', 'Your rating, rating deviation and games played'],
        ['GET', '/api/user/{name}', 'Any player’s public profile and recent games'],
      ],
    },
    {
      group: 'Challenges and seeks',
      rows: [
        ['POST', '/api/challenge/{user}', 'Challenge a named player: rated, clock, colour'],
        ['POST', '/api/challenge/{id}/accept', 'Accept; both sides then get gameStart'],
        ['POST', '/api/challenge/{id}/decline', 'Decline one aimed at you'],
        ['POST', '/api/challenge/{id}/cancel', 'Withdraw one you sent'],
        ['POST', '/api/seek', 'Join the anonymous pool at a time control'],
        ['DELETE', '/api/seek', 'Cancel your open seek'],
      ],
    },
    {
      group: 'Playing',
      rows: [
        ['GET', '/api/game/{id}', 'Metadata, move list and the rendered position'],
        ['POST', '/api/game/{id}/move/{token}', 'Play a move; 400 with a reason if it is illegal'],
        ['POST', '/api/game/{id}/resign', 'Resign'],
        ['POST', '/api/game/{id}/abort', 'Abort before ply 2, with no rating change'],
      ],
    },
    {
      group: 'Streams',
      rows: [
        ['GET', '/api/stream/event', 'ndjson: challenges, game starts, game finishes'],
        ['GET', '/api/game/stream/{id}', 'ndjson: the full game, then a line per state change'],
      ],
    },
    {
      group: 'Public',
      rows: [
        ['GET', '/api/leaderboard', 'Ladder; kind=human|bot|all, optional speed'],
        ['GET', '/api/games/top', 'Live and recent games, grouped by speed'],
      ],
    },
  ];

  onMount(() => subscribe('lobby', onLobby));
</script>

<div class="engines">
  <div class="panel hero">
    <h1>Engines are first-class here.</h1>
    <p>
      Everything the browser does, a token does: seek a game, answer a
      challenge, push a move, watch the board change. It is plain HTTP with
      ndjson streams — any language, no SDK, nothing to install on our side.
      Bring an engine, upgrade an account, and it plays on the same ladder as
      everyone else with a <span class="bot-tag">BOT</span> tag next to its name.
    </p>
    <p class="links">
      <a href={REPO + '/blob/main/API.md'} target="_blank" rel="noopener">
        Full API reference →
      </a>
      <a href={REPO + '/tree/main/bots/reference'} target="_blank" rel="noopener">
        Reference bot on GitHub →
      </a>
      <a href="#/fairplay">Fair play for engines →</a>
    </p>
  </div>

  <div class="cols">
    <section class="docs">
      <div class="panel">
        <h2>Quickstart</h2>

        <h3>1 · Register the engine’s own account</h3>
        <p class="dim">
          Usernames are 2–20 characters of <code>[A-Za-z0-9_-]</code>. Keep the
          cookie jar: minting a token needs the session, because a bearer token
          may never mint another.
        </p>
        <CodeBlock label="shell" code={REGISTER} />

        <h3>2 · Upgrade it to a bot account</h3>
        <p class="dim">
          Allowed only while the account has zero rated games, so upgrade before
          you play anything. This call is the declaration itself: it puts the
          <span class="bot-tag">BOT</span> tag beside the name, and an
          undeclared engine is the one thing
          <a href="#/fairplay">fair play</a> calls genuinely dishonest.
        </p>
        <CodeBlock label="shell" code={UPGRADE} />
        <RatedNote action="upgrade" />

        <h3>3 · Mint a token</h3>
        <p class="dim">
          Scope <code>play</code> moves pieces, <code>bot</code> marks it as an
          engine client. The plaintext token is shown once — store it now.
        </p>
        <CodeBlock label="shell" code={MINT} />

        <h3>4 · A bot that actually plays</h3>
        <p class="dim">
          Accepts every challenge and races its pawn at the goal, falling back
          to the jump or a sidestep when the server rejects the move. It plays
          one game at a time; give each <code>play()</code> a thread when you
          want more. Swap the <code>candidates</code> generator for your search
          and you have an engine.
        </p>
        <CodeBlock label="python" code={BOT} />
        <p class="dim">
          Needs <code>httpx</code>. The
          <a href={REPO + '/tree/main/bots/reference'} target="_blank" rel="noopener"
            >reference bot</a
          > drives a full AlphaZero engine through this exact flow.
        </p>
      </div>

      <div class="panel fair">
        <h2>Fair play, in one screen</h2>
        <p>
          The rule here is not “no engines” — engines are the point. It is
          <strong>be what your account says you are</strong>, so that a rating
          measures whatever it claims to measure.
        </p>
        <ul>
          <li>
            <strong>Declare the account.</strong> Run
            <code>/api/bot/upgrade</code> before playing; opponents are entitled
            to see the tag before they sit down.
          </li>
          <li>
            <strong>One account per engine</strong>, and never a human account
            playing engine moves. A human may not take over mid-game either.
          </li>
          <li>
            <strong>Any engine, any hardware.</strong> No limit on strength,
            depth, books, tables or how much of it you rent.
          </li>
          <li>
            <strong>Be a good neighbour.</strong> No seek floods, respect the
            rate limits, and resign rather than letting a crashed bot burn
            someone’s clock.
          </li>
        </ul>
        <p class="more">
          <a href="#/fairplay">The whole policy — including what we can and cannot detect →</a>
        </p>
      </div>

      <div class="panel">
        <h2>Endpoint reference</h2>
        <div class="scroll">
          <table>
            {#each ENDPOINTS as g (g.group)}
              <tbody>
                <tr class="group">
                  <th colspan="3">{g.group}</th>
                </tr>
                {#each g.rows as r (r[1] + r[0])}
                  <tr>
                    <td class="verb">{r[0]}</td>
                    <td class="path">{r[1]}</td>
                    <td class="dim">{r[2]}</td>
                  </tr>
                {/each}
              </tbody>
            {/each}
          </table>
        </div>
        <p class="dim foot">
          Errors are <code>{'{"error": "reason"}'}</code> with a 4xx status.
          Authenticate with <code>Authorization: Bearer mur_…</code>. Moves are
          rate-limited per account (burst 20, about 10/s).
        </p>
      </div>

      <div class="panel">
        <h2>Notation</h2>
        <NotationDiagram />
        <ul class="tokens">
          <li><code>e2</code> — pawn move, written as the destination square</li>
          <li><code>hd3</code> — horizontal wall on the top edge of d3, across d–e</li>
          <li><code>vf6</code> — vertical wall on the right edge of f6, up 6–7</li>
        </ul>
        <p class="dim">
          A game record is the comma-separated token list in ply order:
          <code>e2,e8,e3,he7,vd2</code>. Player 1 starts on e1 and wins by
          reaching rank 9; Player 2 starts on e9 and wins on rank 1. Ten walls
          each, and no wall may seal a player off from their goal entirely.
        </p>
      </div>
    </section>

    <section class="side">
      <Challenges />

      <EngineList {bots} {me} />

      <Seeks
        {seeks}
        {me}
        kind="bot"
        title="Open engine seeks"
        empty="No engine is waiting in the pool right now."
      />

      <TopGames
        kind="bot"
        title="Top engine games"
        empty="No engine games yet. Point a bot at the API and it will show up here."
      />

      <Leaderboard
        kind="bot"
        title="Engine leaderboard"
        empty="No engines have played a rated game yet."
      />
    </section>
  </div>
</div>

<style>
  .engines {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }
  .hero h1 {
    font-size: 1.6rem;
    letter-spacing: -0.01em;
  }
  .hero p {
    margin: 0 0 8px;
    max-width: 62ch;
  }
  .links {
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    font-weight: 600;
  }
  .cols {
    display: grid;
    grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr);
    gap: 20px;
    align-items: start;
  }
  @media (max-width: 900px) {
    .cols {
      grid-template-columns: 1fr;
    }
  }
  section {
    display: flex;
    flex-direction: column;
    gap: 16px;
    min-width: 0;
  }
  h3 {
    font-size: 0.95rem;
    font-weight: 600;
    margin: 18px 0 4px;
  }
  h3:first-of-type {
    margin-top: 6px;
  }
  .docs p {
    margin: 0 0 8px;
    font-size: 0.92rem;
    max-width: 68ch;
  }
  /* Wide reference rows scroll inside the panel, never the page. */
  .scroll {
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
  }
  tr.group th {
    text-align: left;
    padding: 14px 0 3px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-dim);
    border-bottom: 1px solid var(--line);
  }
  tbody:first-of-type tr.group th {
    padding-top: 0;
  }
  td {
    padding: 3px 12px 3px 0;
    vertical-align: baseline;
    white-space: nowrap;
  }
  td.dim {
    white-space: normal;
    padding-right: 0;
  }
  .verb {
    color: var(--accent);
    font-weight: 700;
    font-size: 0.78rem;
    letter-spacing: 0.03em;
  }
  .path {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }
  .foot {
    margin-top: 12px;
  }
  .fair ul {
    margin: 0 0 10px;
    padding-left: 20px;
  }
  .fair li {
    margin-bottom: 5px;
    font-size: 0.92rem;
  }
  .fair .more {
    margin: 0;
    font-weight: 600;
  }
  .tokens {
    margin: 14px 0 10px;
    padding-left: 20px;
  }
  .tokens li {
    margin-bottom: 3px;
    font-size: 0.92rem;
  }
</style>
