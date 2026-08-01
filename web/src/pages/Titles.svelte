<script lang="ts">
  // The reference for the badges that appear beside names. It lives beside the
  // fair-play policy — both are short site documents reached from the footer,
  // and both exist to say what a rating on this site is claiming.
  import Title from '../lib/Title.svelte';
  import { ESTABLISHED_RD, TITLES } from '../lib/titles';
</script>

<article class="doc">
  <header>
    <h1>Titles</h1>
    <p class="lead">
      Four titles, borrowed from FIDE along with the ratings that earn them.
      A title sits immediately before the name, wherever the name appears —
      on the ladder, in the lobby, beside the board.
    </p>
  </header>

  <div class="scroll">
    <table>
      <thead>
        <tr>
          <th class="badge">Title</th>
          <th>Stands for</th>
          <th class="num">Rating</th>
        </tr>
      </thead>
      <tbody>
        {#each TITLES as t (t.code)}
          <tr>
            <td class="badge"><Title title={t.code} /></td>
            <td>{t.name}</td>
            <td class="num">{t.rating}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  <section>
    <h2>What a title costs</h2>
    <p>
      Reaching the number is not quite enough on its own: the rating has to be
      <strong>established</strong> when it gets there. Ratings here are
      Glicko-2, which carries a deviation alongside the number — how sure of
      itself it is — and a new account starts at 1500 with a deviation of 350,
      meaning almost nothing. Established is a deviation of {ESTABLISHED_RD} or
      below, the same bar the site already uses when it stops printing a
      <span class="q">?</span> after a rating.
    </p>
    <p>
      That is our equivalent of FIDE's minimum number of rated games, and it is
      there for the same reason. A rating that has not settled is not yet a
      claim about anybody, and a title is a claim.
    </p>
  </section>

  <section>
    <h2>Held for life</h2>
    <p>
      A title is awarded the first time an established rating reaches the
      threshold, and after that it is yours. It is not reviewed, it does not
      decay, and it is never taken back. FIDE does not revoke a grandmaster's
      title when their rating falls, and neither do we.
    </p>
    <p>
      So a player's rating and their title can disagree — a
      <Title title="GM" /> rated 2380 today is the system working, not a bug.
      Profiles say which rating earned the title, so the two numbers can always
      be read together.
    </p>
  </section>

  <section>
    <h2>FIDE's numbers, not ours</h2>
    <p>
      2500 is 2500. The thresholds are not scaled down to the size of this
      site's population, which is small and new, so they are as hard to reach
      here as they sound. No account held a title when this page was written,
      and the first one will be earned rather than granted.
    </p>
  </section>
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
  p {
    margin: 0 0 14px;
  }
  .lead {
    font-size: 1.08rem;
  }
  section {
    margin-top: 30px;
    padding-top: 20px;
    border-top: 1px solid var(--line);
  }
  /* Narrow screens scroll the table, never the page. */
  .scroll {
    overflow-x: auto;
  }
  table {
    width: 100%;
    max-width: 30rem;
    border-collapse: collapse;
    margin: 22px 0 4px;
    white-space: nowrap;
  }
  th {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-dim);
    text-align: left;
    padding: 0 10px 4px 0;
  }
  td {
    padding: 5px 10px 5px 0;
    border-top: 1px solid var(--line);
  }
  /* The badge column is set at the size it has beside a name, not at heading
     size: the table shows what you will actually see on the ladder. */
  .badge {
    width: 3.4em;
    font-size: 1.05rem;
  }
  th.num,
  td.num {
    text-align: right;
    padding-right: 0;
    font-variant-numeric: tabular-nums;
    font-weight: 600;
  }
  /* The provisional marker, quoted mid-sentence exactly as the ladder prints it. */
  .q {
    color: var(--text-dim);
    font-weight: 600;
  }
  @media (max-width: 600px) {
    h1 {
      font-size: 1.5rem;
    }
  }
</style>
