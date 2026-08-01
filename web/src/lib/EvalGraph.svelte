<script lang="ts">
  import { classColor, type ReviewMove } from './review';

  // The engine's opinion of every position in the game, and a way to walk it:
  // this graph is a navigation control first and a picture second. Click or
  // drag anywhere along it to put that position on the board.
  export let moves: ReviewMove[] = [];
  export let ply = 0;
  export let onSelect: (p: number) => void = () => {};
  // Off when the per-ply history is unavailable, so the graph would have
  // nowhere to send the viewer. It still reads; it just does not pretend.
  export let interactive = true;

  const W = 320;
  const H = 104;
  const PAD = 3; // keeps the end points and their stroke inside the viewBox
  const MID = H / 2;
  const AMP = MID - PAD; // pixels per 1.0 of evaluation
  // Only the moves worth interrupting the line for. Marking all seven classes
  // at 5 px a ply would be a dotted mess rather than a graph.
  const NOTABLE = ['brilliant', 'mistake', 'blunder'];

  // clipPath ids are document-global, so two graphs on one page would fight
  // over them.
  const uid = 'eg' + Math.random().toString(36).slice(2, 8);

  let box: HTMLElement;
  let hover: number | null = null;
  let dragging = false;

  $: n = moves.length;
  // Ply 0 is the start position: nobody has moved, so the line begins level.
  $: values = [0, ...moves.map((m) => clamp(m.eval))];
  $: step = (W - 2 * PAD) / Math.max(1, n);
  $: line = values.map((v, k) => `${k ? 'L' : 'M'}${x(k)} ${y(v)}`).join(' ');
  // The filled region is between the curve and the centre line, so closing it
  // along y=0 (not along the floor) is what lets the two halves take the two
  // players' colours.
  $: area = `${line} L${x(n)} ${MID} L${x(0)} ${MID} Z`;
  $: notable = moves
    .map((m, i) => ({ m, k: i + 1 }))
    .filter((p) => NOTABLE.indexOf(p.m.class) >= 0);
  $: at = Math.max(0, Math.min(n, ply));

  function clamp(v: number): number {
    return Number.isFinite(v) ? Math.max(-1, Math.min(1, v)) : 0;
  }

  function x(k: number): number {
    return PAD + k * step;
  }

  function y(v: number): number {
    return MID - v * AMP;
  }

  /** Which ply the pointer is over. The viewBox scales uniformly with the
   *  element's width, so one ratio converts client pixels to graph units. */
  function plyAt(clientX: number): number {
    const r = box.getBoundingClientRect();
    if (!r.width) return at;
    const u = ((clientX - r.left) / r.width) * W;
    return Math.max(0, Math.min(n, Math.round((u - PAD) / step)));
  }

  function down(e: PointerEvent) {
    if (!interactive) return;
    dragging = true;
    hover = plyAt(e.clientX);
    onSelect(hover);
    e.preventDefault(); // a drag across the panel must not select text
    // Capture keeps a drag that wanders off the graph — or off the window —
    // scrubbing, and lets it end cleanly. It is an improvement to the drag,
    // not a condition of the click, so it goes last and may fail: a browser
    // that has already let go of the pointer must not cost us the selection.
    try {
      box.setPointerCapture(e.pointerId);
    } catch {
      // Capture refused: the drag still works while the pointer is over the
      // graph, and `move` notices the button coming up either way.
    }
  }

  function move(e: PointerEvent) {
    if (!interactive) return;
    // A pointerup that happened somewhere we never heard about must not leave
    // the graph scrubbing under a pointer with no button pressed.
    if (dragging && !e.buttons) dragging = false;
    hover = plyAt(e.clientX);
    if (dragging) onSelect(hover);
  }

  function up(e: PointerEvent) {
    dragging = false;
    if (box && box.hasPointerCapture(e.pointerId)) {
      box.releasePointerCapture(e.pointerId);
    }
  }
</script>

<!-- Arrow keys, Home and End are already handled for the whole page, so a
     focused graph walks the game with the keyboard without a second listener
     racing the first. -->
<div
  class="graph"
  class:live={interactive}
  bind:this={box}
  role="slider"
  tabindex="0"
  aria-label="Evaluation graph"
  aria-disabled={!interactive}
  aria-valuemin="0"
  aria-valuemax={n}
  aria-valuenow={at}
  aria-valuetext={at === 0 ? 'start position' : `move ${at} of ${n}`}
  on:pointerdown={down}
  on:pointermove={move}
  on:pointerup={up}
  on:pointercancel={up}
  on:pointerleave={() => (hover = null)}
>
  <svg viewBox="0 0 {W} {H}" aria-hidden="true">
    <defs>
      <clipPath id="{uid}-up"><rect x="0" y="0" width={W} height={MID} /></clipPath>
      <clipPath id="{uid}-dn"><rect x="0" y={MID} width={W} height={MID} /></clipPath>
    </defs>

    <rect class="bg" x="0" y="0" width={W} height={H} />
    <path class="fill p1" d={area} clip-path="url(#{uid}-up)" />
    <path class="fill p2" d={area} clip-path="url(#{uid}-dn)" />
    <line class="axis" x1="0" y1={MID} x2={W} y2={MID} />
    <path class="line" d={line} />

    {#each notable as p (p.k)}
      <circle
        cx={x(p.k)}
        cy={y(values[p.k])}
        r="2.6"
        class="dot"
        style="fill: {classColor(p.m.class)}"
      />
    {/each}

    {#if hover !== null && hover !== at}
      <line class="hover" x1={x(hover)} y1="0" x2={x(hover)} y2={H} />
    {/if}

    <line class="cursor" x1={x(at)} y1="0" x2={x(at)} y2={H} />
    <circle class="knob" cx={x(at)} cy={y(values[at] ?? 0)} r="3.4" />

    <text class="tick" x={PAD + 3} y="10">+1</text>
    <text class="tick" x={PAD + 3} y={H - 4}>-1</text>
  </svg>
</div>

<style>
  .graph {
    position: relative;
    border: 1px solid var(--line);
    border-radius: 6px;
    overflow: hidden;
    /* A drag along the graph is a scrub, not a page scroll. */
    touch-action: none;
  }
  .graph.live {
    cursor: pointer;
  }
  .graph:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }
  svg {
    display: block;
    width: 100%;
    height: auto;
  }
  .bg {
    fill: var(--bg);
  }
  .fill.p1 {
    fill: var(--p1);
    opacity: 0.45;
  }
  .fill.p2 {
    fill: var(--p2);
    opacity: 0.45;
  }
  .line {
    fill: none;
    stroke: var(--text);
    stroke-width: 1.4;
    stroke-linejoin: round;
    opacity: 0.75;
  }
  .axis {
    stroke: var(--text-dim);
    stroke-width: 1;
    opacity: 0.8;
  }
  .dot {
    stroke: var(--bg);
    stroke-width: 1;
  }
  .cursor {
    stroke: var(--accent);
    stroke-width: 1.6;
  }
  .knob {
    fill: var(--accent);
    stroke: var(--bg);
    stroke-width: 1.4;
  }
  .hover {
    stroke: var(--text);
    stroke-width: 1;
    opacity: 0.35;
  }
  .tick {
    fill: var(--text-dim);
    font-size: 9px;
  }
</style>
