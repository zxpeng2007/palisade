<script lang="ts">
  import { onMount } from 'svelte';
  import { account } from '../lib/session';
  import { mode, modeHash } from '../lib/mode';
  import { cooldown, resend, verifyToken } from '../lib/verify';

  /** Taken out of the hash by the router; empty if the link was mangled. */
  export let token: string;

  let status: 'working' | 'done' | 'failed' = 'working';
  let confirmed = ''; // the account the link belonged to, per the server
  let error = '';
  let busy = false;
  let said = '';

  // The link may well be opened in a browser signed in as nobody, or as
  // somebody else; only say "you" when it really is this session's account.
  $: mine = !!$account && confirmed === $account.username;

  async function doResend() {
    busy = true;
    said = '';
    try {
      await resend();
      said = $account.email
        ? `A new link is on its way to ${$account.email}.`
        : 'A new link is on its way.';
    } catch (e: any) {
      said = e.message;
    } finally {
      busy = false;
    }
  }

  onMount(async () => {
    if (!token) {
      status = 'failed';
      error = 'This link has no token in it — it may have been cut short by a mail client.';
      return;
    }
    try {
      confirmed = await verifyToken(token);
      status = 'done';
    } catch (e: any) {
      status = 'failed';
      error = e.message;
    }
  });
</script>

<div class="verify panel">
  {#if status === 'working'}
    <h1>Checking your link…</h1>
    <p class="dim">One moment.</p>
  {:else if status === 'done'}
    <h1>Address confirmed</h1>
    <p>
      {#if mine}
        <strong>{confirmed}</strong> is verified. Rated games, rated challenges
        and engine upgrades are open to you.
      {:else if confirmed}
        <strong>{confirmed}</strong> is verified. Sign in as that account and
        rated play is open.
      {:else}
        The address is verified. Sign in and rated play is open.
      {/if}
    </p>
    <p class="onward">
      {#if mine}
        <a href={modeHash($mode)}>Find a game →</a>
      {:else}
        <a href="#/login">Sign in →</a>
      {/if}
      <a href="#/fairplay">Fair play →</a>
    </p>
  {:else}
    <h1>That link did not work</h1>
    <p class="error">{error}</p>
    <p class="dim">
      Verification links are single use and expire. If you have already
      confirmed this address, nothing is wrong — carry on.
    </p>
    <p class="onward">
      {#if $account}
        <button on:click={doResend} disabled={busy || $cooldown > 0}>
          {$cooldown > 0 ? `Resend in ${$cooldown}s` : 'Send a new link'}
        </button>
        <a href={modeHash($mode)}>Back to the site →</a>
      {:else}
        <a href="#/login">Sign in to request a new one →</a>
      {/if}
    </p>
    {#if said}<p class="dim">{said}</p>{/if}
  {/if}
</div>

<style>
  .verify {
    max-width: 520px;
    margin: 40px auto 0;
  }
  h1 {
    font-size: 1.3rem;
  }
  .onward {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
    margin-bottom: 0;
    font-weight: 600;
  }
  .error {
    color: var(--danger);
  }
</style>
