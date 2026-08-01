<script lang="ts">
  import { onMount } from 'svelte';
  import { send, subscribe } from '../lib/ws';
  import { account, needSignIn } from '../lib/session';
  import { PRESETS, clockLabel } from '../lib/format';
  import Challenges from '../lib/Challenges.svelte';
  import Leaderboard from '../lib/Leaderboard.svelte';
  import RatedNote from '../lib/RatedNote.svelte';
  import Seeks from '../lib/Seeks.svelte';
  import TopGames from '../lib/TopGames.svelte';

  // Human mode: this page shows what people are doing. Engines have their own
  // mode, and the lobby lists below filter them out rather than mixing both.
  let seeks: any[] = [];
  let rated = false;

  $: me = $account ? $account.username : null;
  $: mySeek = me ? seeks.find((s) => s.username === me) : null;

  function onLobby(msg: any) {
    seeks = msg.seeks ?? [];
  }

  function createSeek(p: (typeof PRESETS)[number]) {
    if (needSignIn()) return;
    send({
      t: 'seek',
      rated,
      clock: { initial: p.initial, increment: p.increment },
    });
  }

  function cancelSeek() {
    send({ t: 'seekCancel' });
  }

  onMount(() => subscribe('lobby', onLobby));
</script>

<div class="cols">
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
        <RatedNote action="seek" />
        {#if !me}
          <p class="dim signin">
            <a href="#/login">Sign in</a> to play — spectating is open to all.
          </p>
        {/if}
      {/if}
    </div>

    <Challenges />

    <Seeks
      {seeks}
      {me}
      kind="human"
      title="Open seeks"
      empty="No one is waiting. Create a seek above and the next arrival plays you."
    />
  </section>

  <section>
    <TopGames
      kind="human"
      empty="No games between people yet — the first one played will show up here."
    />
    <Leaderboard
      kind="human"
      empty="No one has finished a rated game yet. Play one and take the top spot."
    />
  </section>
</div>

<style>
  .cols {
    display: grid;
    grid-template-columns: 1.1fr 1fr;
    gap: 20px;
    align-items: start;
  }
  @media (max-width: 800px) {
    .cols {
      grid-template-columns: 1fr;
    }
  }
  section {
    display: flex;
    flex-direction: column;
    gap: 16px;
    min-width: 0;
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
  .signin {
    margin-bottom: 0;
  }
</style>
