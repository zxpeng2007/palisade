<script lang="ts">
  // The site's fair-play policy, kept in step with FAIR_PLAY.md at the repo
  // root. Written out as markup rather than parsed at runtime: it is one
  // document that changes a few times a year, and it deserves to be typeset
  // rather than dumped.
  const REPO = 'https://github.com/zxpeng2007/palisade';
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
      The rule is not “no engines”. It is “be what your account says you are”.
    </p>
    <p>
      A rating is a claim about a player. When a person plays, the rating
      measures that person. When an engine plays, it measures that engine.
      Everything below follows from keeping those two claims true.
    </p>
  </header>

  <section>
    <h2>For people</h2>

    <h3>Play your own moves</h3>
    <p>
      During a game on a human account, do not consult an engine, a solver,
      another site’s analysis board, or a stronger player. This applies to
      rated and casual games alike; casual games are still someone else’s time.
    </p>

    <h3>Between games, use anything you like</h3>
    <p>
      Analyse finished games with any engine, including ours. Read openings.
      Study your losses with a bot at 200,000 simulations. None of that touches
      the claim your rating makes, because nothing is helping you
      <em>while the clock runs</em>.
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
    <h2>What we can and cannot detect</h2>
    <p class="dim">Honesty about enforcement, since the alternative is theatre:</p>
    <p>
      We can see move times, rating trajectories, and how a player’s choices
      compare to a strong engine’s. Those signals catch careless cheating — a
      1200 playing top engine moves at a constant three seconds is not subtle.
      They do not catch careful cheating, and no site’s do. We are a small site
      and we are not going to pretend to a detection apparatus we have not
      built.
    </p>
    <p>
      So this policy leans on something else:
      <strong>there is very little to gain here.</strong> If you want to know how
      a strong engine plays, the engine is right there and will play you for
      free, at any time control, as many games as you like. Rating theft from a
      ladder this size buys nothing. The interesting question on this site was
      never “can I beat this person” — it is “how good can I make my engine”,
      and that question is only worth asking honestly.
    </p>
  </section>

  <section>
    <h2>Enforcement</h2>
    <p>
      Accounts that break these rules may have games voided, ratings reset, or be
      removed. There is no appeals bureaucracy; there is a person reading
      reports. Report a concern by opening an issue on
      <a href={REPO + '/issues'} target="_blank" rel="noopener">the repository</a>,
      or contact the operator directly.
    </p>
    <p>
      We would rather correct a misunderstanding than ban someone. If you are not
      sure whether something is allowed — a training harness, a shared account
      for a team engine, an unusual setup — ask first. Answers are cheap.
    </p>
  </section>

  <section class="short">
    <h2>In short</h2>
    <ul>
      <li>Human account: your moves, during the game. Anything you like between games.</li>
      <li>Engine account: declare it, then let it play. Any engine, any hardware.</li>
      <li>One account per player; one account per engine.</li>
      <li>Do not throw games or arrange results.</li>
      <li>Undeclared engines on human accounts are the line.</li>
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
