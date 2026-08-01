<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from './api';
  import { poll } from './poll';
  import { SPEEDS, SPEED_LABEL, clockLabel, reasonText, timeAgo } from './format';

  /** "human" = games where neither player is an engine, "bot" = both are. */
  export let kind: 'human' | 'bot';
  /** What to say when there is nothing to show at all. */
  export let empty: string;
  export let title = 'Top games';

  let live: Record<string, any[]> = {};
  let recent: Record<string, any[]> = {};
  let loaded = false;
  let error = '';

  // Group order is fixed (fastest first); a speed with nothing in it vanishes.
  $: groups = SPEEDS.map((s) => ({
    speed: s,
    live: live[s] ?? [],
    recent: recent[s] ?? [],
  })).filter((g) => g.live.length > 0 || g.recent.length > 0);

  async function load() {
    try {
      const data = await api('GET', `/api/games/top?kind=${kind}&limit=8`);
      live = data.live ?? {};
      recent = data.recent ?? {};
      error = '';
    } catch (e: any) {
      error = e.message;
    }
    loaded = true;
  }

  function score(g: any): string {
    if (g.winner === 'first') return '1–0';
    if (g.winner === 'second') return '0–1';
    return '–';
  }

  function won(g: any, seat: 'first' | 'second'): boolean {
    return g.winner === seat;
  }

  onMount(() => poll(load));
</script>

<div class="panel">
  <h2>{title}</h2>

  {#if error}
    <p class="dim">Could not load games: {error}</p>
  {:else if !loaded}
    <p class="dim">Loading games…</p>
  {:else if groups.length === 0}
    <p class="dim">{empty}</p>
  {:else}
    {#each groups as g (g.speed)}
      <section>
        <h3>{SPEED_LABEL[g.speed]}</h3>
        {#each g.live as game (game.id)}
          <a class="row" href={'#/game/' + game.id}>
            <span class="mark live"><span class="pip"></span>LIVE</span>
            <span class="players">
              <span class="name">{game.first.username}</span>
              <span class="rt">{game.first.rating}</span>
              <span class="vs">vs</span>
              <span class="name">{game.second.username}</span>
              <span class="rt">{game.second.rating}</span>
            </span>
            <span class="meta">
              <span class="tc">{clockLabel(game.clock)}</span>
              <span class="dim">{game.rated ? 'rated' : 'casual'} · ply {game.ply}</span>
            </span>
          </a>
        {/each}
        {#each g.recent as game (game.id)}
          <a class="row" href={'#/game/' + game.id}>
            <span class="mark score" title={reasonText(game.reason)}>{score(game)}</span>
            <span class="players">
              <span class="name" class:winner={won(game, 'first')}>
                {game.first.username}
              </span>
              <span class="rt">{game.first.rating}</span>
              <span class="vs">vs</span>
              <span class="name" class:winner={won(game, 'second')}>
                {game.second.username}
              </span>
              <span class="rt">{game.second.rating}</span>
            </span>
            <span class="meta">
              <span class="tc">{clockLabel(game.clock)}</span>
              <span class="dim">{reasonText(game.reason)} · {timeAgo(game.finished)}</span>
            </span>
          </a>
        {/each}
      </section>
    {/each}
  {/if}
</div>

<style>
  section {
    margin-top: 12px;
  }
  section:first-of-type {
    margin-top: 0;
  }
  h3 {
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--text-dim);
    margin: 0 0 2px;
    padding-bottom: 2px;
    border-bottom: 1px solid var(--line);
  }
  .row {
    display: grid;
    grid-template-columns: 4.2em minmax(0, 1fr) auto;
    align-items: center;
    gap: 10px;
    padding: 5px 6px;
    border-radius: 5px;
    color: var(--text);
  }
  .row:hover {
    background: var(--surface-2);
    text-decoration: none;
  }
  .mark {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .mark.live {
    color: var(--accent);
  }
  .mark.score {
    color: var(--text-dim);
    font-size: 0.85rem;
  }
  .pip {
    display: inline-block;
    width: 6px;
    height: 6px;
    margin-right: 5px;
    border-radius: 50%;
    background: var(--accent);
    vertical-align: 1px;
    animation: pulse 1.8s ease-in-out infinite;
  }
  @keyframes pulse {
    50% {
      opacity: 0.25;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .pip {
      animation: none;
    }
  }
  .players {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .name.winner {
    font-weight: 700;
  }
  .rt,
  .vs {
    color: var(--text-dim);
    font-size: 0.85rem;
    font-variant-numeric: tabular-nums;
  }
  .vs {
    margin: 0 4px;
  }
  .meta {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    line-height: 1.3;
    white-space: nowrap;
  }
  .tc {
    font-size: 0.9rem;
    font-variant-numeric: tabular-nums;
  }
  .meta .dim {
    font-size: 0.75rem;
  }
  @media (max-width: 480px) {
    .row {
      grid-template-columns: 3.6em minmax(0, 1fr);
    }
    .meta {
      grid-column: 2;
      flex-direction: row;
      gap: 8px;
      align-items: baseline;
      justify-content: flex-start;
    }
  }
</style>
