import { writable } from 'svelte/store';

/** One transient message line, shown by App as a toast.
 *
 * Challenges, seeks and socket errors all arrive on the personal channel and
 * can land while any page is up, so the toast lives above the router rather
 * than being re-implemented per page.
 */
export const note = writable('');

let timer: ReturnType<typeof setTimeout> | null = null;

export function flash(message: string, ms = 4000): void {
  note.set(message);
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {
    timer = null;
    note.set('');
  }, ms);
}
