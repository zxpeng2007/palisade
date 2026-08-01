<script lang="ts">
  import { mode } from './mode';

  // Anchors, not buttons: each half of the switch is a real link to the mode's
  // route, so it can be copied, opened in a new tab and bookmarked. The router
  // adopts whichever mode the hash names.
</script>

<nav class="switch" aria-label="Site mode">
  <a
    class="seg"
    class:on={$mode === 'humans'}
    href="#/"
    aria-current={$mode === 'humans' ? 'page' : undefined}
  >
    <svg class="glyph" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="9" cy="9" r="4.2" />
      <circle cx="16" cy="15" r="4.2" class="second" />
    </svg>
    <span class="text">
      <span class="title">Humans</span>
      <span class="sub">Lobby, ladder and the games people are playing</span>
    </span>
  </a>
  <a
    class="seg"
    class:on={$mode === 'engines'}
    href="#/engines"
    aria-current={$mode === 'engines' ? 'page' : undefined}
  >
    <svg class="glyph" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M9 7 4.5 12 9 17" />
      <path d="M15 7 19.5 12 15 17" />
    </svg>
    <span class="text">
      <span class="title">Engines</span>
      <span class="sub">The bot API, engine ladder and engine games</span>
    </span>
  </a>
</nav>

<style>
  .switch {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
    max-width: 1100px;
    margin: 0 auto;
    padding: 6px;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 12px;
  }
  .seg {
    display: flex;
    align-items: center;
    gap: 14px;
    min-width: 0; /* let the subtitle ellipsis instead of widening the grid */
    padding: 14px 18px;
    border-radius: 8px;
    color: var(--text-dim);
    border: 1px solid transparent;
  }
  .seg:hover {
    text-decoration: none;
    background: var(--surface-2);
    color: var(--text);
  }
  .seg.on {
    background: var(--surface-2);
    border-color: var(--accent);
    color: var(--text);
  }
  .text {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .title {
    font-size: 1.5rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    line-height: 1.15;
  }
  .seg.on .title {
    color: var(--accent);
  }
  .sub {
    font-size: 0.85rem;
    color: var(--text-dim);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .glyph {
    flex: none;
    width: 30px;
    height: 30px;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
    opacity: 0.85;
  }
  .seg.on .glyph {
    stroke: var(--accent);
    opacity: 1;
  }
  .glyph circle {
    fill: currentColor;
    stroke: none;
  }
  .seg.on .glyph circle {
    fill: var(--p1);
  }
  .seg.on .glyph circle.second {
    fill: var(--p2);
  }

  @media (max-width: 700px) {
    .seg {
      gap: 10px;
      padding: 10px 12px;
    }
    .title {
      font-size: 1.2rem;
    }
    .sub {
      display: none; /* two words each is still an obvious switch */
    }
    .glyph {
      width: 24px;
      height: 24px;
    }
  }
</style>
