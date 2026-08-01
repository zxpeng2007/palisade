<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from './api';
  import { poll } from './poll';

  export let kind: 'human' | 'bot';
  export let empty: string;
  export let title = 'Leaderboard';

  let players: any[] = [];
  let loaded = false;
  let error = '';

  async function load() {
    try {
      const data = await api('GET', `/api/leaderboard?kind=${kind}&limit=20`);
      players = data.players ?? [];
      error = '';
    } catch (e: any) {
      error = e.message;
    }
    loaded = true;
  }

  onMount(() => poll(load));
</script>

<div class="panel">
  <h2>{title}</h2>

  {#if error}
    <p class="dim">Could not load the leaderboard: {error}</p>
  {:else if !loaded}
    <p class="dim">Loading ratings…</p>
  {:else if players.length === 0}
    <p class="dim">{empty}</p>
  {:else}
    <div class="scroll">
      <table>
        <thead>
          <tr>
            <th class="rank">#</th>
            <th>Player</th>
            <th class="num">Rating</th>
            <th class="num">Games</th>
          </tr>
        </thead>
        <tbody>
          {#each players as p (p.username)}
            <tr>
              <td class="rank dim">{p.rank}</td>
              <td class="who">
                <a href={'#/@/' + encodeURIComponent(p.username)}>{p.username}</a>
                <!-- In engine mode every row is a bot; the tag would be noise. -->
                {#if p.bot && kind !== 'bot'}<span class="bot-tag">BOT</span>{/if}
              </td>
              <td class="num rating">
                {p.rating}{#if p.provisional}<abbr
                    class="prov"
                    title="Provisional — too few rated games for the number to mean much">?</abbr
                  >{/if}
              </td>
              <td class="num dim">{p.games}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  /* Narrow screens scroll the table, never the page. */
  .scroll {
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    white-space: nowrap;
  }
  th {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-dim);
    text-align: left;
    padding: 0 10px 4px 0;
  }
  td {
    padding: 4px 10px 4px 0;
    border-top: 1px solid var(--line);
  }
  th.num,
  td.num {
    text-align: right;
    padding-right: 0;
    font-variant-numeric: tabular-nums;
  }
  th.num + th.num,
  td.num + td.num {
    padding-left: 14px;
  }
  .rank {
    width: 2.2em;
    font-variant-numeric: tabular-nums;
  }
  .who {
    width: 99%; /* the name column absorbs the slack */
  }
  .rating {
    font-weight: 600;
  }
  .prov {
    color: var(--text-dim);
    text-decoration: none;
    cursor: help;
  }
</style>
