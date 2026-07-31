<script lang="ts">
  import { onMount } from 'svelte';
  import { send, subscribe } from '../lib/ws';
  import { account } from '../lib/session';

  const PRESETS = [
    { label: '1+0', initial: 60, increment: 0 },
    { label: '3+0', initial: 180, increment: 0 },
    { label: '3+2', initial: 180, increment: 2 },
    { label: '5+3', initial: 300, increment: 3 },
    { label: '10+0', initial: 600, increment: 0 },
    { label: '15+10', initial: 900, increment: 10 },
  ];

  let seeks: any[] = [];
  let games: any[] = [];
  let bots: any[] = [];
  let rated = false;
  let incoming: any[] = []; // challenges aimed at me
  let note = '';
  let noteTimer: ReturnType<typeof setTimeout>;

  // challenge dialog
  let target: string | null = null;
  let chPreset = PRESETS[3];
  let chRated = false;
  let chColor: 'random' | 'first' | 'second' = 'random';

  $: me = $account ? $account.username : null;
  $: mySeek = me ? seeks.find((s) => s.username === me) : null;

  function onLobby(msg: any) {
    seeks = msg.seeks ?? [];
    games = msg.games ?? [];
    bots = msg.bots ?? [];
  }

  function onUser(msg: any) {
    if (msg.t === 'challenge') {
      incoming = [
        ...incoming.filter((c) => c.id !== msg.challenge.id),
        msg.challenge,
      ];
    } else if (msg.t === 'challengeCanceled') {
      incoming = incoming.filter((c) => c.id !== msg.challenge.id);
    } else if (msg.t === 'challengeDeclined') {
      flash(`${msg.challenge.destUser} declined your challenge`);
    } else if (msg.t === 'err') {
      flash(msg.msg);
    }
  }

  function flash(m: string) {
    note = m;
    clearTimeout(noteTimer);
    noteTimer = setTimeout(() => (note = ''), 4000);
  }

  /** Route to sign-in when an action needs an account; true = bail out. */
  function needLogin(): boolean {
    if (me) return false;
    location.hash = '#/login';
    return true;
  }

  function createSeek(p: (typeof PRESETS)[number]) {
    if (needLogin()) return;
    send({
      t: 'seek',
      rated,
      clock: { initial: p.initial, increment: p.increment },
    });
  }

  // Accepting a seek = sending a matching one; the server pairs them.
  function acceptSeek(s: any) {
    if (needLogin() || s.username === me) return;
    send({ t: 'seek', rated: s.rated, clock: s.clock });
  }

  function cancelSeek() {
    send({ t: 'seekCancel' });
  }

  function sendChallenge() {
    if (needLogin() || !target) return;
    send({
      t: 'challenge',
      user: target,
      rated: chRated,
      clock: { initial: chPreset.initial, increment: chPreset.increment },
      color: chColor,
    });
    flash('Challenge sent to ' + target);
    target = null;
  }

  function acceptChallenge(c: any) {
    send({ t: 'accept', id: c.id });
    incoming = incoming.filter((x) => x.id !== c.id);
  }

  function declineChallenge(c: any) {
    send({ t: 'decline', id: c.id });
    incoming = incoming.filter((x) => x.id !== c.id);
  }

  function clockLabel(c: any): string {
    const min = Math.round((c.initial / 60) * 10) / 10;
    return `${min}+${c.increment}`;
  }

  onMount(() => {
    const unLobby = subscribe('lobby', onLobby);
    const unUser = subscribe('user', onUser);
    return () => {
      unLobby();
      unUser();
    };
  });
</script>

<div class="lobby">
  <section>
    <div class="panel">
      <h2>Create a game</h2>
      {#if mySeek}
        <p>
          Seeking {clockLabel(mySeek.clock)}
          {mySeek.rated ? 'rated' : 'casual'}…
          <button on:click={cancelSeek}>Cancel</button>
        </p>
      {:else}
        <div class="presets">
          {#each PRESETS as p (p.label)}
            <button class="preset" on:click={() => createSeek(p)}>{p.label}</button>
          {/each}
        </div>
        <label class="rated-toggle">
          <input type="checkbox" bind:checked={rated} /> Rated
        </label>
        {#if !me}
          <p class="dim">
            <a href="#/login">Sign in</a> to play — spectating is open to all.
          </p>
        {/if}
      {/if}
    </div>

    {#if incoming.length > 0}
      <div class="panel">
        <h2>Challenges</h2>
        {#each incoming as c (c.id)}
          <div class="row">
            <span>
              <strong>{c.challenger}</strong>
              · {clockLabel(c.clock)} · {c.rated ? 'rated' : 'casual'}
              · they play {c.color}
            </span>
            <span class="actions">
              <button class="primary" on:click={() => acceptChallenge(c)}>
                Accept
              </button>
              <button on:click={() => declineChallenge(c)}>Decline</button>
            </span>
          </div>
        {/each}
      </div>
    {/if}

    <div class="panel">
      <h2>Open seeks</h2>
      {#if seeks.length === 0}
        <p class="dim">No one is waiting. Create a seek above.</p>
      {:else}
        {#each seeks as s}
          {#if s.username === me}
            <div class="row">
              <span>
                <strong>{s.username}</strong> ({s.rating})
                · {clockLabel(s.clock)} · {s.rated ? 'rated' : 'casual'}
                <span class="dim">— your seek</span>
              </span>
              <button on:click={cancelSeek}>Cancel</button>
            </div>
          {:else}
            <button class="row join" on:click={() => acceptSeek(s)}>
              <span>
                <strong>{s.username}</strong> ({s.rating})
                · {clockLabel(s.clock)} · {s.rated ? 'rated' : 'casual'}
              </span>
              <span class="dim">Join</span>
            </button>
          {/if}
        {/each}
      {/if}
    </div>
  </section>

  <section>
    <div class="panel">
      <h2>Games in progress</h2>
      {#if games.length === 0}
        <p class="dim">Nothing being played right now.</p>
      {:else}
        {#each games as g (g.id)}
          <a class="row spectate" href={'#/game/' + g.id}>
            <span>
              {g.first.username} ({g.first.rating}) vs
              {g.second.username} ({g.second.rating})
            </span>
            <span class="dim">
              {clockLabel(g.clock)} · {g.rated ? 'rated' : 'casual'} · ply {g.ply}
            </span>
          </a>
        {/each}
      {/if}
    </div>

    <div class="panel">
      <h2>Online bots</h2>
      {#if bots.length === 0}
        <p class="dim">No bots online.</p>
      {:else}
        {#each bots as b (b.username)}
          <div class="row">
            <span>
              <a href={'#/@/' + b.username}>{b.username}</a>
              <span class="bot-tag">BOT</span>
              <span class="dim">{b.rating}{b.provisional ? '?' : ''}</span>
            </span>
            <button
              disabled={me === b.username}
              on:click={() => (target = target === b.username ? null : b.username)}
            >
              Challenge
            </button>
          </div>
          {#if target === b.username}
            <div class="challenge-form">
              <label>
                Clock
                <select bind:value={chPreset}>
                  {#each PRESETS as p (p.label)}
                    <option value={p}>{p.label}</option>
                  {/each}
                </select>
              </label>
              <label>
                <input type="checkbox" bind:checked={chRated} /> Rated
              </label>
              <label>
                You play
                <select bind:value={chColor}>
                  <option value="random">random</option>
                  <option value="first">first</option>
                  <option value="second">second</option>
                </select>
              </label>
              <button class="primary" on:click={sendChallenge}>Send</button>
              <button on:click={() => (target = null)}>Cancel</button>
            </div>
          {/if}
        {/each}
      {/if}
    </div>

    {#if note}
      <div class="note">{note}</div>
    {/if}
  </section>
</div>

<style>
  .lobby {
    display: grid;
    grid-template-columns: 1.1fr 1fr;
    gap: 20px;
    align-items: start;
  }
  @media (max-width: 800px) {
    .lobby {
      grid-template-columns: 1fr;
    }
  }
  section {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .presets {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-bottom: 10px;
  }
  .preset {
    padding: 12px 0;
    font-size: 1.05rem;
    font-variant-numeric: tabular-nums;
  }
  .rated-toggle {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    width: 100%;
    padding: 6px 8px;
    border-radius: 5px;
  }
  .row.join,
  .row.spectate {
    background: none;
    border: none;
    text-align: left;
    font: inherit;
    color: var(--text);
    cursor: pointer;
  }
  .row.join:hover,
  .row.spectate:hover {
    background: var(--surface-2);
    text-decoration: none;
  }
  .actions {
    display: flex;
    gap: 6px;
  }
  .challenge-form {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
    padding: 8px;
    margin: 0 8px 8px;
    background: var(--surface-2);
    border-radius: 6px;
    font-size: 0.9rem;
  }
  .challenge-form label {
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
  .note {
    color: var(--danger);
    font-size: 0.9rem;
  }
</style>
