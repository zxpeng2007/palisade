<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import Title from '../lib/Title.svelte';
  import { titleName, titleRating } from '../lib/titles';

  export let name: string;

  let profile: any = null;
  let error = '';

  // A title is permanent and a rating is not, so a titled player can sit below
  // their own threshold. That is the system working, and the page has to say
  // so — otherwise a GM rated 2380 reads as a bug in the ladder.
  $: threshold = profile ? titleRating(profile.title) : null;
  $: fallen = threshold !== null && profile.rating < threshold;

  onMount(async () => {
    try {
      profile = await api('GET', '/api/user/' + encodeURIComponent(name));
    } catch (e: any) {
      error = e.message;
    }
  });

  // W/L over the recent games the profile endpoint returns. Aborted games
  // have no winner and count for neither side.
  $: record = tally(profile);

  function tally(p: any) {
    let w = 0;
    let l = 0;
    if (p) {
      for (const g of p.recent) {
        if (g.status !== 'finished' || !g.winner) continue;
        const winnerName = g.winner === 'first' ? g.p1 : g.p2;
        if (winnerName === p.username) w++;
        else l++;
      }
    }
    return { w, l };
  }

  function result(g: any): string {
    if (g.status !== 'finished' || !g.winner) return '–';
    const winnerName = g.winner === 'first' ? g.p1 : g.p2;
    return winnerName === profile.username ? 'W' : 'L';
  }

  function opponent(g: any): string {
    return g.p1 === profile.username ? g.p2 : g.p1;
  }

  function when(iso: string): string {
    if (!iso) return '';
    const d = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T') + 'Z');
    return isNaN(d.getTime()) ? iso : d.toLocaleDateString();
  }
</script>

{#if error}
  <p class="panel">Could not load profile: {error}</p>
{:else if !profile}
  <p class="dim">Loading profile…</p>
{:else}
  <div class="profile">
    <div class="panel head">
      <h1>
        <Title title={profile.title} />
        {profile.username}
        {#if profile.bot}<span class="bot-tag">BOT</span>{/if}
      </h1>
      <div class="stats">
        <div class="stat">
          <span class="value">
            {profile.rating}{profile.provisional ? '?' : ''}
          </span>
          <span class="dim">rating{profile.provisional ? ' (provisional)' : ''}</span>
        </div>
        <div class="stat">
          <span class="value">{profile.games}</span>
          <span class="dim">rated games</span>
        </div>
        <div class="stat">
          <span class="value">{record.w}–{record.l}</span>
          <span class="dim">recent W–L</span>
        </div>
      </div>

      {#if profile.title}
        <p class="titled">
          {#if profile.peak}
            <strong>{titleName(profile.title) || profile.title}</strong>, earned
            at a peak rating of <span class="peak">{profile.peak}</span> and held
            for life.
          {:else}
            <strong>{titleName(profile.title) || profile.title}</strong>, held
            for life.
          {/if}
          {#if fallen}
            The rating above is below the {threshold} that earned it: a title is
            awarded once and never revoked, so the two disagree and both are
            right.
          {/if}
          <a href="#/titles">How titles work →</a>
        </p>
      {/if}
    </div>

    <div class="panel">
      <h2>Recent games</h2>
      {#if profile.recent.length === 0}
        <p class="dim">No games yet.</p>
      {:else}
        <table>
          <tbody>
            {#each profile.recent as g (g.id)}
              <tr>
                <td class="res {result(g)}">{result(g)}</td>
                <td>
                  <a href={'#/game/' + g.id}>vs {opponent(g)}</a>
                </td>
                <td class="dim">{g.rated ? 'rated' : 'casual'}</td>
                <td class="dim">
                  {g.status === 'aborted' ? 'aborted' : g.reason}
                </td>
                <td class="dim">{when(g.created)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>
  </div>
{/if}

<style>
  .profile {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 720px;
    margin: 0 auto;
  }
  .head h1 {
    font-size: 1.4rem;
  }
  .stats {
    display: flex;
    gap: 36px;
  }
  .stat {
    display: flex;
    flex-direction: column;
  }
  .value {
    font-size: 1.3rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  /* Below the stats, because it explains one of them. */
  .titled {
    margin: 14px 0 0;
    padding-top: 12px;
    border-top: 1px solid var(--line);
    font-size: 0.9rem;
    color: var(--text-dim);
    max-width: 66ch;
  }
  .titled strong {
    color: var(--text);
  }
  .peak {
    color: var(--text);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  table {
    width: 100%;
    border-collapse: collapse;
  }
  td {
    padding: 4px 10px 4px 0;
    border-top: 1px solid var(--line);
  }
  tr:first-child td {
    border-top: none;
  }
  .res {
    font-weight: 700;
    width: 2em;
  }
  .res.W {
    color: var(--accent);
  }
  .res.L {
    color: var(--danger);
  }

  @media (max-width: 720px) {
    .head h1 {
      font-size: 1.25rem;
    }
    /* Three numbers with 36px between them is a desktop's spacing; on a phone
       they share the width evenly instead of leaving a gap at the end. */
    .stats {
      gap: 0;
      justify-content: space-between;
    }
    /* Each recent game is a link to that game, so the row is the target and
       the row is a finger tall. */
    td {
      padding: 11px 8px 11px 0;
    }
    td a {
      display: block;
    }
  }
</style>
