/** The title system, as API.md defines it.
 *
 *  The badge, the profile line and the explainer page all read from here, so
 *  the four numbers are written once: an explainer whose thresholds drifted
 *  from the server's would be worse than no explainer at all.
 */

export type TitleCode = 'GM' | 'IM' | 'FM' | 'CM';

export interface TitleDef {
  code: TitleCode;
  /** What the abbreviation stands for, spelled out. */
  name: string;
  /** The established rating that earns it. */
  rating: number;
}

/** Highest first — the order they are worth reading in. */
export const TITLES: TitleDef[] = [
  { code: 'GM', name: 'Grandmaster', rating: 2500 },
  { code: 'IM', name: 'International Master', rating: 2400 },
  { code: 'FM', name: 'FIDE Master', rating: 2300 },
  { code: 'CM', name: 'Candidate Master', rating: 2200 },
];

/** A rating deviation at or below this is established. The site already calls
 *  the same thing non-provisional; a title needs it. */
export const ESTABLISHED_RD = 110;

function find(code: string | null | undefined): TitleDef | null {
  if (!code) return null;
  for (const t of TITLES) if (t.code === code) return t;
  return null;
}

/** "Grandmaster" for GM, and '' for a code this build has never heard of — an
 *  unknown title still renders as itself rather than vanishing. */
export function titleName(code: string | null | undefined): string {
  const t = find(code);
  return t ? t.name : '';
}

/** The rating that earns the title, or null when we do not know it. */
export function titleRating(code: string | null | undefined): number | null {
  const t = find(code);
  return t ? t.rating : null;
}
