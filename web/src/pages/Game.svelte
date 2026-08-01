<script lang="ts">
  import { afterUpdate, onMount } from 'svelte';
  import { api } from '../lib/api';
  import { send, subscribe } from '../lib/ws';
  import { account } from '../lib/session';
  import Board from '../lib/Board.svelte';
  import Clock from '../lib/Clock.svelte';

  export let id: string;

  // Live games come over the websocket (gameFull, then state updates).
  // Finished games are no longer live on the server, so the channel stays
  // silent; the REST fetch below supplies their final view + move list.
  let full: any = null; // {id, rated, clock, first, second}
  let state: any = null; // latest {moves, p1time, p2time, status, winner, reason}
  let view: any = null;
  let legal: string[] | null = null;
  let wsSeen = false;
  let loadError = '';
  let flashMsg = '';
  let flashTimer: ReturnType<typeof setTimeout>;
  let confirming: 'resign' | 'abort' | null = null;
  let movesEl: HTMLElement;
  let renderedPlies = 0;

  $: me = $account ? $account.username : null;
  // Declared, not inferred: the board's `color` prop is a union, and a bare
  // reactive ternary widens to string.
  let myColor: 'first' | 'second' | null = null;
  $: myColor =
    full && me
      ? full.first.username === me
        ? 'first'
        : full.second.username === me
          ? 'second'
          : null
      : null;
  $: moves = state && state.moves ? state.moves.split(',') : [];
  $: active = state !== null && state.status === 'active';
  $: moverSeat = moves.length % 2; // 0 = first to move
  $: bottom = myColor === 'second' ? 'second' : 'first';
  $: top = bottom === 'first' ? 'second' : 'first';
  $: topP = full ? full[top] : null;
  $: bottomP = full ? full[bottom] : null;
  $: pairs = chunk(moves);
  $: tc = full ? clockLabel(full.clock) : '';

  function chunk(ms: string[]) {
    const out = [];
    for (let i = 0; i < ms.length; i += 2) {
      out.push({ n: i / 2 + 1, a: ms[i], b: ms[i + 1] ?? '' });
    }
    return out;
  }

  function clockLabel(c: any): string {
    const min = Math.round((c.initial / 60) * 10) / 10;
    return `${min}+${c.increment}`;
  }

  // Reactive on `state`: a plain seatTime(top) call in the template would
  // only re-run when `top` changes, freezing both clocks for the whole game.
  $: topTime = state ? ((top === 'first' ? state.p1time : state.p2time) ?? null) : null;
  $: bottomTime = state ? ((bottom === 'first' ? state.p1time : state.p2time) ?? null) : null;

  function applyState(s: any, lg: string[] | null) {
    state = s;
    if (s.view) view = s.view;
    legal = lg;
  }

  function onGameMsg(msg: any) {
    wsSeen = true;
    if (msg.t === 'gameFull') {
      full = msg;
      // Only the initial gameFull carries legal inside state; later state
      // messages carry it at the top level.
      applyState(msg.state, msg.state.legal ?? null);
    } else if (msg.t === 'state') {
      applyState(msg, msg.legal ?? null);
    }
  }

  function onUserMsg(msg: any) {
    if (msg.t === 'err') flash(msg.msg);
  }

  function flash(m: string) {
    flashMsg = m;
    clearTimeout(flashTimer);
    flashTimer = setTimeout(() => (flashMsg = ''), 4000);
  }

  async function load() {
    try {
      const g = await api('GET', '/api/game/' + id);
      // A websocket gameFull may already have landed with fresher state and
      // the legal list; never clobber it with this snapshot.
      if (!wsSeen) {
        full = g;
        applyState(g.state, null);
        if (g.view) view = g.view; // REST puts the view beside state, not in it
      }
    } catch (e: any) {
      if (!wsSeen) loadError = e.message;
    }
  }

  function play(token: string) {
    send({ t: 'move', game: id, move: token });
    legal = null; // no second move until the server says it is our turn again
  }

  function doConfirmed() {
    if (confirming) send({ t: confirming, game: id });
    confirming = null;
  }

  function reasonText(reason: string): string {
    if (reason === 'mate') return 'by reaching the goal';
    if (reason === 'resign') return 'by resignation';
    if (reason === 'timeout') return 'on time';
    return reason ?? '';
  }

  onMount(() => {
    const unGame = subscribe('game:' + id, onGameMsg);
    const unUser = subscribe('user', onUserMsg);
    load();
    return () => {
      unGame();
      unUser();
      clearTimeout(flashTimer);
    };
  });

  afterUpdate(() => {
    if (movesEl && moves.length !== renderedPlies) {
      renderedPlies = moves.length;
      movesEl.scrollTop = movesEl.scrollHeight;
    }
  });
</script>

{#if loadError}
  <p class="panel">Could not load game: {loadError}</p>
{:else if !full || !view}
  <p class="dim">Loading game…</p>
{:else}
  <div class="game">
    <div class="board-col">
      <Board
        {view}
        legal={myColor && active ? legal : null}
        color={myColor}
        onMove={play}
      />
    </div>

    <aside>
      <div class="meta dim">
        {full.rated ? 'Rated' : 'Casual'} · {tc}
        {#if !myColor}
          · spectating
        {/if}
      </div>

      <div class="seat">
        <div class="who">
          <a href={'#/@/' + topP.username}>{topP.username}</a>
          {#if topP.bot}<span class="bot-tag">BOT</span>{/if}
          <span class="dim">
            {topP.rating}{topP.provisional ? '?' : ''}
          </span>
          {#if topP.delta !== null && topP.delta !== undefined}
            <span class="delta" class:up={topP.delta > 0}>
              {topP.delta > 0 ? '+' : ''}{Math.round(topP.delta)}
            </span>
          {/if}
        </div>
        <Clock
          time={topTime}
          running={active && moverSeat === (top === 'first' ? 0 : 1)}
        />
      </div>

      <div class="moves panel" bind:this={movesEl}>
        {#if pairs.length === 0}
          <span class="dim">No moves yet.</span>
        {:else}
          <table>
            <tbody>
              {#each pairs as p (p.n)}
                <tr>
                  <td class="num dim">{p.n}.</td>
                  <td>{p.a}</td>
                  <td>{p.b}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </div>

      <div class="seat">
        <div class="who">
          <a href={'#/@/' + bottomP.username}>{bottomP.username}</a>
          {#if bottomP.bot}<span class="bot-tag">BOT</span>{/if}
          <span class="dim">
            {bottomP.rating}{bottomP.provisional ? '?' : ''}
          </span>
          {#if bottomP.delta !== null && bottomP.delta !== undefined}
            <span class="delta" class:up={bottomP.delta > 0}>
              {bottomP.delta > 0 ? '+' : ''}{Math.round(bottomP.delta)}
            </span>
          {/if}
        </div>
        <Clock
          time={bottomTime}
          running={active && moverSeat === (bottom === 'first' ? 0 : 1)}
        />
      </div>

      {#if state.status !== 'active'}
        <div class="banner panel">
          {#if state.status === 'aborted'}
            Game aborted
          {:else if state.winner}
            <strong>{full[state.winner].username}</strong>
            wins {reasonText(state.reason)}
          {/if}
        </div>
      {:else if myColor}
        <div class="controls">
          {#if confirming}
            <span>Really {confirming}?</span>
            <button class="danger" on:click={doConfirmed}>Yes</button>
            <button on:click={() => (confirming = null)}>No</button>
          {:else if moves.length < 2}
            <button on:click={() => (confirming = 'abort')}>Abort</button>
          {:else}
            <button on:click={() => (confirming = 'resign')}>Resign</button>
          {/if}
        </div>
      {/if}

      {#if flashMsg}
        <div class="flash">{flashMsg}</div>
      {/if}
    </aside>
  </div>
{/if}

<style>
  .game {
    display: grid;
    grid-template-columns: minmax(300px, 620px) 280px;
    gap: 24px;
    align-items: start;
  }
  @media (max-width: 900px) {
    .game {
      grid-template-columns: 1fr;
    }
  }
  aside {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .meta {
    font-size: 0.85rem;
  }
  .seat {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }
  .who {
    display: flex;
    align-items: baseline;
    gap: 6px;
    min-width: 0;
  }
  .who a {
    color: var(--text);
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .delta {
    color: var(--danger);
    font-size: 0.85rem;
  }
  .delta.up {
    color: var(--accent);
  }
  .moves {
    height: 260px;
    overflow-y: auto;
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
  .banner {
    text-align: center;
    border-color: var(--accent);
  }
  .controls {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .flash {
    color: var(--danger);
    font-size: 0.9rem;
  }
</style>
