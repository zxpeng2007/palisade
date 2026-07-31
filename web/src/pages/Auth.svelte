<script lang="ts">
  import { login, register } from '../lib/session';

  let mode: 'login' | 'register' = 'login';
  let username = '';
  let password = '';
  let error = '';
  let busy = false;

  function switchTo(m: 'login' | 'register') {
    mode = m;
    error = '';
  }

  async function submit() {
    error = '';
    busy = true;
    try {
      if (mode === 'login') await login(username, password);
      else await register(username, password);
      location.hash = '#/';
    } catch (e: any) {
      error = e.message;
    } finally {
      busy = false;
    }
  }
</script>

<div class="auth panel">
  <div class="tabs">
    <button class:active={mode === 'login'} on:click={() => switchTo('login')}>
      Sign in
    </button>
    <button
      class:active={mode === 'register'}
      on:click={() => switchTo('register')}
    >
      Register
    </button>
  </div>

  <form on:submit|preventDefault={submit}>
    <label>
      Username
      <input
        bind:value={username}
        autocomplete="username"
        spellcheck="false"
        required
      />
    </label>
    {#if mode === 'register'}
      <p class="dim hint">2–20 characters: letters, digits, _ or -</p>
    {/if}
    <label>
      Password
      <input
        type="password"
        bind:value={password}
        autocomplete={mode === 'login' ? 'current-password' : 'new-password'}
        required
      />
    </label>
    {#if mode === 'register'}
      <p class="dim hint">At least 8 characters</p>
    {/if}

    {#if error}
      <p class="error">{error}</p>
    {/if}

    <button class="primary" type="submit" disabled={busy}>
      {mode === 'login' ? 'Sign in' : 'Create account'}
    </button>
  </form>
</div>

<style>
  .auth {
    max-width: 360px;
    margin: 40px auto 0;
  }
  .tabs {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
  }
  .tabs button {
    flex: 1;
    background: none;
    border: none;
    border-bottom: 2px solid var(--line);
    border-radius: 0;
    padding: 8px 0;
    color: var(--text-dim);
  }
  .tabs button.active {
    color: var(--text);
    border-bottom-color: var(--accent);
  }
  form {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 0.9rem;
    color: var(--text-dim);
  }
  .hint {
    margin: -6px 0 0;
    font-size: 0.8rem;
  }
  .error {
    color: var(--danger);
    margin: 0;
  }
</style>
