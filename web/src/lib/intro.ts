/** Whether the newcomer's introduction has been seen.
 *
 * Kept in localStorage rather than on the account, deliberately: the people
 * who most need the rules are the ones who have not signed up yet, and asking
 * them to register before the site explains itself has the order backwards.
 *
 * Versioned so the introduction can be shown again if it ever changes
 * materially — but only then. Being taught the same thing twice is its own
 * kind of insult.
 */
import { writable } from 'svelte/store';

const KEY = 'murus.intro.seen';
const VERSION = '1';

function seen(): boolean {
  try {
    return localStorage.getItem(KEY) === VERSION;
  } catch {
    // Private browsing with storage disabled: show it, and accept that it
    // will be shown again next time. Better than failing to explain the game.
    return false;
  }
}

function remember(): void {
  try {
    localStorage.setItem(KEY, VERSION);
  } catch {
    /* nothing to do; see above */
  }
}

export const introOpen = writable(false);

/** Open it on a first visit. Called once, from the app shell. */
export function offerIntro(): void {
  if (!seen()) introOpen.set(true);
}

/** Open it because someone asked — from a "how to play" link. */
export function showIntro(): void {
  introOpen.set(true);
}

export function closeIntro(): void {
  remember();
  introOpen.set(false);
}
