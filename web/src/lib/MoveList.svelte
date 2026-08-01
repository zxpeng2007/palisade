<script lang="ts">
  import { afterUpdate } from 'svelte';
  import MoveMark from './MoveMark.svelte';
  import { classLabel } from './review';

  interface Cell {
    ply: number;
    token: string;
  }
  interface Row {
    n: number;
    a: Cell;
    b: Cell | null;
  }

  // Move tokens in ply order. Token i produced the position at ply i + 1 —
  // API.md numbers positions, not moves, so ply 0 is the start and owns no
  // token. Every other ply is exactly one button in this list.
  export let moves: string[] = [];
  // The ply currently on the board, and the newest ply the game has reached.
  export let ply = 0;
  export let latest = 0;
  // False when the per-ply history is unavailable (an older server, or a
  // snapshot that lost a race): the list still reads, it just cannot jump.
  export let navigable = true;
  export let onSelect: (ply: number) => void = () => {};
  // Review classifications by ply, when the game has been reviewed. Empty
  // otherwise, and then the list looks exactly as it always did.
  export let marks: Record<number, string> = {};

  let box: HTMLElement;
  let revealed = -1;
  // The move under the pointer or the keyboard, whichever moved last; the
  // selected move when neither is anywhere.
  let poked: number | null = null;

  $: rows = pairs(moves);
  $: graded = Object.keys(marks).length > 0;
  // `marks` is passed in rather than read from scope so that both of these
  // recompute when a review lands: Svelte tracks what an expression mentions,
  // not what the function it calls goes looking for.
  $: caption = capture(poked ?? ply, marks);

  function capture(
    p: number,
    by: Record<number, string>
  ): { token: string; cls: string } | null {
    const cls = by[p];
    return cls && moves[p - 1] ? { token: moves[p - 1], cls } : null;
  }

  /** What the button says it is, for a pointer and for a screen reader. */
  function moveTitle(c: Cell, by: Record<number, string>): string {
    const where = `Show the position after ${c.token}`;
    return by[c.ply] ? `${c.token} — ${classLabel(by[c.ply])}. ${where}` : where;
  }

  function poke(p: number) {
    poked = p;
  }

  function unpoke(p: number) {
    if (poked === p) poked = null;
  }

  function pairs(ms: string[]): Row[] {
    const out: Row[] = [];
    for (let i = 0; i < ms.length; i += 2) {
      out.push({
        n: i / 2 + 1,
        a: { ply: i + 1, token: ms[i] },
        b: i + 1 < ms.length ? { ply: i + 2, token: ms[i + 1] } : null,
      });
    }
    return out;
  }

  // Keep the selected move in sight, and only ever move the list because the
  // selection moved. That single rule covers every case: clicking a move you
  // can already see scrolls nothing, the arrow keys walk the list along with
  // you, a new move in a game you are watching live scrolls to the bottom —
  // and a viewer parked on an earlier move is left exactly where they were.
  afterUpdate(() => {
    if (!box || ply === revealed) return;
    revealed = ply;
    const el = box.querySelector(`[data-ply="${ply}"]`) as HTMLElement | null;
    if (!el) {
      if (ply === 0) box.scrollTop = 0; // the start position has no token
      return;
    }
    // Scroll the list itself rather than calling scrollIntoView, which would
    // drag the whole page around when the panel is already partly off screen.
    const a = el.getBoundingClientRect();
    const b = box.getBoundingClientRect();
    if (a.top < b.top) box.scrollTop += a.top - b.top;
    else if (a.bottom > b.bottom) box.scrollTop += a.bottom - b.bottom;
  });
</script>

<div class="moves panel" bind:this={box}>
  {#if rows.length === 0}
    <span class="dim">No moves yet.</span>
  {:else}
    <table>
      <tbody>
        {#each rows as r (r.n)}
          <tr>
            <td class="num dim">{r.n}.</td>
            {#each [r.a, r.b] as c}
              <td class="mv">
                {#if c}
                  <button
                    data-ply={c.ply}
                    class:sel={ply === c.ply}
                    aria-current={ply === c.ply ? 'true' : undefined}
                    aria-label={marks[c.ply]
                      ? `${c.token}, ${classLabel(marks[c.ply])}`
                      : undefined}
                    disabled={!navigable}
                    title={moveTitle(c, marks)}
                    on:click={() => onSelect(c.ply)}
                    on:mouseenter={() => poke(c.ply)}
                    on:mouseleave={() => unpoke(c.ply)}
                    on:focus={() => poke(c.ply)}
                    on:blur={() => unpoke(c.ply)}
                  >
                    <span class="tok">{c.token}</span>
                    {#if marks[c.ply]}<MoveMark cls={marks[c.ply]} />{/if}
                  </button>
                {/if}
              </td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<!-- A title attribute answers the pointer but not the keyboard, so the class
     of whichever move is hovered or focused — and of the selected one when
     nothing is — is spelled out here as well. -->
{#if graded}
  <div class="legend">
    {#if caption}
      <MoveMark cls={caption.cls} />
      <span><b>{caption.token}</b> — {classLabel(caption.cls)}</span>
    {/if}
  </div>
{/if}

<div class="nav">
  <button
    disabled={!navigable || ply === 0}
    aria-label="Start position"
    title="Start position (Home)"
    on:click={() => onSelect(0)}>&laquo;</button
  >
  <button
    disabled={!navigable || ply === 0}
    aria-label="Previous move"
    title="Previous move (left arrow)"
    on:click={() => onSelect(ply - 1)}>&lsaquo;</button
  >
  <button
    disabled={!navigable || ply >= latest}
    aria-label="Next move"
    title="Next move (right arrow)"
    on:click={() => onSelect(ply + 1)}>&rsaquo;</button
  >
  <button
    disabled={!navigable || ply >= latest}
    aria-label="Latest position"
    title="Latest position (End)"
    on:click={() => onSelect(latest)}>&raquo;</button
  >
</div>

<style>
  .moves {
    position: relative;
    height: 260px;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 8px 12px;
  }
  .moves table {
    width: 100%;
    border-collapse: collapse;
    font-variant-numeric: tabular-nums;
  }
  .moves td {
    padding: 1px 6px 1px 0;
  }
  .moves td.num {
    width: 2.5em;
  }
  .moves td.mv {
    width: 45%;
  }
  .moves button {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font: inherit;
    color: var(--text);
    background: none;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 1px 7px;
    cursor: pointer;
  }
  .moves button .tok {
    /* The token column stays put whether or not a mark follows it, so a
       reviewed list reads down the same straight edge as an unreviewed one. */
    min-width: 2.2em;
  }
  .moves button:hover:not(:disabled) {
    background: var(--surface-2);
    border-color: var(--line);
  }
  /* Without a history there is nothing to jump to, so the list should read as
     plain text rather than as a row of dead controls. */
  .moves button:disabled {
    opacity: 1;
    cursor: default;
  }
  .moves button.sel {
    background: var(--accent);
    border-color: var(--accent);
    color: #15200a;
    font-weight: 600;
  }
  .moves button:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }
  .legend {
    display: flex;
    align-items: center;
    gap: 6px;
    /* Reserved whether or not anything is in it: the row must not appear and
       disappear under the pointer, shoving the buttons below it around. */
    min-height: 1.5em;
    padding: 0 2px;
    font-size: 0.82rem;
    color: var(--text-dim);
  }
  .legend b {
    color: var(--text);
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }
  .nav {
    display: flex;
    gap: 6px;
  }
  .nav button {
    flex: 1;
    padding: 3px 0;
    font-size: 1.05rem;
    line-height: 1.2;
  }

  /* On a phone this list is the one place in the game with a dozen targets a
     few pixels apart, so the rows open up to a finger's width. The box keeps a
     fixed height at every size — the moves scroll inside it, and a game that
     gains a move must not push the page around. */
  @media (max-width: 720px) {
    .moves {
      height: 340px;
      padding: 6px 8px;
    }
    .moves td {
      padding: 0 4px 0 0;
    }
    .moves button {
      width: 100%;
      min-height: 44px;
      padding: 0 10px;
      font-size: 1.02rem;
    }
    .moves button .tok {
      min-width: 2.6em;
    }
    .legend {
      min-height: 1.9em;
      font-size: 0.9rem;
    }
    /* Stepping is how a phone reads a game: the list is a long way down the
       column, and on a reviewed game the board and the move you are asking
       about are hundreds of pixels apart. So the stepper rides the bottom of
       the screen while there is still page below it, and settles back into
       its own place in the column at the end. */
    .nav {
      position: sticky;
      bottom: 0;
      z-index: 2;
      gap: 8px;
      padding: 6px 0 8px;
      background: var(--bg);
    }
    .nav button {
      font-size: 1.3rem;
    }
  }
</style>
