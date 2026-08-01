import { writable } from 'svelte/store';

/** Humans or engines: a site-wide mode, not a page.
 *
 * The choice is persisted so returning to the bare URL puts you back where you
 * work, and mirrored in the hash so a link can point at either side.
 */
export type Mode = 'humans' | 'engines';

const KEY = 'murus.mode';

function stored(): Mode {
  try {
    return localStorage.getItem(KEY) === 'engines' ? 'engines' : 'humans';
  } catch {
    // Storage can throw outright in private windows; the default is fine.
    return 'humans';
  }
}

export const mode = writable<Mode>(stored());

export function setMode(m: Mode): void {
  mode.set(m);
  try {
    localStorage.setItem(KEY, m);
  } catch {
    // Not being able to remember the choice is not worth an error.
  }
}

export function modeHash(m: Mode): string {
  return m === 'engines' ? '#/engines' : '#/';
}

/** True when the visitor arrived at the bare site and last used engine mode,
 *  in which case the router sends them there instead of the human lobby. */
export function prefersEnginesHome(): boolean {
  return stored() === 'engines';
}
