/** Small formatters shared by the lobby, the engine page and the profile. */

export type Speed = 'bullet' | 'blitz' | 'rapid' | 'classical';

/** Display order for speed groups — fastest first, as on the server. */
export const SPEEDS: Speed[] = ['bullet', 'blitz', 'rapid', 'classical'];

export const SPEED_LABEL: Record<string, string> = {
  bullet: 'Bullet',
  blitz: 'Blitz',
  rapid: 'Rapid',
  classical: 'Classical',
};

export interface Clock {
  initial: number;
  increment: number;
}

/** The offered time controls, one per speed band and then some: 1+0 is bullet,
 *  3+0/3+2/5+3 blitz, 10+0/15+10 rapid. */
export const PRESETS = [
  { label: '1+0', initial: 60, increment: 0 },
  { label: '3+0', initial: 180, increment: 0 },
  { label: '3+2', initial: 180, increment: 2 },
  { label: '5+3', initial: 300, increment: 3 },
  { label: '10+0', initial: 600, increment: 0 },
  { label: '15+10', initial: 900, increment: 10 },
];

/** "5+3" — the same rendering as palisade.speed.label on the server. */
export function clockLabel(c: Clock): string {
  if (!c) return '';
  const minutes = c.initial / 60;
  const shown = Number.isInteger(minutes) ? minutes : Math.round(minutes * 10) / 10;
  return `${shown}+${c.increment}`;
}

/** How a finished game ended, in words. */
export function reasonText(reason: string): string {
  if (reason === 'mate') return 'reached the goal';
  if (reason === 'resign') return 'resigned';
  if (reason === 'timeout') return 'on time';
  if (reason === 'abort') return 'aborted';
  return reason ?? '';
}

/** Compact age of a server timestamp ("2026-08-01 12:04:11", UTC). */
export function timeAgo(stamp: string): string {
  if (!stamp) return '';
  const d = new Date(stamp.includes('T') ? stamp : stamp.replace(' ', 'T') + 'Z');
  const secs = (Date.now() - d.getTime()) / 1000;
  if (isNaN(secs)) return '';
  if (secs < 60) return 'just now';
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  if (secs < 86400 * 30) return `${Math.floor(secs / 86400)}d ago`;
  return d.toLocaleDateString();
}
