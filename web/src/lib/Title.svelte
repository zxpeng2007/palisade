<script lang="ts">
  import { titleName } from './titles';

  /** A player object's `title`: GM, IM, FM, CM — or null, which is everybody.
   *  Untitled must cost nothing at all, so the component renders no element,
   *  no wrapper and no spacing when there is no title to show. */
  export let title: string | null | undefined = null;

  $: name = titleName(title);
</script>

{#if title}<abbr class="title" title={name || undefined}>{title}</abbr>{/if}

<style>
  /* Chess convention: the title is short, bold, coloured, and sits immediately
     before the name as part of it — text, not a chip. That is deliberately not
     how the BOT tag reads (an outlined green box after the name), because the
     two say different kinds of thing: a title is something a player earned,
     BOT is what a player is. Gold is used nowhere else on the site, so neither
     can be mistaken for the accent that means live/yours/won either.

     Sized in em so it stays in proportion whether it precedes a leaderboard
     row, a seek, or the name in a profile heading. */
  .title {
    color: var(--title);
    font-size: 0.8em;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-decoration: none;
    white-space: nowrap;
    cursor: help;
  }
</style>
