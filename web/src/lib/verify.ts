/** Email verification: the three endpoints plus the resend cooldown.
 *
 * The cooldown is a store rather than component state because two places offer
 * the resend — the banner and the note beside rated play — and a resend from
 * one has to be visible in the other. The deadline lives in sessionStorage so
 * that reloading the page cannot conjure a button the server would refuse.
 */

import { writable } from 'svelte/store';
import { api } from './api';
import { refresh } from './session';

const COOLDOWN_MS = 60_000;
const KEY = 'palisade.resendUntil';

/** Seconds left before another verification mail may be requested. */
export const cooldown = writable(0);

let timer: ReturnType<typeof setInterval> | null = null;

function deadline(): number {
  try {
    return Number(sessionStorage.getItem(KEY)) || 0;
  } catch {
    // Storage can throw outright in private windows; no memory, no cooldown.
    return 0;
  }
}

function tick(): void {
  const left = Math.max(0, Math.ceil((deadline() - Date.now()) / 1000));
  cooldown.set(left);
  if (left === 0 && timer) {
    clearInterval(timer);
    timer = null;
  }
}

function start(): void {
  if (timer) return;
  timer = setInterval(tick, 1000);
  tick(); // stops the interval again straight away if nothing is pending
}

// A reload part-way through the minute picks the count back up.
start();

/** Ask for another verification link. 200 even if the address is already
 *  confirmed, so the caller need not special-case that. */
export async function resend(): Promise<void> {
  await api('POST', '/api/email/resend');
  try {
    sessionStorage.setItem(KEY, String(Date.now() + COOLDOWN_MS));
  } catch {
    // Forgetting the deadline only costs an early 4xx from the server.
  }
  start();
}

/** Redeem a token from a verification link; resolves to the account the link
 *  belonged to. The endpoint takes no session — links are routinely opened in
 *  a different browser from the one that signed up — so that name is the only
 *  thing that says whose address was just confirmed. */
export async function verifyToken(token: string): Promise<string> {
  const res = await api('POST', '/api/email/verify', { token });
  await refresh();
  return res && res.username ? String(res.username) : '';
}

/** Point the account at a different address; the password proves it is you. */
export async function changeEmail(email: string, password: string): Promise<void> {
  await api('POST', '/api/email/change', { email, password });
  await refresh();
}
