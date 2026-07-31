<script lang="ts">
  import { onMount } from 'svelte';

  // The view object from API.md: {p1, p2, wallsH, wallsV, wallsLeft, turn}
  export let view: any;
  // Full legal token list when it is the viewer's turn, else null (render-only).
  export let legal: string[] | null = null;
  // The viewer's seat; null = spectator.
  export let color: 'first' | 'second' | null = null;
  export let onMove: (token: string) => void = () => {};

  const FILES = 'abcdefghi';
  const CELL = 50;
  const GAP = 10; // wall thickness = the gutter between cells
  const M = 28; // margin for coordinate labels
  const STEP = CELL + GAP;
  const SPAN = 9 * CELL + 8 * GAP;
  const SIZE = SPAN + 2 * M;
  const HIT = 36; // wall-anchor hit square, centered on the cross point
  const GRID = [0, 1, 2, 3, 4, 5, 6, 7, 8];

  let wallMode = false;
  let orientation: 'h' | 'v' = 'h';
  let ghost: string | null = null;

  // The viewer's own side sits at the bottom: flip the RENDERING for the
  // second player. Tokens on the wire never change.
  $: flip = color === 'second';
  $: legalSet = new Set(legal ?? []);
  $: myTurn = legal !== null;
  $: if (legal === null) ghost = null;

  // -- geometry -------------------------------------------------------------
  // file a = column 0 = left edge from Player 1's view; rank 1 = Player 1's
  // home rank, drawn at the bottom unless flipped.

  function squareXY(token: string, flip: boolean) {
    const f = FILES.indexOf(token[0]);
    const r = +token[1] - 1;
    return { x: M + f * STEP, y: M + (flip ? r : 8 - r) * STEP };
  }

  // h<file><rank>: on the edge between <rank> and <rank>+1, spanning files
  // <file> and <file>+1. v<file><rank>: on the edge between <file> and
  // <file>+1, spanning ranks <rank> and <rank>+1.
  function wallGeom(token: string, flip: boolean) {
    const f = FILES.indexOf(token[1]);
    const r = +token[2] - 1; // the lower of the two ranks touching the wall
    const topY = M + (flip ? r : 7 - r) * STEP; // screen-top cell of the pair
    if (token[0] === 'h') {
      return { x: M + f * STEP, y: topY + CELL, w: 2 * CELL + GAP, h: GAP };
    }
    return { x: M + f * STEP + CELL, y: topY, w: GAP, h: 2 * CELL + GAP };
  }

  // Pawn destinations are 2 chars ("e2"); wall tokens are 3 ("hd3"). Testing
  // the first character is not enough: "h4" is a pawn move to file h.
  function isWall(token: string): boolean {
    return token.length === 3;
  }

  // -- derived render lists -------------------------------------------------

  $: pawns = [
    { seat: 1, ...squareXY(view.p1, flip) },
    { seat: 2, ...squareXY(view.p2, flip) },
  ];

  $: walls = [...(view.wallsH ?? []), ...(view.wallsV ?? [])].map(
    (t: string) => ({ token: t, ...wallGeom(t, flip) })
  );

  $: pawnTargets = (legal ?? [])
    .filter((t) => !isWall(t))
    .map((t) => ({ token: t, ...squareXY(t, flip) }));

  $: wallTargets = !wallMode
    ? []
    : (legal ?? [])
        .filter((t) => isWall(t) && t[0] === orientation)
        .map((t) => {
          const f = FILES.indexOf(t[1]);
          const r = +t[2] - 1;
          const topY = M + (flip ? r : 7 - r) * STEP;
          return {
            token: t,
            cx: M + f * STEP + CELL + GAP / 2,
            cy: topY + CELL + GAP / 2,
          };
        });

  $: ghostGeom = ghost !== null ? wallGeom(ghost, flip) : null;

  $: rankLabels = GRID.map((r) => ({
    text: String(r + 1),
    x: M - 12,
    y: M + (flip ? r : 8 - r) * STEP + CELL / 2,
  }));
  const fileLabels = GRID.map((f) => ({
    text: FILES[f],
    x: M + f * STEP + CELL / 2,
    y: M + SPAN + 17,
  }));

  $: bottomSeat = flip ? 2 : 1;
  $: topSeat = flip ? 1 : 2;

  // -- interaction ----------------------------------------------------------

  function clickPawn(token: string) {
    if (legalSet.has(token)) onMove(token);
  }

  function clickWall(token: string) {
    if (!legalSet.has(token)) return;
    ghost = null;
    onMove(token);
  }

  function arm(o: 'h' | 'v') {
    if (wallMode && orientation === o) {
      wallMode = false;
    } else {
      wallMode = true;
      orientation = o;
    }
    ghost = null;
  }

  function onKey(e: KeyboardEvent) {
    const tag = (e.target as HTMLElement | null)?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (legal === null) return;
    if (e.key === 'r' || e.key === 'R') {
      if (!wallMode) wallMode = true;
      else orientation = orientation === 'h' ? 'v' : 'h';
      ghost = null;
    } else if (e.key === 'Escape') {
      wallMode = false;
      ghost = null;
    }
  }

  onMount(() => {
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });
</script>

<div class="wrap">
  <div class="rail">
    <span class="dot p{topSeat}"></span>
    {#each Array(view.wallsLeft[topSeat - 1]) as _}
      <span class="chip"></span>
    {/each}
    <span class="count">{view.wallsLeft[topSeat - 1]} walls</span>
  </div>

  <svg class="board" viewBox="0 0 {SIZE} {SIZE}">
    <rect x="0" y="0" width={SIZE} height={SIZE} rx="8" class="frame" />

    {#each GRID as row}
      {#each GRID as col}
        <rect
          x={M + col * STEP}
          y={M + row * STEP}
          width={CELL}
          height={CELL}
          rx="4"
          class="cell"
        />
      {/each}
    {/each}

    {#each rankLabels as l}
      <text x={l.x} y={l.y} class="coord" text-anchor="middle" dominant-baseline="central">{l.text}</text>
    {/each}
    {#each fileLabels as l}
      <text x={l.x} y={l.y} class="coord" text-anchor="middle">{l.text}</text>
    {/each}

    {#each walls as w (w.token)}
      <rect x={w.x} y={w.y} width={w.w} height={w.h} rx="3" class="wall" />
    {/each}

    {#if ghostGeom}
      <rect
        x={ghostGeom.x}
        y={ghostGeom.y}
        width={ghostGeom.w}
        height={ghostGeom.h}
        rx="3"
        class="wall ghost"
      />
    {/if}

    {#each pawns as p (p.seat)}
      <circle
        cx={p.x + CELL / 2}
        cy={p.y + CELL / 2}
        r={CELL * 0.36}
        class="pawn p{p.seat}"
        class:mover={view.turn === p.seat}
      />
    {/each}

    {#each pawnTargets as t (t.token)}
      <circle cx={t.x + CELL / 2} cy={t.y + CELL / 2} r="9" class="target-dot" />
      <rect
        x={t.x}
        y={t.y}
        width={CELL}
        height={CELL}
        class="hit"
        role="button"
        tabindex="-1"
        on:click={() => clickPawn(t.token)}
      />
    {/each}

    {#each wallTargets as t (t.token)}
      <rect
        x={t.cx - HIT / 2}
        y={t.cy - HIT / 2}
        width={HIT}
        height={HIT}
        class="hit"
        role="button"
        tabindex="-1"
        on:click={() => clickWall(t.token)}
        on:mouseenter={() => (ghost = t.token)}
        on:mouseleave={() => (ghost = ghost === t.token ? null : ghost)}
      />
    {/each}
  </svg>

  <div class="rail">
    <span class="dot p{bottomSeat}"></span>
    {#each Array(view.wallsLeft[bottomSeat - 1]) as _}
      <span class="chip"></span>
    {/each}
    <span class="count">{view.wallsLeft[bottomSeat - 1]} walls</span>
    {#if color !== null}
      <span class="spacer"></span>
      <button
        class:active={wallMode && orientation === 'h'}
        disabled={!myTurn}
        title="Place a horizontal wall (press r)"
        on:click={() => arm('h')}>wall &#9472;</button
      >
      <button
        class:active={wallMode && orientation === 'v'}
        disabled={!myTurn}
        title="Place a vertical wall (press r)"
        on:click={() => arm('v')}>wall &#9474;</button
      >
    {/if}
  </div>
</div>

<style>
  .wrap {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  svg.board {
    display: block;
    width: 100%;
    height: auto;
  }
  .frame {
    fill: var(--surface);
    stroke: var(--line);
  }
  .cell {
    fill: var(--cell);
  }
  .coord {
    fill: var(--text-dim);
    font-size: 12px;
  }
  .wall {
    fill: var(--wall);
  }
  .wall.ghost {
    opacity: 0.5;
    pointer-events: none;
  }
  .pawn {
    stroke: rgba(0, 0, 0, 0.35);
    stroke-width: 1.5;
  }
  .pawn.p1 {
    fill: var(--p1);
  }
  .pawn.p2 {
    fill: var(--p2);
  }
  .pawn.mover {
    stroke: var(--accent);
    stroke-width: 2.5;
  }
  .target-dot {
    fill: var(--accent-soft);
    pointer-events: none;
  }
  .hit {
    fill: transparent;
    cursor: pointer;
    outline: none;
  }
  .rail {
    display: flex;
    align-items: center;
    gap: 3px;
    min-height: 30px;
    padding: 0 4px;
  }
  .rail button {
    padding: 2px 10px;
    font-size: 0.85rem;
  }
  .rail button.active {
    border-color: var(--accent);
    color: var(--accent);
  }
  .chip {
    display: inline-block;
    width: 7px;
    height: 18px;
    border-radius: 2px;
    background: var(--wall);
  }
  .dot {
    display: inline-block;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    margin-right: 6px;
  }
  .dot.p1 {
    background: var(--p1);
  }
  .dot.p2 {
    background: var(--p2);
  }
  .count {
    margin-left: 8px;
    font-size: 0.85rem;
    color: var(--text-dim);
  }
  .spacer {
    flex: 1;
  }
</style>
