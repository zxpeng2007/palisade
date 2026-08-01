<script lang="ts">
  import { onMount } from 'svelte';
  import { send, subscribe } from './ws';
  import { flash } from './notify';
  import { clockLabel } from './format';

  // Challenges aimed at me. They arrive on the personal channel in either
  // mode — a human can be challenged by an engine and the other way round —
  // so both the lobby and the engine page mount this panel.
  let incoming: any[] = [];

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

  function accept(c: any) {
    send({ t: 'accept', id: c.id });
    incoming = incoming.filter((x) => x.id !== c.id);
  }

  function decline(c: any) {
    send({ t: 'decline', id: c.id });
    incoming = incoming.filter((x) => x.id !== c.id);
  }

  onMount(() => subscribe('user', onUser));
</script>

{#if incoming.length > 0}
  <div class="panel">
    <h2>Challenges</h2>
    {#each incoming as c (c.id)}
      <div class="row">
        <span class="what">
          <strong>{c.challenger}</strong>
          · {clockLabel(c.clock)} · {c.rated ? 'rated' : 'casual'}
          · they play {c.color}
        </span>
        <span class="actions">
          <button class="primary" on:click={() => accept(c)}>Accept</button>
          <button on:click={() => decline(c)}>Decline</button>
        </span>
      </div>
    {/each}
  </div>
{/if}

<style>
  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
    padding: 6px 0;
  }
  .what {
    min-width: 0;
  }
  .actions {
    display: flex;
    gap: 6px;
  }
</style>
