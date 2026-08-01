<script lang="ts">
  // The site's fair-play policy, kept in step with FAIR_PLAY.md at the repo
  // root. Written out as markup rather than parsed at runtime: it is one
  // document that changes a few times a year, and it deserves to be typeset
  // rather than dumped.
  const REPO = 'https://github.com/zxpeng2007/murus';
  const UPDATED = '1 August 2026';
</script>

<article class="doc">
  <header>
    <h1>Fair play on murus.net</h1>
    <p class="lead">
      Most game sites have one fair-play rule: no engines. Ours cannot be that
      rule, because engines are welcome here — they have their own accounts,
      their own side of the site, and they play on the same ladder as everyone
      else. That makes the line we draw a different one, and worth stating
      precisely.
    </p>
    <p class="rule">
      The rule is “be what your account says you are”. Engines play as engines.
      People play as people. A rating is a claim about a player, and everything
      below exists to keep that claim true.
    </p>
    <p>Which means the oldest rule still applies, without exception:</p>
    <blockquote class="hard-rule">
      If you are playing on a human account, you may not use an engine, a
      solver, an analysis board, or another player’s advice to choose your
      moves. Not in rated games, not in casual games, not once, not “just to
      check”.
    </blockquote>
    <p>
      That we welcome engines elsewhere on the site changes nothing about this.
      It makes it worse: an engine has
      <a href="#/engines">its own account</a> waiting for it, so running one
      behind a human name is a deliberate choice to misrepresent who is
      playing. This is the one thing here we will remove an account for
      without discussion.
    </p>
  </header>

  <section>
    <h2>For people</h2>

    <h3>Play your own moves</h3>
    <p>
      Every move in every game must be yours — your reading of the position, in
      the time on your clock. No engine, no solver, no analysis board open in
      another tab, no stronger player over your shoulder, no “I only used it in
      the endgame”. Casual games included; they are still someone else’s
      evening.
    </p>

    <h3>Study freely when you are not playing</h3>
    <p>
      Analyse your finished games with any engine, including ours at full
      strength. Read openings, drill endgames, have a bot show you what you
      missed. Learning between games is the point of the site. It is only ever
      a violation <em>while a clock is running</em>.
    </p>

    <h3>One account</h3>
    <p>
      Extra accounts to farm rating, dodge opponents, or restart after a bad run
      all corrupt the ladder. If you want to play an engine you wrote, register
      it as an engine — that is what
      <a href="#/engines">engine accounts</a> are for, and nobody will think
      less of you for it.
    </p>

    <h3>Do not throw games</h3>
    <p>
      Losing deliberately, abandoning a losing position to timeout, or arranging
      results with an opponent are the same offence as boosting, seen from the
      other end.
    </p>
  </section>

  <section>
    <h2>For engine operators</h2>

    <h3>Declare the account</h3>
    <p>
      Run <code>POST /api/bot/upgrade</code> before playing. Engine accounts
      carry a <span class="bot-tag">BOT</span> tag everywhere they appear, and
      opponents are entitled to see it before they sit down. An undeclared
      engine is the one thing on this site that is genuinely dishonest — it is a
      rating claim that is false by construction.
    </p>

    <h3>Do not play a human account with an engine</h3>
    <p>
      The obvious corollary. If your engine plays, it plays under its own name.
    </p>

    <h3>A human may not take over mid-game</h3>
    <p>
      Do not step in to fix a move your engine got wrong, and do not play
      “assisted” games from a bot account. The account is either the engine or
      it is not.
    </p>

    <h3>Run whatever you like, on whatever hardware</h3>
    <p>
      There is no restriction on strength, search depth, opening books, endgame
      tables, hardware, or how much of it you rent. A stronger engine is the
      point. Copying someone else’s weights is between you and their licence,
      not something we police.
    </p>

    <h3>Multiple engines, multiple accounts — encouraged</h3>
    <p>
      One account per engine version, so ratings mean something. Say what the
      engine is in a way people can find; nobody enjoys losing to
      <code>bot_47291</code> with no idea what it was.
    </p>

    <h3>Be a good neighbour</h3>
    <p>
      Do not open dozens of parallel seeks, hammer the matchmaker, or ignore the
      rate limits. If your engine crashes mid-game, resign rather than letting
      the clock run out on someone.
    </p>
  </section>

  <section>
    <h2>Time and disconnection</h2>
    <p>
      Losing on time is a loss, including when your connection drops. Games
      interrupted by a server restart are aborted with no rating change; that is
      our fault, not yours. Games interrupted by <em>your</em> problems are not —
      run your bot somewhere it can stay connected, and see the abort window in
      <a href={REPO + '/blob/main/API.md'} target="_blank" rel="noopener">API.md</a>
      if you need to bail out of a game that has barely started.
    </p>
  </section>

  <section>
    <h2>Enforcement</h2>
    <p>
      Every game is recorded in full — moves, the time spent on each one, and
      the rating history around it. We compare human games against engine
      analysis, and a person playing an engine’s moves at an engine’s tempo
      does not look like a person playing. Accounts we are satisfied are using
      assistance have their games voided, their rating removed, and the account
      closed.
    </p>
    <p>
      We will also say what we cannot do, because a policy that overstates its
      detection is a policy nobody believes. We are a small site. Careful,
      occasional cheating is hard for anyone to catch and we will not pretend
      otherwise. So the rule above is not primarily a dare to our detection —
      it is the condition for this site being worth using at all.
    </p>
    <p>
      And it costs you nothing to keep. If you want to know how a strong engine
      plays, the engine is right there, declared, and will play you for free at
      any time control for as long as you like. Nothing is gained by smuggling
      one onto a human account that you cannot have openly, immediately, and
      with a better opponent.
    </p>
    <p>
      Reports go to an issue on
      <a href={REPO + '/issues'} target="_blank" rel="noopener">the repository</a>
      or straight to the operator. There is no appeals bureaucracy; there is a
      person reading them. And we would far rather answer a question than close
      an account — if you are unsure whether something is allowed (a training
      harness, a shared account for a team engine, an unusual setup), ask
      first. Answers are cheap.
    </p>
  </section>

  <section class="short">
    <h2>In short</h2>
    <ul>
      <li>
        <strong>Human account: your own moves, always. No engine help during a
        game, ever.</strong>
      </li>
      <li>Study with any engine you like between games.</li>
      <li>Engine account: declare it, then let it play. Any engine, any hardware.</li>
      <li>One account per player; one account per engine.</li>
      <li>Do not throw games or arrange results.</li>
      <li>
        An undeclared engine on a human account is the line, and it is not a
        fine one.
      </li>
    </ul>
  </section>

  <p class="updated dim">Last updated {UPDATED}.</p>
</article>

<style>
  .doc {
    max-width: 68ch;
    margin: 8px auto 0;
  }
  h1 {
    font-size: 1.9rem;
    letter-spacing: -0.015em;
    margin-bottom: 0.4em;
  }
  /* The document's own headings, not the site's small uppercase panel labels. */
  .doc h2 {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text);
    text-transform: none;
    letter-spacing: -0.01em;
    margin: 0 0 0.2em;
  }
  .doc h3 {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text);
    margin: 22px 0 0.25em;
  }
  p {
    margin: 0 0 14px;
  }
  .lead {
    font-size: 1.08rem;
  }
  /* The one sentence everything else is derived from. */
  .rule {
    margin: 22px 0;
    padding: 12px 16px;
    background: var(--surface);
    border-left: 3px solid var(--accent);
    border-radius: 0 6px 6px 0;
    font-size: 1.08rem;
    font-weight: 600;
  }
  /* The one prohibition everything else hangs off. It is set apart because a
     reader who takes nothing else from this page must take this. */
  .hard-rule {
    margin: 18px 0;
    padding: 16px 20px;
    background: var(--surface-2, var(--surface));
    border: 1px solid var(--line);
    border-left: 4px solid var(--accent);
    border-radius: 0 8px 8px 0;
    font-size: 1.12rem;
    line-height: 1.6;
    font-weight: 600;
    color: var(--text);
  }
  section {
    margin-top: 38px;
    padding-top: 20px;
    border-top: 1px solid var(--line);
  }
  .short ul {
    margin: 0;
    padding-left: 20px;
  }
  .short li {
    margin-bottom: 4px;
  }
  .updated {
    margin-top: 32px;
    font-size: 0.85rem;
    font-style: italic;
  }
  @media (max-width: 600px) {
    h1 {
      font-size: 1.5rem;
    }
  }
</style>
