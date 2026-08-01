<script lang="ts">
  import { account, unverified } from './session';
  import { cooldown, resend } from './verify';

  /** Which rated action is on offer here; only the first sentence differs. */
  export let action: 'seek' | 'challenge' | 'upgrade' = 'seek';

  const LEAD = {
    seek: 'Rated games need a verified email address.',
    challenge: 'Rated challenges need a verified email address.',
    upgrade: 'Declaring an engine account needs a verified email address.',
  };

  let busy = false;
  let said = '';

  // Nothing to say to a verified account, and nothing to say before we know
  // which account this is — a note that flickers in and out is worse than none.
  $: blocked = unverified($account);
  $: anonymous = $account === null;

  async function doResend() {
    busy = true;
    said = '';
    try {
      await resend();
      said = 'Sent.';
    } catch (e: any) {
      said = e.message;
    } finally {
      busy = false;
    }
  }
</script>

{#if blocked}
  <p class="note">
    {LEAD[action]}
    {#if $account.email}
      Open the link we sent to <span class="addr">{$account.email}</span>, or
      <button class="link" on:click={doResend} disabled={busy || $cooldown > 0}>
        {$cooldown > 0 ? `resend in ${$cooldown}s` : 'send another'}
      </button>.
    {:else}
      Add an address in the banner at the top of the page.
    {/if}
    {#if said}<span class="said">{said}</span>{/if}
  </p>
{:else if anonymous}
  <p class="note">
    {LEAD[action]} You choose one when you register; casual games do not need it.
  </p>
{/if}

<style>
  .note {
    margin: 6px 0 0;
    font-size: 0.85rem;
    color: var(--text-dim);
    max-width: 60ch;
  }
  .addr {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.9em;
    word-break: break-all;
  }
  /* A button, because it acts; styled as a link, because it reads mid-sentence. */
  .link {
    background: none;
    border: none;
    border-radius: 0;
    padding: 0;
    font: inherit;
    color: var(--accent);
    text-decoration: underline;
  }
  .link:disabled {
    color: var(--text-dim);
    text-decoration: none;
  }
  .said {
    color: var(--text);
  }
</style>
