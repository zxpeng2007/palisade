<script lang="ts">
  const REPO = 'https://github.com/zxpeng2007/palisade';
</script>

<footer>
  <span class="dim">palisade — the wall game, for people and engines</span>
  <nav>
    <a href="#/fairplay">Fair play</a>
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
</style>
