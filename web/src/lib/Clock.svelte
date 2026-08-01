<script lang="ts">
  import { onDestroy } from 'svelte';

  // Seconds remaining as last reported by the server; null = unknown
  // (finished games loaded from the database carry no clock values).
  export let time: number | null = null;
  // Whether this clock is the one ticking. False freezes the display.
  export let running = false;

  let base = 0;
  let at = 0;
  let now = 0;
  let raf = 0;

  // Re-stamp on every server state so local ticking always counts down from
  // the freshest value.
  $: {
    base = time ?? 0;
    at = performance.now();
    now = at;
  }

  function tick() {
    now = performance.now();
    raf = running ? requestAnimationFrame(tick) : 0;
  }

  $: if (running && time !== null) {
    if (!raf) raf = requestAnimationFrame(tick);
  } else if (raf) {
    cancelAnimationFrame(raf);
    raf = 0;
  }

  $: remaining =
    time === null ? null : Math.max(0, base - (running ? (now - at) / 1000 : 0));

  function fmt(s: number): string {
    const whole = Math.floor(s);
    const m = Math.floor(whole / 60);
    const sec = whole % 60;
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  }

  onDestroy(() => {
    if (raf) cancelAnimationFrame(raf);
  });
</script>

<div class="clock" class:low={remaining !== null && remaining < 20} class:running>
  {remaining === null ? '--:--' : fmt(remaining)}
</div>

<style>
  /* Tabular figures and a floor on the width together mean a tick can never
     change the size of this box — a clock that resizes sixty times a minute
     drags the whole column around with it. The floor is set in ch so it
     survives the larger type below. */
  .clock {
    font-variant-numeric: tabular-nums;
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--text-dim);
    background: var(--surface-2);
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 2px 12px;
    display: inline-block;
    min-width: 5.2ch;
    text-align: center;
  }
  /* On a phone the clock is the one number you glance at mid-move, and it is
     also what sets the height of the row it shares with the player's name. */
  @media (max-width: 720px) {
    .clock {
      font-size: 1.7rem;
      padding: 4px 14px;
      min-height: 44px;
    }
  }
  .clock.running {
    color: var(--text);
    border-color: var(--accent);
  }
  .clock.low {
    color: var(--danger);
  }
</style>
