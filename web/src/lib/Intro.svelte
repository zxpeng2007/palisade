<script lang="ts">
  /* The first thing a newcomer sees. Almost nobody arriving here has played
   * this game before — it is not chess, and the name on the door tells them
   * nothing — so the site has to teach the rules before it can ask for a move.
   *
   * Four panels, because there are exactly four things you must know to play:
   * where you are going, what a turn is, what a wall does, and the one rule
   * that stops walls being unfair. Everything else can be discovered.
   *
   * Each panel carries a real board drawn with the same geometry module the
   * playable board uses, so the pictures cannot drift from the game.
   */
  import { createEventDispatcher } from 'svelte';
  import { CELL, GAP, M, SIZE, SPAN, STEP, squareXY, wallGeom } from './geometry';

  export let open = false;

  const dispatch = createEventDispatcher();
  let step = 0;

  interface Panel {
    title: string;
    body: string;
    p1: string;
    p2: string;
    walls: string[];
    goal: 'top' | null;
    path: string[];
    note?: string;
  }

  const PANELS: Panel[] = [
    {
      title: 'Race to the other side',
      body:
        'You are the amber pawn on the near side. Get to any square on the far ' +
        'row and you win. Your opponent is doing the same in the other ' +
        'direction — first one across wins, and there are no draws.',
      p1: 'e1',
      p2: 'e9',
      walls: [],
      goal: 'top',
      path: [],
      note: 'Nine rows to cross.',
    },
    {
      title: 'A turn is a step, or a wall',
      body:
        'On your turn you either move your pawn one square — up, down, left ' +
        'or right — or you place one of your ten walls. You cannot do both, ' +
        'and that trade is the whole game: every wall you place is a step you ' +
        'did not take.',
      p1: 'e2',
      p2: 'e8',
      walls: [],
      goal: null,
      path: ['e1', 'e2'],
      note: 'Both pawns have taken one step.',
    },
    {
      title: 'Walls block the way',
      body:
        'A wall sits between squares and spans two of them. Nobody may cross ' +
        'it — including you, so a wall aimed at your opponent can just as ' +
        'easily cost you the game. You have ten, and when they are gone they ' +
        'are gone.',
      p1: 'e4',
      p2: 'e6',
      walls: ['he5'],
      goal: null,
      path: [],
      note: 'The amber pawn must now go around.',
    },
    {
      title: 'You may never seal someone in',
      body:
        'The one rule that keeps walls honest: a wall is illegal if it would ' +
        'leave either player with no route at all to their far row. You can ' +
        'make the journey long. You cannot make it impossible.',
      p1: 'e5',
      p2: 'e7',
      walls: ['hd6', 'hf6', 'vc5', 'vf5'],
      goal: null,
      path: [],
      note: 'A cage like this can never be closed completely.',
    },
  ];

  $: panel = PANELS[step];
  $: last = step === PANELS.length - 1;
  // Derived here rather than with {@const} in the markup: that directive is
  // only allowed as the immediate child of a block, and these sit straight
  // inside the <svg>.
  $: p1XY = squareXY(panel.p1);
  $: p2XY = squareXY(panel.p2);

  function close() {
    open = false;
    step = 0;
    dispatch('close');
  }

  function next() {
    if (last) close();
    else step += 1;
  }

  function onKey(e: KeyboardEvent) {
    if (!open) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowRight') next();
    else if (e.key === 'ArrowLeft' && step > 0) step -= 1;
  }

  // The panels draw a board at a smaller scale than the playable one; the
  // geometry module works in its own units, so the viewBox does the shrinking
  // and every coordinate stays the one the real board would use.
  const cells = Array.from({ length: 9 }, (_, r) =>
    Array.from({ length: 9 }, (_, f) => ({
      x: M + f * STEP,
      y: M + r * STEP,
    })),
  );
</script>

<svelte:window on:keydown={onKey} />

{#if open}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <div class="scrim" on:click|self={close} role="presentation">
    <div
      class="sheet"
      role="dialog"
      aria-modal="true"
      aria-label="How to play Murus"
    >
      <div class="art">
        <svg viewBox="0 0 {SIZE} {SIZE}" aria-hidden="true">
          {#if panel.goal === 'top'}
            <rect
              class="goal"
              x={M}
              y={M}
              width={SPAN}
              height={CELL}
              rx="3"
            />
          {/if}
          {#each cells as row}
            {#each row as c}
              <rect class="cell" x={c.x} y={c.y} width={CELL} height={CELL} rx="3" />
            {/each}
          {/each}

          {#each panel.path as sq, i}
            {@const p = squareXY(sq)}
            <circle
              class="trace"
              cx={p.x + CELL / 2}
              cy={p.y + CELL / 2}
              r={CELL * 0.16}
              opacity={0.25 + 0.2 * i}
            />
          {/each}

          {#each panel.walls as w}
            {@const g = wallGeom(w)}
            <rect class="wall" x={g.x} y={g.y} width={g.w} height={g.h} rx="3" />
          {/each}

          <circle
            class="p1"
            cx={p1XY.x + CELL / 2}
            cy={p1XY.y + CELL / 2}
            r={CELL * 0.34}
          />
          <circle
            class="p2"
            cx={p2XY.x + CELL / 2}
            cy={p2XY.y + CELL / 2}
            r={CELL * 0.34}
          />

          {#if panel.goal === 'top'}
            <text class="flag" x={M + SPAN / 2} y={M + CELL * 0.68} text-anchor="middle"
              >your goal</text
            >
          {/if}
        </svg>
        {#if panel.note}<p class="note">{panel.note}</p>{/if}
      </div>

      <div class="words">
        <h2>{panel.title}</h2>
        <p>{panel.body}</p>

        <div class="foot">
          <div class="dots" aria-hidden="true">
            {#each PANELS as _, i}
              <span class="dot" class:on={i === step}></span>
            {/each}
          </div>
          <div class="buttons">
            <button class="ghost" on:click={close}>
              {last ? 'Close' : 'Skip'}
            </button>
            <button class="primary" on:click={next}>
              {last ? 'Play' : 'Next'}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .scrim {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.66);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
    z-index: 60;
  }
  .sheet {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 10px;
    max-width: 720px;
    width: 100%;
    max-height: calc(100vh - 32px);
    overflow-y: auto;
    display: grid;
    grid-template-columns: 260px 1fr;
    gap: 20px;
    padding: 20px;
    box-shadow: 0 18px 60px rgba(0, 0, 0, 0.5);
  }
  .art svg {
    width: 100%;
    height: auto;
    display: block;
  }
  .cell {
    fill: var(--cell);
  }
  .goal {
    fill: var(--accent-soft);
  }
  .wall {
    fill: var(--wall);
  }
  .trace {
    fill: var(--p1);
  }
  .p1 {
    fill: var(--p1);
  }
  .p2 {
    fill: var(--p2);
  }
  .flag {
    fill: var(--text);
    font-size: 22px;
    opacity: 0.75;
  }
  .note {
    margin: 8px 0 0;
    font-size: 0.82rem;
    color: var(--text-dim);
    text-align: center;
  }
  .words {
    display: flex;
    flex-direction: column;
  }
  h2 {
    margin: 0 0 10px;
    font-size: 1.25rem;
  }
  .words p {
    margin: 0;
    line-height: 1.6;
    color: var(--text);
  }
  .foot {
    margin-top: auto;
    padding-top: 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }
  .dots {
    display: flex;
    gap: 6px;
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--line);
  }
  .dot.on {
    background: var(--accent);
  }
  .buttons {
    display: flex;
    gap: 8px;
  }
  button {
    min-height: 44px;
    padding: 0 18px;
    border-radius: 6px;
    font-size: 0.95rem;
    cursor: pointer;
  }
  .primary {
    background: var(--accent);
    border: 1px solid var(--accent);
    color: #12200a;
    font-weight: 600;
  }
  .ghost {
    background: transparent;
    border: 1px solid var(--line);
    color: var(--text-dim);
  }

  @media (max-width: 620px) {
    .sheet {
      grid-template-columns: 1fr;
      gap: 14px;
      padding: 16px;
    }
    /* The picture is the explanation on a phone, but it must not push the
     * words off the screen, so it gets a share of the height rather than
     * whatever its aspect ratio asks for. */
    .art svg {
      max-height: 38vh;
      margin: 0 auto;
    }
    .foot {
      padding-top: 14px;
    }
    .buttons {
      flex: 1;
      justify-content: flex-end;
    }
  }
</style>
