<script lang="ts">
  import { classColor } from './review';

  // One classification glyph. Seven silhouettes — star, tick, disc, ring,
  // diamond, triangle, cross — so the classes stay apart when the colour is
  // lost to a monochrome display, a projector, or the reader's eyes.
  export let cls: string;
  export let size = 11;

  // Decorative by default: inside a move button the class is already in the
  // button's own label, and a second announcement would only be noise.
  export let label = '';
</script>

<svg
  class="mark"
  width={size}
  height={size}
  viewBox="0 0 12 12"
  style="color: {classColor(cls)}"
  role={label ? 'img' : undefined}
  aria-label={label || undefined}
  aria-hidden={label ? undefined : 'true'}
>
  {#if label}<title>{label}</title>{/if}
  {#if cls === 'brilliant'}
    <path
      d="M6 0.5 L7.35 4.65 L11.5 6 L7.35 7.35 L6 11.5 L4.65 7.35 L0.5 6 L4.65 4.65 Z"
      fill="currentColor"
    />
  {:else if cls === 'best'}
    <path
      d="M1.8 6.4 L4.7 9.4 L10.2 2.7"
      fill="none"
      stroke="currentColor"
      stroke-width="2.2"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  {:else if cls === 'excellent'}
    <circle cx="6" cy="6" r="4" fill="currentColor" />
  {:else if cls === 'good'}
    <circle
      cx="6"
      cy="6"
      r="3.6"
      fill="none"
      stroke="currentColor"
      stroke-width="1.7"
    />
  {:else if cls === 'inaccuracy'}
    <path
      d="M6 1.3 L10.7 6 L6 10.7 L1.3 6 Z"
      fill="none"
      stroke="currentColor"
      stroke-width="1.7"
      stroke-linejoin="round"
    />
  {:else if cls === 'mistake'}
    <path d="M6 1.1 L11.3 10.6 L0.7 10.6 Z" fill="currentColor" />
  {:else if cls === 'blunder'}
    <path
      d="M2.4 2.4 L9.6 9.6 M9.6 2.4 L2.4 9.6"
      fill="none"
      stroke="currentColor"
      stroke-width="2.4"
      stroke-linecap="round"
    />
  {:else}
    <!-- A class this build has not heard of: show that something was said
         about the move rather than pretending nothing was. -->
    <rect
      x="1.8"
      y="1.8"
      width="8.4"
      height="8.4"
      rx="1.5"
      fill="none"
      stroke="currentColor"
      stroke-width="1.6"
    />
  {/if}
</svg>

<style>
  .mark {
    flex: none;
    vertical-align: -1px;
  }
</style>
