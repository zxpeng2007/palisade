<script lang="ts">
  import { afterUpdate } from 'svelte';

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

  let box: HTMLElement;
  let revealed = -1;

  $: rows = pairs(moves);

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
                    disabled={!navigable}
                    title="Show the position after {c.token}"
                    on:click={() => onSelect(c.ply)}>{c.token}</button
                  >
                {/if}
              </td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

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
    font: inherit;
    color: var(--text);
    background: none;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 1px 7px;
    cursor: pointer;
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
</style>
