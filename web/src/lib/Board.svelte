<script lang="ts">
  import { onMount } from 'svelte';
  import MoveMark from './MoveMark.svelte';
  import { classColor, classLabel } from './review';
  import {
    CELL,
    FILES,
    GAP,
    M,
    SIZE,
    SPAN,
    STEP,
    crossToken,
    isWall,
    nearestCross,
    squareXY,
    wallGeom,
    type CrossHit,
  } from './geometry';

  // The view object from API.md: {p1, p2, wallsH, wallsV, wallsLeft, turn}
  export let view: any;
  // Full legal token list when it is the viewer's turn, else null (render-only).
  export let legal: string[] | null = null;
  // The viewer's seat; null = spectator.
  export let color: 'first' | 'second' | null = null;
  export let onMove: (token: string) => void = () => {};

  // Review annotations for the position on screen. `played` is the token that
  // produced it and `mark` its classification; `best` is the engine's choice,
  // passed only when it differs from what was played — a ghost drawn on top of
  // the move that was played would imply a correction that does not exist.
  export let played: string | null = null;
  export let mark: string | null = null;
  export let best: string | null = null;

  const GRID = [0, 1, 2, 3, 4, 5, 6, 7, 8];
  const LONG = 2 * CELL + GAP; // a wall's length
  const BADGE = 13; // classification badge radius
  const GLYPH = 17;

  // A wall drawn under the fingertip is hidden exactly when it needs to be
  // seen, so on touch it rides above the contact point — far enough to clear a
  // finger pad, which at a phone's board scale is a little over half a square.
  const LIFT = 56;
  // The lift fades in with the gesture instead of applying from the first
  // instant: a plain tap must still place where it landed, which is the
  // placement every existing player already knows.
  const SLOP = 10; // movement under this is a tap, not a drag
  const RAMP = 45; // distance over which the lift comes fully in

  // The viewer's own side sits at the bottom: flip the RENDERING for the
  // second player. Tokens on the wire never change.
  $: flip = color === 'second';
  $: legalSet = new Set(legal ?? []);
  $: myTurn = legal !== null;
  $: canWall = (legal ?? []).some(isWall);

  // -- derived render lists -------------------------------------------------
  // Geometry lives in ./geometry so the notation diagram in engine mode is
  // drawn by the same code as the board.

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

  // -- review annotations ---------------------------------------------------

  /** Where a classification badge sits: the corner of the thing that moved —
   *  the destination square for a pawn, the far end of the wall for a wall. */
  function badgeAt(token: string, fl: boolean): { x: number; y: number } {
    if (!isWall(token)) {
      const s = squareXY(token, fl);
      return { x: s.x + CELL, y: s.y };
    }
    const g = wallGeom(token, fl);
    return token[0] === 'h'
      ? { x: g.x + g.w, y: g.y + g.h / 2 }
      : { x: g.x + g.w / 2, y: g.y };
  }

  $: badge = mark && played ? badgeAt(played, flip) : null;
  $: bestPawn = best && !isWall(best) ? squareXY(best, flip) : null;
  $: bestWall = best && isWall(best) ? wallGeom(best, flip) : null;

  // -- wall placement: drag, float, release ---------------------------------
  // One implementation on Pointer Events serves touch, mouse and stylus. A
  // wall is taken from the reserve or straight off the board, follows the
  // pointer, and is placed by releasing over a legal slot.

  let svgEl: SVGSVGElement;
  let dragId: number | null = null; // pointer holding a wall; null = none
  let touchDrag = false;
  let start = { x: 0, y: 0 }; // where the gesture began, board units
  let aim: { x: number; y: number } | null = null;
  // An explicit rotation outranks the gesture. `forcedAt` is the cross it was
  // made at, or null when it was armed with nothing in hand and so applies
  // wherever the next wall lands.
  let forced: 'h' | 'v' | null = null;
  let forcedAt: string | null = null;

  // The turn can end in the middle of a gesture: an opponent's move lands, or
  // the viewer scrubs back and the board becomes a picture. Everything the
  // gesture draws is gated on `canWall` rather than cleared afterwards, because
  // a reactive statement that clears `aim` runs too late to undo the values
  // already derived from it in the same update — the wall would hang there over
  // a board that can no longer take it.
  $: cross = canWall && aim ? nearestCross(aim.x, aim.y, flip) : null;
  $: orient = pick(cross, forced, legalSet);
  $: candidate = cross ? crossToken(cross, orient) : null;
  $: candOK = candidate !== null && legalSet.has(candidate);
  $: snap = candidate ? wallGeom(candidate, flip) : null;
  $: hand = canWall && aim && dragId !== null ? handGeom(aim, orient) : null;

  // ...and the gesture is dropped as well, so no listener outlives the turn it
  // belongs to.
  $: if (!canWall) release();

  /** Which of a cross's two walls the gesture is asking for.
   *
   *  Displacement decides: further from the cross along x than along y means
   *  the wall lies along x. With no rotation in force, a cross offering
   *  exactly one legal wall gives that one — the other is refused wherever the
   *  finger sits, and showing the refusal instead of the wall the player can
   *  actually have helps nobody. */
  function pick(
    c: CrossHit | null,
    f: 'h' | 'v' | null,
    ok: Set<string>
  ): 'h' | 'v' {
    if (f !== null) return f;
    if (c === null) return 'h';
    const gesture: 'h' | 'v' = Math.abs(c.dy) > Math.abs(c.dx) ? 'v' : 'h';
    const other: 'h' | 'v' = gesture === 'h' ? 'v' : 'h';
    if (!ok.has(crossToken(c, gesture)) && ok.has(crossToken(c, other))) {
      return other;
    }
    return gesture;
  }

  function handGeom(a: { x: number; y: number }, o: 'h' | 'v') {
    const w = o === 'h' ? LONG : GAP;
    const h = o === 'h' ? GAP : LONG;
    return { x: a.x - w / 2, y: a.y - h / 2, w, h };
  }

  /** Client coordinates into the board's own units. */
  function boardPoint(e: PointerEvent): { x: number; y: number } | null {
    if (!svgEl) return null;
    const m = svgEl.getScreenCTM();
    if (!m) return null;
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse());
    return { x: p.x, y: p.y };
  }

  /** The point the wall is aimed at — the wall itself on touch, since the
   *  player aims with what they can see rather than with a hidden fingertip. */
  function aimFor(p: { x: number; y: number }): { x: number; y: number } {
    if (!touchDrag) return p;
    const moved = Math.hypot(p.x - start.x, p.y - start.y);
    const t = Math.min(1, Math.max(0, (moved - SLOP) / RAMP));
    return { x: p.x, y: p.y - LIFT * t };
  }

  /** The legal wall a release at this point would place, or null. Recomputed
   *  from the event rather than read off the drawn preview: on touch the
   *  release can carry a position the last pointermove never reported. */
  function targetAt(p: { x: number; y: number }): string | null {
    const c = nearestCross(p.x, p.y, flip);
    if (!c) return null;
    const t = crossToken(c, pick(c, forced, legalSet));
    return legalSet.has(t) ? t : null;
  }

  function grab(e: PointerEvent) {
    if (!canWall) return;
    // A second finger while a wall is in hand rotates it: the one-handed
    // answer to a cross where the gesture is genuinely ambiguous.
    if (dragId !== null) {
      if (e.pointerId !== dragId) {
        e.preventDefault();
        rotate();
      }
      return;
    }
    const p = boardPoint(e);
    if (!p) return;
    e.preventDefault(); // no text selection, no synthetic mouse events
    dragId = e.pointerId;
    touchDrag = e.pointerType === 'touch';
    start = p;
    aim = aimFor(p);
    const el = e.currentTarget as Element;
    try {
      el.setPointerCapture(e.pointerId);
    } catch {
      // A pointer that vanished between dispatch and here: the window
      // listeners below still end the drag cleanly.
    }
    window.addEventListener('pointermove', onDragMove);
    window.addEventListener('pointerup', onDragUp);
    window.addEventListener('pointercancel', onDragCancel);
  }

  function onDragMove(e: PointerEvent) {
    if (e.pointerId !== dragId) return;
    const p = boardPoint(e);
    if (!p) return;
    aim = aimFor(p);
    // A rotation speaks for the cross it was made at. Move on and the gesture
    // is meaningful again, so hand the decision back to it.
    if (forcedAt !== null) {
      const c = nearestCross(aim.x, aim.y, flip);
      if (c === null || c.key !== forcedAt) {
        forced = null;
        forcedAt = null;
      }
    }
  }

  function onDragUp(e: PointerEvent) {
    if (e.pointerId !== dragId) return;
    const p = boardPoint(e);
    const token = p ? targetAt(aimFor(p)) : null;
    release();
    // Released anywhere but a legal slot, the wall goes back to the reserve
    // and nothing is placed.
    if (token !== null) {
      forced = null;
      forcedAt = null;
      onMove(token);
    }
  }

  function onDragCancel(e: PointerEvent) {
    if (e.pointerId !== dragId) return;
    release();
  }

  /** Put down whatever is in hand, placing nothing. Safe when nothing is. */
  function release() {
    dragId = null;
    aim = null;
    window.removeEventListener('pointermove', onDragMove);
    window.removeEventListener('pointerup', onDragUp);
    window.removeEventListener('pointercancel', onDragCancel);
  }

  function rotate() {
    forced = orient === 'h' ? 'v' : 'h';
    forcedAt = cross ? cross.key : null;
  }

  // A mouse has a position without pressing, so show it what a click would
  // place. Touch has no such thing — a finger that is not down is not there.
  function hoverMove(e: PointerEvent) {
    if (dragId !== null || e.pointerType !== 'mouse') return;
    aim = boardPoint(e);
  }

  function hoverOut() {
    if (dragId === null) aim = null;
  }

  function clickPawn(token: string) {
    if (legalSet.has(token)) onMove(token);
  }

  function onKey(e: KeyboardEvent) {
    const tag = (e.target as HTMLElement | null)?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (!canWall) return;
    if (e.key === 'r' || e.key === 'R') {
      rotate();
    } else if (e.key === 'Escape') {
      release();
      forced = null;
      forcedAt = null;
    }
  }

  onMount(() => {
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      release();
    };
  });
</script>

<div class="wrap">
  <div class="rail">
    <span class="dot p{topSeat}"></span>
    <div class="reserve">
      {#each Array(view.wallsLeft[topSeat - 1]) as _}
        <span class="chip"></span>
      {/each}
    </div>
    <span class="count">{view.wallsLeft[topSeat - 1]} walls</span>
  </div>

  <!-- touch-action while a wall can be placed: a drag across the board is a
       placement, not a scroll. Off-turn the page scrolls as it always did. -->
  <svg
    class="board"
    viewBox="0 0 {SIZE} {SIZE}"
    bind:this={svgEl}
    style:touch-action={canWall ? 'none' : 'auto'}
  >
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

    {#if bestWall}
      <rect
        x={bestWall.x}
        y={bestWall.y}
        width={bestWall.w}
        height={bestWall.h}
        rx="3"
        class="best-wall"
      >
        <title>Engine's move: {best}</title>
      </rect>
    {/if}
    {#if bestPawn}
      <circle
        cx={bestPawn.x + CELL / 2}
        cy={bestPawn.y + CELL / 2}
        r={CELL * 0.36}
        class="best-pawn"
      >
        <title>Engine's move: {best}</title>
      </circle>
    {/if}

    {#if snap}
      <rect
        x={snap.x}
        y={snap.y}
        width={snap.w}
        height={snap.h}
        rx="3"
        class="snap"
        class:refused={!candOK}
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

    {#if badge && mark}
      <g class="badge" transform="translate({badge.x},{badge.y})">
        <circle r={BADGE} class="badge-back" />
        <circle r={BADGE} class="badge-tint" style="fill: {classColor(mark)}" />
        <circle
          r={BADGE}
          class="badge-ring"
          style="stroke: {classColor(mark)}"
        />
        <g transform="translate({-GLYPH / 2},{-GLYPH / 2})">
          <MoveMark cls={mark} size={GLYPH} label={classLabel(mark)} />
        </g>
      </g>
    {/if}

    <!-- The wall surface sits under the pawn targets, so a legal pawn square
         keeps its whole 50-unit face and pressing anywhere else takes a wall.
         Only ever present when a wall can actually be placed. -->
    {#if canWall}
      <rect
        x={M}
        y={M}
        width={SPAN}
        height={SPAN}
        class="surface"
        on:pointerdown={grab}
        on:pointermove={hoverMove}
        on:pointerleave={hoverOut}
      />
    {/if}

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

    {#if hand}
      <rect
        x={hand.x + 2}
        y={hand.y + 3}
        width={hand.w}
        height={hand.h}
        rx="3"
        class="hand-shadow"
      />
      <rect
        x={hand.x}
        y={hand.y}
        width={hand.w}
        height={hand.h}
        rx="3"
        class="hand"
        class:refused={!candOK}
      />
    {/if}
  </svg>

  <div class="rail">
    <span class="dot p{bottomSeat}"></span>
    <!-- Press and hold here to take a wall in hand. -->
    <div
      class="reserve"
      class:live={canWall}
      style:touch-action={canWall ? 'none' : 'auto'}
      on:pointerdown={grab}
    >
      {#each Array(view.wallsLeft[bottomSeat - 1]) as _}
        <span class="chip"></span>
      {/each}
    </div>
    <span class="count">
      {#if dragId !== null && candidate}
        <span class="token" class:bad={!candOK}>{candidate}</span>
      {:else}
        {view.wallsLeft[bottomSeat - 1]} walls
      {/if}
    </span>
    {#if color !== null}
      <span class="spacer"></span>
      <button
        class="rot"
        class:armed={forced !== null}
        disabled={!canWall}
        aria-label="Rotate the wall"
        title="Rotate the wall (r, or a second finger while dragging)"
        on:click={rotate}
      >
        <svg viewBox="0 0 24 24" class="rot-icon" aria-hidden="true">
          <rect x="3" y="10.5" width="18" height="3" rx="1.5" class:on={orient === 'h'} />
          <rect x="10.5" y="3" width="3" height="18" rx="1.5" class:on={orient === 'v'} />
        </svg>
      </button>
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
    /* The wall in hand is drawn where the pointer is, which on pick-up is
       still down on the reserve rail: let it show there rather than clipping
       it until it reaches the board. */
    overflow: visible;
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

  /* Where the wall would land. The refused variant is drawn at the slot the
     gesture actually picked, never at some other slot that happens to be
     legal: a preview that quietly moves elsewhere teaches the wrong thing. */
  .snap {
    fill: var(--wall);
    opacity: 0.55;
    stroke: var(--accent);
    stroke-width: 2;
    pointer-events: none;
  }
  .snap.refused {
    fill: none;
    opacity: 1;
    stroke: var(--danger);
    stroke-dasharray: 7 5;
  }

  /* The wall in hand, following the pointer. */
  .hand {
    fill: var(--wall);
    stroke: var(--accent);
    stroke-width: 2;
    opacity: 0.92;
    pointer-events: none;
  }
  .hand.refused {
    stroke: var(--danger);
  }
  .hand-shadow {
    fill: rgba(0, 0, 0, 0.45);
    pointer-events: none;
  }

  /* The engine's move: translucent, dashed, accent — not a piece, and not the
     solid wall-coloured preview of something about to be placed. */
  .best-wall {
    fill: var(--accent);
    fill-opacity: 0.35;
    stroke: var(--accent);
    stroke-width: 2;
    stroke-dasharray: 6 4;
    pointer-events: none;
  }
  .best-pawn {
    fill: var(--accent-soft);
    stroke: var(--accent);
    stroke-width: 2.5;
    stroke-dasharray: 6 4;
    pointer-events: none;
  }

  /* Classification badge: a ringed token in the class colour carrying the
     class glyph, so colour never carries the meaning alone, and nothing about
     it reads as a pawn. */
  .badge {
    pointer-events: none;
  }
  .badge-back {
    fill: var(--surface);
  }
  .badge-tint {
    opacity: 0.28;
  }
  .badge-ring {
    fill: none;
    stroke-width: 2.5;
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
  .surface {
    fill: transparent;
    cursor: grab;
  }
  .rail {
    display: flex;
    align-items: center;
    gap: 3px;
    min-height: 30px;
    padding: 0 4px;
  }
  .reserve {
    display: flex;
    align-items: center;
    gap: 3px;
    padding: 6px 2px;
    border-radius: 5px;
  }
  .reserve.live {
    cursor: grab;
    background: var(--surface-2);
    box-shadow: inset 0 0 0 1px var(--line);
    padding: 6px;
  }
  .reserve.live:hover {
    box-shadow: inset 0 0 0 1px var(--accent);
  }
  .rot {
    display: grid;
    place-items: center;
    width: 44px;
    height: 40px;
    padding: 0;
  }
  .rot.armed:not(:disabled) {
    border-color: var(--accent);
  }
  .rot-icon {
    width: 22px;
    height: 22px;
  }
  .rot-icon rect {
    fill: var(--text-dim);
    opacity: 0.3;
  }
  .rot-icon rect.on {
    fill: var(--wall);
    opacity: 1;
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
  .token {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    color: var(--accent);
  }
  .token.bad {
    color: var(--danger);
  }
  .spacer {
    flex: 1;
  }

  /* On a phone the reserve is the thing you press first: give it a full touch
     target rather than the 18px chips it is drawn from. */
  @media (max-width: 560px) {
    .reserve.live {
      min-height: 44px;
      gap: 4px;
    }
    .chip {
      width: 8px;
      height: 24px;
    }
    .rot {
      height: 44px;
    }
  }
</style>
