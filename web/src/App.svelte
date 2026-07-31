<script lang="ts">
  import { onMount } from 'svelte';
  import { account, boot, logout } from './lib/session';
  import { connect, subscribe } from './lib/ws';
  import Lobby from './pages/Lobby.svelte';
  import Game from './pages/Game.svelte';
  import Auth from './pages/Auth.svelte';
  import Profile from './pages/Profile.svelte';

  interface Route {
    page: 'lobby' | 'login' | 'game' | 'profile';
    id?: string;
    name?: string;
  }

  function parse(hash: string): Route {
    const h = hash.replace(/^#/, '') || '/';
    let m: RegExpMatchArray | null;
    if ((m = h.match(/^\/game\/([^/]+)$/))) return { page: 'game', id: m[1] };
    if ((m = h.match(/^\/@\/([^/]+)$/)))
      return { page: 'profile', name: decodeURIComponent(m[1]) };
    if (h === '/login') return { page: 'login' };
    return { page: 'lobby' };
  }

  let route: Route = parse(location.hash);

  onMount(() => {
    boot();
    connect();
    const onHash = () => (route = parse(location.hash));
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
    location.hash = '#/';
  }
</script>

<header>
  <a class="brand" href="#/">palisade<span class="brand-dot">.</span></a>
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
  {:else}
    <Lobby />
  {/if}
</main>

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
  main {
    max-width: 1100px;
    margin: 0 auto;
    padding: 20px 16px 48px;
  }
</style>
