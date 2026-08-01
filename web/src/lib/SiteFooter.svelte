<script lang="ts">
  import { showIntro } from './intro';

  const REPO = 'https://github.com/zxpeng2007/murus';
</script>

<footer>
  <span class="dim">murus — the wall game, for people and engines</span>
  <nav>
    <!-- First in the list: the rules are what a stranger needs before any of
         the rest of this means anything. -->
    <button class="linky" on:click={showIntro}>How to play</button>
    <a href="#/fairplay">Fair play</a>
    <a href="#/titles">Titles</a>
    <a href="#/engines">Engine API</a>
    <a href={REPO + '/blob/main/API.md'} target="_blank" rel="noopener">API.md</a>
    <a href={REPO} target="_blank" rel="noopener">Source</a>
  </nav>
</footer>

<style>
  footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px 20px;
    max-width: 1100px;
    margin: 0 auto;
    padding: 16px;
    border-top: 1px solid var(--line);
    font-size: 0.85rem;
  }
  nav {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
  }
  /* A button because it opens a dialog rather than going anywhere, styled as
     a link because that is what it is doing in this row. */
  .linky {
    background: none;
    border: 0;
    padding: 0;
    font: inherit;
    color: var(--accent);
    cursor: pointer;
  }
  .linky:hover {
    text-decoration: underline;
  }
</style>
