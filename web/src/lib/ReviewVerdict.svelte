<script lang="ts">
  import MoveMark from './MoveMark.svelte';
  import {
    BANDS,
    CLASS_NOTE,
    bandPos,
    classColor,
    classLabel,
    evalText,
    pctText,
    type ReviewMove,
  } from './review';

  // The engine's opinion of the move that produced the position on the board.
  export let m: ReviewMove | null = null;
  export let ply = 0;
  export let first = '';
  export let second = '';
  export let navigable = true;
  export let onSelect: (p: number) => void = () => {};

  // Odd plies are the first player's: they move first, from ply 1.
  $: mover = m ? (m.ply % 2 === 1 ? first : second) : '';
  $: agreed = !!m && m.best === m.move;
  // Which band to light up: the one the server's own class names, not one
  // re-derived from the loss here. `best` and `brilliant` are agreements
  // rather than bands, so for those the ruler shows only where the pin lands.
  $: here = m ? BANDS.findIndex((b) => b.cls === m.class) : -1;

  function lead(v: number): string {
    if (!Number.isFinite(v) || Math.abs(v) < 0.02) return 'level';
    return `${v > 0 ? first : second} ahead`;
  }
</script>

<div class="verdict">
  {#if !m}
    <p class="dim empty">
      {#if ply === 0}
        The start position. Pick a move — on the graph or in the list — to see
        what the engine made of it.
      {:else}
        This move was not part of the review.
      {/if}
    </p>
  {:else}
    <div class="head">
      <span class="dim">Move {m.ply} · {mover}</span>
      <span class="cls" style="color: {classColor(m.class)}">
        <MoveMark cls={m.class} size={13} />
        {classLabel(m.class)}
      </span>
    </div>

    {#if agreed}
      <div class="pair one">
        <span class="lbl dim">played</span>
        <b class="tok" style="color: {classColor(m.class)}">{m.move}</b>
        <span class="dim note">{CLASS_NOTE[m.class] ?? 'the engine agreed'}</span>
      </div>
    {:else}
      <!-- Two tokens side by side say almost nothing; stacked, aligned, and
           labelled, the substitution is the thing you see first. -->
      <div class="pair">
        <span class="lbl dim">played</span>
        <b class="tok" style="color: {classColor(m.class)}">{m.move}</b>
        <span class="dim note">{CLASS_NOTE[m.class] ?? ''}</span>

        <span class="lbl dim">engine</span>
        <b class="tok pref">{m.best}</b>
        <span class="dim note">
          would have kept <b class="cost">{pctText(m.loss)}</b> more win probability
        </span>
      </div>
    {/if}

    <div class="ruler">
      <div class="bands">
        {#each BANDS as b, i}
          <span
            class="band"
            class:on={i === here}
            style="background: {classColor(b.cls)}"
          ></span>
        {/each}
        <span class="pin" style="left: {bandPos(m.loss) * 100}%"></span>
      </div>
      <div class="names">
        {#each BANDS as b, i}
          <span
            class="bname"
            class:on={i === here}
            style="color: {i === here ? classColor(b.cls) : ''}"
          >
            {b.cls}
          </span>
        {/each}
      </div>
      <div class="scale dim">
        win probability lost — {pctText(m.loss)}, on the bands of the review
      </div>
    </div>

    <div class="foot dim">
      <span>Position after: <b>{evalText(m.eval)}</b> ({lead(m.eval)})</span>
      {#if navigable && m.ply > 0}
        <button class="link" on:click={() => onSelect(m.ply - 1)}>
          see the position before
        </button>
      {/if}
    </div>
  {/if}
</div>

<style>
  .verdict {
    border-top: 1px solid var(--line);
    padding-top: 10px;
  }
  .empty {
    margin: 0;
    font-size: 0.9rem;
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    font-size: 0.9rem;
  }
  .cls {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-weight: 600;
  }
  .pair {
    display: grid;
    grid-template-columns: auto auto 1fr;
    align-items: baseline;
    gap: 2px 8px;
    margin: 6px 0 10px;
  }
  .lbl {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .tok {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 1.05rem;
  }
  .tok.pref {
    color: var(--accent);
  }
  .note {
    font-size: 0.85rem;
    min-width: 0;
  }
  b.cost {
    color: var(--text);
  }
  .ruler {
    margin: 8px 0 6px;
  }
  .bands {
    position: relative;
    display: flex;
    gap: 2px;
    height: 8px;
  }
  .band {
    flex: 1;
    border-radius: 2px;
    opacity: 0.3;
  }
  .band.on {
    opacity: 0.85;
  }
  .pin {
    position: absolute;
    top: -3px;
    bottom: -3px;
    width: 2px;
    margin-left: -1px;
    background: var(--text);
    border-radius: 1px;
  }
  .names {
    display: flex;
    gap: 2px;
    margin-top: 2px;
  }
  .bname {
    flex: 1;
    text-align: center;
    font-size: 0.62rem;
    line-height: 1.3;
    color: var(--text-dim);
    overflow: hidden;
    white-space: nowrap;
  }
  .bname.on {
    font-weight: 700;
  }
  .scale {
    font-size: 0.72rem;
    margin-top: 2px;
  }
  .foot {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
    font-size: 0.85rem;
  }
  .foot b {
    color: var(--text);
    font-variant-numeric: tabular-nums;
  }
  button.link {
    background: none;
    border: none;
    padding: 0;
    color: var(--accent);
    font-size: 0.85rem;
    text-decoration: underline;
  }

  @media (max-width: 720px) {
    /* The played move and the engine's move stack, one label per line, rather
       than sharing a row with a sentence that would wrap to three lines of
       its own beside them. */
    .pair {
      grid-template-columns: auto 1fr;
      gap: 4px 8px;
    }
    .note {
      grid-column: 1 / -1;
      margin-bottom: 4px;
    }
    .tok {
      font-size: 1.15rem;
    }
    /* Five band names across 309px is 60px each, which 0.62rem was chosen to
       fit; the reading distance is shorter on a phone but the type should not
       be this small, so the row loses the labels it cannot show and keeps the
       pin, the lit band, and the sentence under it that names both. */
    .names {
      display: none;
    }
    .bands {
      height: 12px;
    }
    .scale {
      font-size: 0.78rem;
      margin-top: 6px;
    }
    .foot {
      gap: 4px 8px;
    }
    /* On its own line at the end of the panel, so it can have the height of a
       real control without disturbing a sentence. */
    button.link {
      padding: 12px 0;
      font-size: 0.9rem;
    }
  }
</style>
