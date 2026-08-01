<script lang="ts">
  import { onMount } from 'svelte';
  import { account, boot, logout } from './lib/session';
  import { mode, modeHash, prefersEnginesHome, setMode } from './lib/mode';
  import { note } from './lib/notify';
  import { connect, subscribe } from './lib/ws';
  import ModeSwitch from './lib/ModeSwitch.svelte';
  import Lobby from './pages/Lobby.svelte';
  import Engines from './pages/Engines.svelte';
  import Game from './pages/Game.svelte';
  import Auth from './pages/Auth.svelte';
  import Profile from './pages/Profile.svelte';

  interface Route {
    page: 'lobby' | 'engines' | 'login' | 'game' | 'profile';
    id?: string;
    name?: string;
  }

  function parse(hash: string): Route {
    const h = hash.replace(/^#/, '') || '/';
    let m: RegExpMatchArray | null;
    if ((m = h.match(/^\/game\/([^/]+)$/))) return { page: 'game', id: m[1] };
    if ((m = h.match(/^\/@\/([^/]+)$/))) {
      // A malformed percent-escape in a pasted URL must not crash the app.
      try {
        return { page: 'profile', name: decodeURIComponent(m[1]) };
      } catch {
        return { page: 'lobby' };
      }
    }
    if (h === '/engines') return { page: 'engines' };
    if (h === '/login') return { page: 'login' };
    return { page: 'lobby' };
  }

  let route: Route = parse(location.hash);

  // The two landing routes *are* the mode; the game, profile and sign-in pages
  // sit inside whichever mode you came from and leave it alone.
  function adoptMode(r: Route): void {
    if (r.page === 'lobby') setMode('humans');
    else if (r.page === 'engines') setMode('engines');
  }

  onMount(() => {
    // A bare link to the site puts a returning engine author back in engine
    // mode. An explicit #/ always means the human lobby, so a shared link
    // lands where its author meant it to.
    if (location.hash === '' && prefersEnginesHome()) {
      location.replace(location.pathname + location.search + '#/engines');
    }
    route = parse(location.hash);
    adoptMode(route);

    boot();
    connect();
    const onHash = () => {
      route = parse(location.hash);
      adoptMode(route);
    };
    window.addEventListener('hashchange', onHash);
    // gameStart arrives on the personal channel no matter which page is up:
    // being paired (seek matched, challenge accepted) takes you to the game.
    const unsub = subscribe('user', (msg) => {
      if (msg.t === 'gameStart' && msg.game && msg.game.id) {
        location.hash = '#/game/' + msg.game.id;
      }
    });
    return () => {
      window.removeEventListener('hashchange', onHash);
      unsub();
    };
  });

  async function signOut() {
    await logout();
    location.hash = modeHash($mode);
  }
</script>

<header>
  <a class="brand" href={modeHash($mode)}>palisade<span class="brand-dot">.</span></a>
  <nav>
    {#if $account}
      <a href={'#/@/' + $account.username}>{$account.username}</a>
      <span class="rating dim">{$account.rating}</span>
      <button on:click={signOut}>Sign out</button>
    {:else if $account === null}
      <a href="#/login">Sign in</a>
    {/if}
  </nav>
</header>

<div class="modebar">
  <ModeSwitch />
</div>

<main>
  {#if route.page === 'game'}
    {#key route.id}
      <Game id={route.id} />
    {/key}
  {:else if route.page === 'login'}
    <Auth />
  {:else if route.page === 'profile'}
    {#key route.name}
      <Profile name={route.name} />
    {/key}
  {:else if route.page === 'engines'}
    <Engines />
  {:else}
    <Lobby />
  {/if}
</main>

{#if $note}
  <div class="toast">{$note}</div>
{/if}

<style>
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    border-bottom: 1px solid var(--line);
    background: var(--surface);
  }
  .brand {
    color: var(--text);
    font-size: 1.15rem;
    font-weight: 700;
    letter-spacing: 0.02em;
  }
  .brand:hover {
    text-decoration: none;
    color: var(--accent);
  }
  .brand-dot {
    color: var(--accent);
  }
  nav {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .modebar {
    padding: 16px 16px 0;
  }
  main {
    max-width: 1100px;
    margin: 0 auto;
    padding: 20px 16px 48px;
  }
  .toast {
    position: fixed;
    left: 50%;
    bottom: 18px;
    transform: translateX(-50%);
    max-width: calc(100vw - 32px);
    padding: 8px 16px;
    background: var(--surface-2);
    border: 1px solid var(--line);
    border-left: 3px solid var(--accent);
    border-radius: 6px;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
    font-size: 0.9rem;
  }
</style>
