<script lang="ts">
  import { send } from './ws';
  import { needSignIn } from './session';
  import { flash } from './notify';
  import { PRESETS } from './format';
  import RatedNote from './RatedNote.svelte';

  /** Engines currently connected, from the lobby snapshot. */
  export let bots: any[] = [];
  export let me: string | null = null;

  // The challenge form opens under the engine it targets; only one at a time.
  let target: string | null = null;
  let preset = PRESETS[3];
  let rated = false;
  let color: 'random' | 'first' | 'second' = 'random';

  function toggle(name: string) {
    if (needSignIn()) return;
    target = target === name ? null : name;
  }

  function sendChallenge() {
    if (needSignIn() || !target) return;
    send({
      t: 'challenge',
      user: target,
      rated,
      clock: { initial: preset.initial, increment: preset.increment },
      color,
    });
    flash('Challenge sent to ' + target);
    target = null;
  }
</script>

<div class="panel">
  <h2>Online engines</h2>
  {#if bots.length === 0}
    <p class="dim">
      No engines are connected right now. Any account that has run
      <code>/api/bot/upgrade</code> and holds an open event stream appears here.
    </p>
  {:else}
    {#each bots as b (b.username)}
      <div class="row">
        <span class="who">
          <a href={'#/@/' + encodeURIComponent(b.username)}>{b.username}</a>
          <span class="bot-tag">BOT</span>
          <span class="dim">{b.rating}{b.provisional ? '?' : ''}</span>
        </span>
        <button disabled={me === b.username} on:click={() => toggle(b.username)}>
          Challenge
        </button>
      </div>
      {#if target === b.username}
        <div class="challenge-form">
          <label>
            Clock
            <select bind:value={preset}>
              {#each PRESETS as p (p.label)}
                <option value={p}>{p.label}</option>
              {/each}
            </select>
          </label>
          <label>
            <input type="checkbox" bind:checked={rated} /> Rated
          </label>
          <label>
            You play
            <select bind:value={color}>
              <option value="random">random</option>
              <option value="first">first</option>
              <option value="second">second</option>
            </select>
          </label>
          <button class="primary" on:click={sendChallenge}>Send</button>
          <button on:click={() => (target = null)}>Cancel</button>
          <div class="full"><RatedNote action="challenge" /></div>
        </div>
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
    padding: 6px 8px;
    border-radius: 5px;
  }
  .who {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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
  /* The rated note is a sentence, not a control: its own line under the row. */
  .full {
    flex: 1 0 100%;
  }
</style>
