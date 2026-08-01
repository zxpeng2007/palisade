/** Board geometry, shared by the playable board and the notation diagram.
 *
 * Kept in one place so the picture in the API docs is drawn by exactly the
 * code that draws the game: a notation explainer that disagrees with the
 * board is worse than no explainer at all.
 */

export const FILES = 'abcdefghi';

export const CELL = 50; // square side
export const GAP = 10; // gutter between squares — also the wall thickness
export const M = 28; // margin holding the coordinate labels
export const STEP = CELL + GAP;
export const SPAN = 9 * CELL + 8 * GAP;
export const SIZE = SPAN + 2 * M;

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Top-left corner of a square token ("e2").
 *
 * File a is the leftmost column and rank 1 is Player 1's home rank, drawn at
 * the bottom — unless `flip` seats Player 2 at the bottom instead.
 */
export function squareXY(token: string, flip = false): { x: number; y: number } {
  const f = FILES.indexOf(token[0]);
  const r = +token.slice(1) - 1;
  return { x: M + f * STEP, y: M + (flip ? r : 8 - r) * STEP };
}

/** Rect covering a wall token.
 *
 * `h<file><rank>` lies on the edge between <rank> and <rank>+1, spanning files
 * <file> and <file>+1; `v<file><rank>` lies on the edge between <file> and
 * <file>+1, spanning ranks <rank> and <rank>+1. Either way the anchor square
 * is <file><rank> and the wall runs along its upper (h) or right (v) edge.
 */
export function wallGeom(token: string, flip = false): Rect {
  const f = FILES.indexOf(token[1]);
  const r = +token.slice(2) - 1; // the lower of the two ranks touching the wall
  const topY = M + (flip ? r : 7 - r) * STEP; // screen-top cell of the pair
  if (token[0] === 'h') {
    return { x: M + f * STEP, y: topY + CELL, w: 2 * CELL + GAP, h: GAP };
  }
  return { x: M + f * STEP + CELL, y: topY, w: GAP, h: 2 * CELL + GAP };
}

/** Centre of the cross point a wall token hangs off — the corner shared by its
 *  anchor square and the three squares diagonally around it. */
export function wallCross(token: string, flip = false): { cx: number; cy: number } {
  const f = FILES.indexOf(token[1]);
  const r = +token.slice(2) - 1;
  const topY = M + (flip ? r : 7 - r) * STEP;
  return { cx: M + f * STEP + CELL + GAP / 2, cy: topY + CELL + GAP / 2 };
}

/** Pawn destinations are 2 chars ("e2"); wall tokens are 3 ("hd3"). Testing
 *  the first character is not enough: "h4" is a pawn move to file h. */
export function isWall(token: string): boolean {
  return token.length === 3;
}
