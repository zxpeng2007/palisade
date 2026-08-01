<script lang="ts">
  import { account, unverified } from './session';
  import { changeEmail, cooldown, resend } from './verify';

  // Dismissal is remembered per account for the browser session only: rated
  // play stays blocked until the address is confirmed, so the reminder is due
  // again next visit, but it should not follow you around all afternoon.
  const KEY = 'murus.verifyDismissed';

  let dismissedFor = read();
  let changing = false;
  let email = '';
  let password = '';
  let busy = false;
  let message = '';
  let error = '';

  $: show = unverified($account) && $account.username !== dismissedFor;

  function read(): string {
    try {
      return sessionStorage.getItem(KEY) ?? '';
    } catch {
      return '';
    }
  }

  function dismiss() {
    dismissedFor = $account ? $account.username : '';
    try {
      sessionStorage.setItem(KEY, dismissedFor);
    } catch {
      // Not remembering just means the banner returns on the next page load.
    }
  }

  async function doResend() {
    busy = true;
    message = '';
    error = '';
    try {
      await resend();
      message = `Link sent to ${$account.email}. It can take a minute to arrive.`;
    } catch (e: any) {
      error = e.message;
    } finally {
      busy = false;
    }
  }

  async function doChange() {
    busy = true;
    message = '';
    error = '';
    try {
      await changeEmail(email, password);
      message = `Address changed to ${email}. Check it for the link.`;
      changing = false;
      email = '';
      password = '';
    } catch (e: any) {
      error = e.message;
    } finally {
      busy = false;
    }
  }
</script>

{#if show}
  <div class="verify">
    <div class="top">
      <p class="say">
        <strong>Confirm your email address to play rated games.</strong>
        {#if $account.email}
          We sent a link to <span class="addr">{$account.email}</span>.
        {:else}
          Add an address below and we will send you a link.
        {/if}
        Casual games, spectating and the API work as normal meanwhile.
      </p>
      <div class="actions">
        {#if $account.email}
          <button on:click={doResend} disabled={busy || $cooldown > 0}>
            {$cooldown > 0 ? `Resend in ${$cooldown}s` : 'Resend link'}
          </button>
        {/if}
        <button class="quiet" on:click={() => (changing = !changing)}>
          {$account.email ? 'Wrong address?' : 'Add an address'}
        </button>
        <button class="close" on:click={dismiss} aria-label="Dismiss">×</button>
      </div>
    </div>

    {#if changing}
      <form on:submit|preventDefault={doChange}>
        <input
          type="email"
          bind:value={email}
          placeholder="you@example.com"
          autocomplete="email"
          required
        />
        <input
          type="password"
          bind:value={password}
          placeholder="Your password"
          autocomplete="current-password"
          required
        />
        <button class="primary" type="submit" disabled={busy}>Save address</button>
      </form>
    {/if}

    {#if message}<p class="msg">{message}</p>{/if}
    {#if error}<p class="err">{error}</p>{/if}
  </div>
{/if}

<style>
  .verify {
    max-width: 1100px;
    margin: 16px auto 0;
    padding: 10px 14px;
    background: var(--surface);
    border: 1px solid var(--line);
    border-left: 3px solid var(--accent);
    border-radius: 8px;
    font-size: 0.92rem;
  }
  .top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
  }
  .say {
    margin: 0;
    min-width: 0;
    max-width: 70ch;
  }
  .addr {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.9em;
    word-break: break-all;
  }
  .actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .quiet {
    background: none;
    border-color: transparent;
    color: var(--text-dim);
    padding-left: 4px;
    padding-right: 4px;
  }
  .close {
    background: none;
    border-color: transparent;
    color: var(--text-dim);
    font-size: 1.1rem;
    line-height: 1;
    padding: 2px 8px;
  }
  form {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;
  }
  form input {
    flex: 1 1 200px;
    min-width: 0;
  }
  .msg,
  .err {
    margin: 8px 0 0;
  }
  .err {
    color: var(--danger);
  }
</style>
