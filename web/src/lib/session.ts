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

export async function login(username: string, password: string): Promise<void> {
  account.set(await api('POST', '/api/login', { username, password }));
  reconnect(); // the socket authenticates by cookie at handshake time
}

export async function register(
  username: string,
  password: string
): Promise<void> {
  account.set(await api('POST', '/api/register', { username, password }));
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
