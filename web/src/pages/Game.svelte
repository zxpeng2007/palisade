<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { send, subscribe } from '../lib/ws';
  import { account } from '../lib/session';
  import Board from '../lib/Board.svelte';
  import Clock from '../lib/Clock.svelte';
  import MoveList from '../lib/MoveList.svelte';
  import ReviewPanel from '../lib/ReviewPanel.svelte';
  import Title from '../lib/Title.svelte';
  import {
    fetchReview,
    isRunning,
    startReview,
    watchReview,
    type Review,
    type ReviewMove,
  } from '../lib/review';

  export let id: string;

  // Live games come over the websocket (gameFull, then state updates).
  // Finished games are no longer live on the server, so the channel stays
  // silent; the REST fetch below supplies their final view + move list.
  let full: any = null; // {id, rated, clock, first, second}
  let state: any = null; // latest {moves, p1time, p2time, status, winner, reason}
  let view: any = null; // the position the game is actually in
  let legal: string[] | null = null;
  let wsSeen = false;
  let loadError = '';
  let flashMsg = '';
  let flashTimer: ReturnType<typeof setTimeout>;
  let confirming: 'resign' | 'abort' | null = null;

  // -- position history -----------------------------------------------------
  // known[k] is the rendered position after k moves (API.md `views`). It fills
  // from two directions — the REST snapshot brings 0..n in one go, the socket
  // appends one per move — so a hole in the middle is possible until both have
  // landed. `have` is the length of the hole-free prefix; navigation needs it
  // to cover every ply, otherwise there is a moment we simply cannot draw.
  let known: any[] = [];
  let have = 0;
  let latest = 0; // ply the game itself is at
  let ply = 0; // ply the viewer is looking at
  let repaired = false;

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
  $: tc = full ? clockLabel(full.clock) : '';

  // -- review ---------------------------------------------------------------
  // Only finished games can be reviewed, and their review is stored for good,
  // so the page asks once — the moment it learns the game is over — and only
  // polls while a job is genuinely in flight.
  let review: Review | null = null;
  let reviewErr = '';
  let reviewBusy = false;
  let asked = false;
  let unwatch: (() => void) | null = null;

  $: finished = state !== null && state.status === 'finished';
  $: if (finished && !asked) probeReview();
  $: marks =
    review && review.status === 'done' && review.moves
      ? markMap(review.moves)
      : {};

  function markMap(ms: ReviewMove[]): Record<number, string> {
    const out: Record<number, string> = {};
    for (const m of ms) out[m.ply] = m.class;
    return out;
  }

  function take(r: Review | null): void {
    if (!r) return;
    review = r;
    if (unwatch) unwatch();
    unwatch = isRunning(r)
      ? watchReview(
          id,
          (u) => (review = u),
          (msg) => (reviewErr = msg)
        )
      : null;
  }

  async function probeReview() {
    asked = true;
    try {
      take(await fetchReview(id));
    } catch {
      // Having nothing to show is not worth a banner: the button appears, and
      // if starting a review is refused too, that refusal is what gets said.
    }
  }

  async function beginReview() {
    reviewBusy = true;
    reviewErr = '';
    try {
      take(await startReview(id));
    } catch (e: any) {
      reviewErr = e.message;
    } finally {
      reviewBusy = false;
    }
  }

  $: canNavigate = have > latest; // every ply 0..latest is drawable
  $: shownPly = canNavigate ? ply : latest;
  $: shownView = (canNavigate && known[shownPly]) || view;
  $: atLatest = shownPly >= latest;
  $: plyLabel =
    shownPly === 0 ? 'the start position' : `move ${shownPly} of ${latest}`;

  // THE read-only rule: a move is legal for one position only, so the board
  // may accept clicks solely when the viewer is looking at the position the
  // server is in. Scrubbed back, it is a picture.
  $: boardLegal = atLatest && myColor && active ? legal : null;

  function clockLabel(c: any): string {
    const min = Math.round((c.initial / 60) * 10) / 10;
    return `${min}+${c.increment}`;
  }

  // Reactive on `state`: a plain seatTime(top) call in the template would
  // only re-run when `top` changes, freezing both clocks for the whole game.
  $: topTime = state ? ((top === 'first' ? state.p1time : state.p2time) ?? null) : null;
  $: bottomTime = state ? ((bottom === 'first' ? state.p1time : state.p2time) ?? null) : null;

  function plyOf(moveList: string): number {
    return moveList ? moveList.split(',').length : 0;
  }

  function record(n: number, v: any): void {
    if (!v || known[n]) return; // positions never change; first writer wins
    known[n] = v;
    while (known[have]) have++;
  }

  function adopt(list: any): void {
    if (!Array.isArray(list)) return;
    for (let i = 0; i < list.length; i++) record(i, list[i]);
  }

  function applyState(s: any, lg: string[] | null) {
    const n = plyOf(s.moves);
    const following = ply === latest; // read before `latest` moves on
    state = s;
    latest = n;
    if (s.view) {
      view = s.view;
      record(n, s.view);
    }
    legal = lg;
    // Someone reviewing an earlier position keeps their place — a new move
    // must never yank the board out from under them. Only a viewer already at
    // the end rides along.
    if (following) ply = n;
  }

  function goto(p: number): void {
    if (!canNavigate) return;
    ply = Math.max(0, Math.min(latest, p)); // re-selecting the same ply is a no-op
  }

  function onKey(e: KeyboardEvent) {
    if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return;
    const el = e.target as HTMLElement | null;
    const tag = el ? el.tagName : '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (el && el.isContentEditable) return;
    // `ply` and `latest`, not the derived `shownPly`: reactive values settle
    // after the handler returns, so a held-down arrow key would otherwise
    // compute every repeat from the same stale ply and move only one step.
    if (e.key === 'ArrowLeft') goto(ply - 1);
    else if (e.key === 'ArrowRight') goto(ply + 1);
    else if (e.key === 'Home') goto(0);
    else if (e.key === 'End') goto(latest);
    else return;
    e.preventDefault(); // arrows and Home/End otherwise scroll the page
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
      // the legal list; never clobber it with this snapshot. The history is
      // another matter — it arrives nowhere else, so always take it.
      if (!wsSeen) {
        full = g;
        applyState(g.state, null);
        if (g.view) view = g.view; // REST puts the view beside state, not in it
      }
      adopt(g.views);
      if (have <= latest) repair();
    } catch (e: any) {
      if (!wsSeen) loadError = e.message;
    }
  }

  /** Close a hole left by a snapshot older than the socket's first message.
   *
   *  The missing plies were played before we subscribed, so no later socket
   *  message will ever supply them. One repeat fetch is enough and cannot
   *  loop: the socket's first ply is fixed, and any fetch issued after that
   *  message arrived is answered from a position at least that far along. */
  async function repair() {
    if (repaired) return;
    repaired = true;
    try {
      adopt((await api('GET', `/api/game/${id}/views`)).views);
    } catch {
      // An older server without the endpoint. Navigation stays off and the
      // live position still draws — the game is watchable either way.
    }
  }

  function play(token: string) {
    // Belt and braces behind `boardLegal`: a move sent for a position the
    // server has already left is either illegal or, worse, legal by accident.
    if (!atLatest) return;
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
    window.addEventListener('keydown', onKey);
    load();
    return () => {
      unGame();
      unUser();
      window.removeEventListener('keydown', onKey);
      clearTimeout(flashTimer);
      if (unwatch) unwatch();
    };
  });
</script>

{#if loadError}
  <p class="panel">Could not load game: {loadError}</p>
{:else if !full || !view}
  <p class="dim">Loading game…</p>
{:else}
  <div class="game">
    <div class="board-col">
      <Board view={shownView} legal={boardLegal} color={myColor} onMove={play} />

      {#if canNavigate && latest > 0}
        <div class="scrub" class:behind={!atLatest}>
          <span>Viewing {plyLabel}</span>
          {#if !atLatest && active}
            <button class="primary" on:click={() => goto(latest)}>
              {legal && myColor ? 'Return to live to move' : 'Return to live'}
            </button>
          {/if}
        </div>
      {/if}

      {#if finished}
        <ReviewPanel
          {review}
          error={reviewErr}
          busy={reviewBusy}
          total={moves.length}
          ply={shownPly}
          navigable={canNavigate}
          first={full.first.username}
          second={full.second.username}
          onStart={beginReview}
          onSelect={goto}
        />
      {/if}
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
          <Title title={topP.title} />
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

      <MoveList
        {moves}
        {latest}
        {marks}
        ply={shownPly}
        navigable={canNavigate}
        onSelect={goto}
      />

      <div class="seat">
        <div class="who">
          <Title title={bottomP.title} />
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
        <!-- The result belongs to the game, not to the position on screen, so
             it stays up during replay — but it must not be read as a caption
             for an earlier position. -->
        <div class="banner panel">
          {#if state.status === 'aborted'}
            Game aborted
          {:else if state.winner}
            <Title title={full[state.winner].title} />
            <strong>{full[state.winner].username}</strong>
            wins {reasonText(state.reason)}
          {/if}
          {#if !atLatest}
            <div class="note dim">Showing {plyLabel}, not the final position.</div>
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
  .scrub {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
    padding: 2px 4px;
    font-size: 0.9rem;
    color: var(--text-dim);
  }
  .scrub.behind {
    color: var(--text);
    border-left: 3px solid var(--accent);
    padding-left: 8px;
  }
  .banner {
    text-align: center;
    border-color: var(--accent);
  }
  .banner .note {
    font-size: 0.85rem;
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
