<script lang="ts">
  import { send } from './ws';
  import { needSignIn } from './session';
  import { clockLabel } from './format';

  export let seeks: any[] = [];
  export let me: string | null = null;
  /** Which side of the site this list belongs to. */
  export let kind: 'human' | 'bot';
  export let title: string;
  export let empty: string;

  $: shown = seeks.filter((s) => (kind === 'bot' ? s.bot : !s.bot));

  // Accepting a seek means posting a matching one; the server pairs them.
  function join(s: any) {
    if (needSignIn() || s.username === me) return;
    send({ t: 'seek', rated: s.rated, clock: s.clock });
  }

  function cancel() {
    send({ t: 'seekCancel' });
  }
</script>

<div class="panel">
  <h2>{title}</h2>
  {#if shown.length === 0}
    <p class="dim">{empty}</p>
  {:else}
    {#each shown as s (s.username)}
      {#if s.username === me}
        <div class="row">
          <span class="who">
            <strong>{s.username}</strong>
            <span class="dim">({s.rating})</span>
            · {clockLabel(s.clock)} · {s.rated ? 'rated' : 'casual'}
            <span class="dim">— your seek</span>
          </span>
          <button on:click={cancel}>Cancel</button>
        </div>
      {:else}
        <button class="row join" on:click={() => join(s)}>
          <span class="who">
            <strong>{s.username}</strong>
            <span class="dim">({s.rating})</span>
            {#if s.bot && kind !== 'bot'}<span class="bot-tag">BOT</span>{/if}
            · {clockLabel(s.clock)} · {s.rated ? 'rated' : 'casual'}
          </span>
          <span class="dim">Join</span>
        </button>
      {/if}
    {/each}
  {/if}
</div>

<style>
  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    width: 100%;
    padding: 6px 8px;
    border-radius: 5px;
  }
  .row.join {
    background: none;
    border: none;
    text-align: left;
    font: inherit;
    color: var(--text);
    cursor: pointer;
  }
  .row.join:hover {
    background: var(--surface-2);
  }
  .who {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
