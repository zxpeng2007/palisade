import { get, writable } from 'svelte/store';
import { api } from './api';
import { reconnect } from './ws';

export interface Account {
  id: number;
  username: string;
  bot: boolean;
  rating: number;
  rd: number;
  games: number;
  /** GM, IM, FM or CM; null for the untitled, which is everybody so far. */
  title?: string | null;
  /** Null on accounts that predate verification; those are verified anyway. */
  email: string | null;
  emailVerified: boolean;
}

/** undefined = not yet checked; null = signed out. */
export const account = writable<Account | null | undefined>(undefined);

/** Called once on boot: adopt an existing session cookie if there is one. */
export async function boot(): Promise<void> {
  try {
    account.set(await api('GET', '/api/account'));
  } catch {
    account.set(null);
  }
}

/** Re-read the account after the server changed something about it — an
 *  address verified or swapped. Unlike boot() a failure here leaves the
 *  signed-in state alone: a blip on this call is not a sign-out. */
export async function refresh(): Promise<void> {
  try {
    account.set(await api('GET', '/api/account'));
  } catch {
    // Keep whatever we last knew; the next page load will settle it.
  }
}

/** True when the server will refuse rated play and bot upgrades for want of a
 *  confirmed address. Only an explicit false counts, so a grandfathered
 *  account (no address, verified true) and any server that does not send the
 *  field at all are both left alone — the UI never invents a block. */
export function unverified(a: Account | null | undefined): boolean {
  return !!a && a.emailVerified === false;
}

export async function login(username: string, password: string): Promise<void> {
  account.set(await api('POST', '/api/login', { username, password }));
  reconnect(); // the socket authenticates by cookie at handshake time
}

export async function register(
  username: string,
  password: string,
  email: string
): Promise<void> {
  account.set(await api('POST', '/api/register', { username, password, email }));
  reconnect();
}

/** Guard for actions that need an account: routes to sign-in and returns true
 *  when the caller should bail out. Spectating stays open to everyone. */
export function needSignIn(): boolean {
  if (get(account)) return false;
  location.hash = '#/login';
  return true;
}

export async function logout(): Promise<void> {
  try {
    await api('POST', '/api/logout');
  } finally {
    account.set(null);
    reconnect();
  }
}
