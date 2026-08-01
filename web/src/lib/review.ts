/** Game review — the stored analysis job of API.md's "Game review".
 *
 * Analysis is minutes of engine time, so the server runs it as a job and
 * keeps the answer forever: a finished game cannot change, so a review never
 * needs recomputing. The client therefore asks once, offers to start one when
 * there is none, and polls only while a job is actually in flight.
 */
import { api } from './api';

export interface ReviewMove {
  ply: number;
  move: string;
  best: string;
  eval: number;
  loss: number;
  class: string;
}

export interface Review {
  status: 'pending' | 'running' | 'done' | 'failed';
  engine?: string;
  sims?: number;
  progress?: number; // fraction of positions analysed, while running
  accuracy?: { first: number; second: number };
  moves?: ReviewMove[];
  error?: string;
}

const STATUSES = ['pending', 'running', 'done', 'failed'];

/** The seven classes of API.md, best first. */
export const CLASSES = [
  'brilliant',
  'best',
  'excellent',
  'good',
  'inaccuracy',
  'mistake',
  'blunder',
];

export const CLASS_LABEL: Record<string, string> = {
  brilliant: 'Brilliant',
  best: 'Best',
  excellent: 'Excellent',
  good: 'Good',
  inaccuracy: 'Inaccuracy',
  mistake: 'Mistake',
  blunder: 'Blunder',
};

/** What each class actually claims, in the engine's own terms. Shown beside
 *  the verdict so a label never has to be taken on faith. */
export const CLASS_NOTE: Record<string, string> = {
  brilliant: 'the engine agreed — and its own policy had nearly dismissed it',
  best: 'the move the engine chose too',
  excellent: 'gave up almost nothing',
  good: 'a small concession',
  inaccuracy: 'a noticeable concession',
  mistake: 'a costly move',
  blunder: 'a decisive error',
};

/** The win-probability bands of API.md, in order. `blunder` is everything
 *  past 0.20; `best` and `brilliant` are agreements, not bands, so they sit
 *  at the bottom of the first segment. */
export const BANDS = [
  { upto: 0.02, cls: 'excellent' },
  { upto: 0.05, cls: 'good' },
  { upto: 0.1, cls: 'inaccuracy' },
  { upto: 0.2, cls: 'mistake' },
  { upto: 1.0, cls: 'blunder' },
];

/** CSS colour for a class marker. An unrecognised name — a newer server with
 *  a class this build has never heard of — falls back to neutral rather than
 *  interpolating whatever arrived into a style attribute. */
export function classColor(cls: string): string {
  return CLASSES.indexOf(cls) >= 0 ? `var(--cls-${cls})` : 'var(--text-dim)';
}

export function classLabel(cls: string): string {
  return CLASS_LABEL[cls] ?? cls ?? '';
}

/** Where a loss sits on the band ruler, 0..1.
 *
 *  The ruler's scale is the bands themselves, one equal segment each: on a
 *  linear 0..1 axis the four bands that decide most games would share the
 *  first fifth of the width and every ordinary move would look identical. */
export function bandPos(loss: number): number {
  const x = Math.max(0, Math.min(1, loss || 0));
  let lo = 0;
  for (let i = 0; i < BANDS.length; i++) {
    const hi = BANDS[i].upto;
    if (x <= hi || i === BANDS.length - 1) {
      return (i + (x - lo) / (hi - lo)) / BANDS.length;
    }
    lo = hi;
  }
  return 1;
}

/** Position value, first player's point of view: "+0.31", "-0.31", "0.00". */
export function evalText(v: number): string {
  if (!Number.isFinite(v)) return '?';
  const r = Math.round(v * 100) / 100;
  return r > 0 ? `+${r.toFixed(2)}` : r.toFixed(2);
}

/** A 0..1 probability as a percentage, keeping a decimal while the number is
 *  small enough that rounding would print a bare "0%" for a real loss. */
export function pctText(x: number): string {
  if (!Number.isFinite(x)) return '?';
  const p = Math.max(0, x) * 100;
  return (p < 9.95 ? p.toFixed(1) : String(Math.round(p))) + '%';
}

/** Accuracy arrives already in percent (82.4). */
export function accuracyText(a: number): string {
  return Number.isFinite(a) ? `${(Math.round(a * 10) / 10).toFixed(1)}%` : '—';
}

export function isRunning(r: Review | null): boolean {
  return !!r && (r.status === 'pending' || r.status === 'running');
}

function shaped(r: any): r is Review {
  return !!r && typeof r === 'object' && STATUSES.indexOf(r.status) >= 0;
}

/** The stored review, or null when this game has never been reviewed.
 *
 *  Nothing stored is the ordinary case rather than a failure. A server may
 *  say so with a 404 — which is also what a bad game id returns — or with a
 *  body carrying none of the four statuses the contract defines. Both mean
 *  the same thing here: offer the button, and let the POST report the real
 *  reason if there is one. */
export async function fetchReview(id: string): Promise<Review | null> {
  try {
    const r = await api('GET', `/api/game/${id}/review`);
    return shaped(r) ? r : null;
  } catch (e: any) {
    if (e && e.status === 404) return null;
    throw e;
  }
}

/** Start a review, or pick up the one already running or stored. */
export async function startReview(id: string): Promise<Review> {
  const r = await api('POST', `/api/game/${id}/review`);
  if (!shaped(r)) throw new Error('the server did not return a review');
  return r;
}

/** Poll while the job is pending or running; stop for good once it is done,
 *  has failed, or the caller unmounts.
 *
 *  A hidden tab polls nothing — a progress bar nobody is looking at is not
 *  worth a request every two seconds for two minutes — and catches up the
 *  moment it comes back. A single failed poll is a blip on a phone changing
 *  networks, so only a run of them gives up.
 */
export function watchReview(
  id: string,
  onState: (r: Review) => void,
  onError: (msg: string) => void,
  ms = 2000
): () => void {
  let stopped = false;
  let fails = 0;
  let timer: ReturnType<typeof setTimeout>;

  const again = () => {
    if (!stopped) timer = setTimeout(tick, ms);
  };

  const tick = async () => {
    if (stopped) return;
    if (document.hidden) return again();
    try {
      const r = await fetchReview(id);
      if (stopped) return;
      fails = 0;
      if (r) {
        onState(r);
        if (!isRunning(r)) {
          stopped = true;
          return;
        }
      }
    } catch (e: any) {
      if (stopped) return;
      if (++fails >= 3) {
        stopped = true;
        // Three misses in a row is the connection, not the job: the review is
        // still running on the server and it is the asking that has stopped,
        // so say that rather than handing over a bare "Failed to fetch".
        const why = e && e.message ? ` (${e.message})` : '';
        const on = 'The review carries on there — ask again to pick it up.';
        onError(`Lost contact with the server${why}. ${on}`);
        return;
      }
    }
    again();
  };

  const wake = () => {
    if (stopped || document.hidden) return;
    clearTimeout(timer); // back in view: show where the job got to, now
    tick();
  };

  document.addEventListener('visibilitychange', wake);
  again();

  return () => {
    stopped = true;
    clearTimeout(timer);
    document.removeEventListener('visibilitychange', wake);
  };
}
