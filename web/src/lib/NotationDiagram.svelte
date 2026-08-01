<script lang="ts">
  import {
    CELL,
    FILES,
    GAP,
    M,
    SIZE,
    SPAN,
    STEP,
    squareXY,
    wallGeom,
  } from './geometry';

  // One position that shows every token shape at once. The rects come from the
  // same geometry the playable board uses, so what an engine author reads off
  // this picture is what the server will draw.
  const PAWN1 = 'e1';
  const PAWN2 = 'e9';
  const MOVE = 'e2'; // pawn destination
  const WALL_H = 'hd3'; // anchor d3, lying on the edge between ranks 3 and 4
  const WALL_V = 'vf6'; // anchor f6, lying on the edge between files f and g

  const GRID = [0, 1, 2, 3, 4, 5, 6, 7, 8];

  const p1 = squareXY(PAWN1);
  const p2 = squareXY(PAWN2);
  const dest = squareXY(MOVE);
  const wh = wallGeom(WALL_H);
  const wv = wallGeom(WALL_V);
  const anchorH = squareXY(WALL_H.slice(1));
  const anchorV = squareXY(WALL_V.slice(1));

  const rankLabels = GRID.map((r) => ({
    text: String(r + 1),
    x: M - 12,
    y: M + (8 - r) * STEP + CELL / 2,
  }));
  const fileLabels = GRID.map((f) => ({
    text: FILES[f],
    x: M + f * STEP + CELL / 2,
    y: M + SPAN + 17,
  }));
</script>

<figure>
  <svg viewBox="0 0 {SIZE} {SIZE}" role="img" aria-labelledby="notation-caption">
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
      <text x={l.x} y={l.y} class="coord" text-anchor="middle" dominant-baseline="central"
        >{l.text}</text
      >
    {/each}
    {#each fileLabels as l}
      <text x={l.x} y={l.y} class="coord" text-anchor="middle">{l.text}</text>
    {/each}

    <!-- Anchor squares: the token names this square, the wall hangs off it. -->
    <rect x={anchorH.x} y={anchorH.y} width={CELL} height={CELL} rx="4" class="anchor" />
    <text
      x={anchorH.x + CELL / 2}
      y={anchorH.y + CELL / 2}
      class="anchor-text"
      text-anchor="middle"
      dominant-baseline="central">d3</text
    >
    <rect x={anchorV.x} y={anchorV.y} width={CELL} height={CELL} rx="4" class="anchor" />
    <text
      x={anchorV.x + CELL / 2}
      y={anchorV.y + CELL / 2}
      class="anchor-text"
      text-anchor="middle"
      dominant-baseline="central">f6</text
    >

    <rect x={wh.x} y={wh.y} width={wh.w} height={wh.h} rx="3" class="wall" />
    <rect x={wv.x} y={wv.y} width={wv.w} height={wv.h} rx="3" class="wall" />

    <!-- Pawns, and the move that names its destination. -->
    <circle cx={p1.x + CELL / 2} cy={p1.y + CELL / 2} r={CELL * 0.36} class="pawn p1" />
    <circle cx={p2.x + CELL / 2} cy={p2.y + CELL / 2} r={CELL * 0.36} class="pawn p2" />
    <line
      x1={p1.x + CELL / 2}
      y1={p1.y + CELL / 2 - 20}
      x2={dest.x + CELL / 2}
      y2={dest.y + CELL / 2 + 16}
      class="arrow"
    />
    <circle cx={dest.x + CELL / 2} cy={dest.y + CELL / 2} r="10" class="dot" />

    <line
      x1={dest.x + CELL / 2 + 14}
      y1={dest.y + CELL / 2}
      x2={dest.x + CELL + GAP + 2}
      y2={dest.y + CELL / 2}
      class="leader"
    />
    <text x={dest.x + CELL + GAP + 8} y={dest.y + CELL / 2 - 4} class="token">e2</text>
    <text x={dest.x + CELL + GAP + 8} y={dest.y + CELL / 2 + 15} class="gloss">
      pawn move: the square it lands on
    </text>

    <text x={wh.x + wh.w / 2} y={wh.y - 14} class="token" text-anchor="middle">hd3</text>
    <text x={wh.x + wh.w / 2} y={wh.y - 35} class="gloss" text-anchor="middle">
      edge between ranks 3 and 4, across files d–e
    </text>

    <text x={wv.x + wv.w + 10} y={wv.y + wv.h / 2 - 4} class="token">vf6</text>
    <text x={wv.x + wv.w + 10} y={wv.y + wv.h / 2 + 16} class="gloss">edge between</text>
    <text x={wv.x + wv.w + 10} y={wv.y + wv.h / 2 + 33} class="gloss">
      files f and g, up ranks 6–7
    </text>
  </svg>

  <figcaption id="notation-caption">
    Squares are <code>a1</code>–<code>i9</code>, file then rank, from Player 1's
    side. A pawn move is written as its destination — jumps included. A wall is
    <code>h</code> or <code>v</code> plus its anchor square: the horizontal wall
    lies along the anchor's upper edge, the vertical wall along its right edge,
    and both are two squares long. Anchors run <code>a1</code>–<code>h8</code>.
  </figcaption>
</figure>

<style>
  figure {
    margin: 0;
  }
  svg {
    display: block;
    width: 100%;
    max-width: 460px;
    height: auto;
    margin: 0 auto;
  }
  .frame {
    fill: var(--surface);
    stroke: var(--line);
  }
  .cell {
    fill: var(--cell);
  }
  .anchor {
    fill: var(--accent-soft);
  }
  .anchor-text {
    fill: var(--text);
    font-size: 15px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    opacity: 0.75;
  }
  .coord {
    fill: var(--text-dim);
    font-size: 12px;
  }
  .wall {
    fill: var(--wall);
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
  .dot {
    fill: var(--accent-soft);
    stroke: var(--accent);
    stroke-width: 1.5;
  }
  .arrow,
  .leader {
    stroke: var(--accent);
    stroke-width: 1.5;
    opacity: 0.7;
  }
  .arrow {
    stroke-dasharray: 4 4;
  }
  .token {
    fill: var(--accent);
    font-size: 19px;
    font-weight: 700;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }
  .gloss {
    fill: var(--text-dim);
    font-size: 12.5px;
  }
  figcaption {
    margin-top: 10px;
    font-size: 0.88rem;
    color: var(--text-dim);
  }
  figcaption code {
    color: var(--text);
  }
</style>
