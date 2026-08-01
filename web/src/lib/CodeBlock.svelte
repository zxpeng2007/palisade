<script lang="ts">
  import { onDestroy } from 'svelte';

  export let code: string;
  /** Shown on the block's header bar, e.g. "shell" or "python". */
  export let label = '';

  let state: 'idle' | 'copied' | 'failed' = 'idle';
  let timer: ReturnType<typeof setTimeout> | null = null;

  // navigator.clipboard only exists in a secure context; the textarea trick
  // keeps the button honest when the page is served over plain http.
  function legacyCopy(text: string): boolean {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '0';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch {
      ok = false;
    }
    document.body.removeChild(ta);
    return ok;
  }

  async function copy() {
    let ok = false;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(code);
        ok = true;
      } else {
        ok = legacyCopy(code);
      }
    } catch {
      ok = legacyCopy(code);
    }
    state = ok ? 'copied' : 'failed';
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      state = 'idle';
    }, 1800);
  }

  onDestroy(() => {
    if (timer) clearTimeout(timer);
  });
</script>

<div class="block">
  <div class="bar">
    <span class="label">{label}</span>
    <button class="copy" class:done={state === 'copied'} on:click={copy}>
      {#if state === 'copied'}
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 8.5 6 12l7.5-8" /></svg>
        Copied
      {:else if state === 'failed'}
        Press ⌘/Ctrl+C
      {:else}
        Copy
      {/if}
    </button>
  </div>
  <pre><code>{code}</code></pre>
</div>

<style>
  .block {
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 7px;
    overflow: hidden;
    margin: 0 0 12px;
  }
  .bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 4px 6px 4px 12px;
    background: var(--surface-2);
    border-bottom: 1px solid var(--line);
  }
  .label {
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-dim);
  }
  .copy {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 2px 9px;
    font-size: 0.8rem;
    background: transparent;
  }
  .copy.done {
    color: var(--accent);
    border-color: var(--accent);
  }
  .copy svg {
    width: 12px;
    height: 12px;
    fill: none;
    stroke: currentColor;
    stroke-width: 2.2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  pre {
    margin: 0;
    padding: 12px;
    overflow-x: auto; /* long curl lines scroll here, not the page */
  }
  /* A whole listing, not an inline literal: drop the chip styling. */
  code {
    font-size: 0.82rem;
    line-height: 1.5;
    white-space: pre;
    background: none;
    padding: 0;
  }
</style>
