<script lang="ts">
  import EvalGraph from './EvalGraph.svelte';
  import ReviewVerdict from './ReviewVerdict.svelte';
  import { accuracyText, type Review, type ReviewMove } from './review';

  // Everything the review shows about a finished game: the control that
  // starts one, the progress of a job in flight, and — once it lands — the
  // graph, the accuracies, and the engine's verdict on the selected move.
  export let review: Review | null = null;
  export let error = ''; // a start that was refused, or polling that gave up
  export let busy = false; // POST in flight
  export let total = 0; // plies in the game
  export let ply = 0;
  export let navigable = true;
  export let first = '';
  export let second = '';
  export let onStart: () => void = () => {};
  export let onSelect: (p: number) => void = () => {};

  $: st = review ? review.status : 'none';
  $: rmoves = (review && review.moves) || ([] as ReviewMove[]);
  $: selected = rmoves.find((m) => m.ply === ply) ?? null;
  $: frac = Math.max(0, Math.min(1, (review && review.progress) || 0));
  // The server reports a fraction; the count comes from the game itself, so
  // "of 55" is the number of moves the reader can see in the list.
  $: at = Math.min(total, Math.round(frac * total));
  $: pct = Math.round(frac * 100);
  $: acc = (review && review.accuracy) || null;
</script>

<section class="review panel">
  <h2>Game review</h2>

  {#if total === 0}
    <p class="dim line">No moves were played, so there is nothing to review.</p>
  {:else if st === 'none'}
    <div class="start">
      <button class="primary" disabled={busy} on:click={onStart}>
        {busy ? 'Starting…' : 'Review this game'}
      </button>
      <span class="dim line">
        The engine replays all {total} moves and grades each one. It takes a
        couple of minutes; the result is stored, so this is asked once.
      </span>
    </div>
  {:else if st === 'pending' || st === 'running'}
    <div class="progress">
      <div class="pline">
        <strong>
          {#if st === 'pending'}
            Queued for analysis
          {:else}
            Analysing move {Math.max(1, at)} of {total}
          {/if}
        </strong>
        <span class="dim">{pct}%</span>
      </div>
      <div
        class="bar"
        role="progressbar"
        aria-label="Review progress"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={pct}
      >
        <div class="fill" style="width: {pct}%"></div>
      </div>
      {#if !error}
        <p class="dim line">
          {#if review && review.engine}<b>{review.engine}</b>{:else}The engine{/if}
          is thinking about one position at a time{#if review && review.sims}, {review.sims}
            simulations each{/if}. You can leave this page — the review carries
          on and is kept.
        </p>
      {/if}
    </div>
  {:else if st === 'failed'}
    <div class="failed">
      <p class="line">
        The review failed{review && review.error ? `: ${review.error}` : '.'}
      </p>
      <button disabled={busy} on:click={onStart}>
        {busy ? 'Retrying…' : 'Try again'}
      </button>
    </div>
  {:else if rmoves.length === 0}
    <p class="dim line">
      The review finished without grading any moves. Nothing to show.
    </p>
  {:else}
    <div class="acc">
      <div class="side">
        <span class="sw" style="background: var(--p1)"></span>
        <span class="name">{first}</span>
        <span class="pct">{acc ? accuracyText(acc.first) : '—'}</span>
        <span class="dim sub">accuracy · above the line</span>
      </div>
      <div class="side">
        <span class="sw" style="background: var(--p2)"></span>
        <span class="name">{second}</span>
        <span class="pct">{acc ? accuracyText(acc.second) : '—'}</span>
        <span class="dim sub">accuracy · below the line</span>
      </div>
    </div>

    <EvalGraph moves={rmoves} {ply} {onSelect} interactive={navigable} />

    <ReviewVerdict
      m={selected}
      {ply}
      {first}
      {second}
      {navigable}
      {onSelect}
    />

    <!-- A review is one engine's opinion at one depth. Naming both is the
         difference between an opinion and a verdict from nowhere. -->
    <p class="dim credit">
      {#if review && review.engine}
        Analysed by <b>{review.engine}</b>{#if review.sims}{' '}at {review.sims}
          simulations a move{/if}. One engine's opinion at that depth, not the
        truth about the game.
      {:else}
        The engine and search depth behind this review were not reported.
      {/if}
    </p>
  {/if}

  {#if error}
    <p class="err line">{error}</p>
    {#if st === 'pending' || st === 'running'}
      <!-- The progress above stopped where the polling did, so it must not be
           the only thing on screen: the way back is a button, not a reload. -->
      <button disabled={busy} on:click={onStart}>
        {busy ? 'Asking…' : 'Check again'}
      </button>
    {/if}
  {/if}
</section>

<style>
  .review {
    margin-top: 12px;
  }
  .line {
    margin: 0;
    font-size: 0.88rem;
  }
  .start {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }
  .start .line {
    flex: 1;
    min-width: 220px;
  }
  .pline {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 10px;
  }
  .bar {
    height: 7px;
    margin: 6px 0 8px;
    background: var(--surface-2);
    border-radius: 4px;
    overflow: hidden;
  }
  .bar .fill {
    height: 100%;
    background: var(--accent);
    transition: width 0.4s linear;
  }
  .failed {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }
  .acc {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px 14px;
    margin-bottom: 10px;
  }
  .side {
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: baseline;
    gap: 0 7px;
    min-width: 0;
  }
  .sw {
    width: 10px;
    height: 10px;
    border-radius: 2px;
    align-self: center;
  }
  .name {
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .pct {
    font-variant-numeric: tabular-nums;
    font-weight: 600;
  }
  .sub {
    grid-column: 2 / -1;
    font-size: 0.72rem;
  }
  .credit {
    margin: 8px 0 0;
    font-size: 0.75rem;
    line-height: 1.4;
  }
  .credit b,
  .progress b {
    color: var(--text);
    font-weight: 600;
  }
  .err {
    color: var(--danger);
    margin-top: 8px;
  }

  /* Two accuracies side by side come to 154px each on a 375px screen, which is
     not enough for a name and a percentage: the name would be ellipsised to
     make room for a number that is only meaningful with the name attached.
     One above the other, both fit whole. */
  @media (max-width: 720px) {
    .review {
      padding: 12px;
    }
    .acc {
      grid-template-columns: 1fr;
      gap: 4px;
      margin-bottom: 12px;
    }
    .side {
      gap: 0 8px;
    }
    .sub {
      font-size: 0.76rem;
    }
    .start .line {
      min-width: 0; /* the sentence wraps rather than forcing the panel wide */
    }
  }
</style>
