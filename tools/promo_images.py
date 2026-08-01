"""Generate the link-preview image and promotional screenshots.

Everything here is drawn from the live site or from a real recorded game --
no mock-ups. A promotional image of a position that never occurred would be
the same lie as a screenshot with invented numbers in it, and the real games
are more interesting anyway.

    python tools/promo_images.py --out promo/
"""

from __future__ import annotations

import argparse
import json
import pathlib
import urllib.request

# Geometry, matching web/src/lib/geometry.ts exactly. Duplicated rather than
# imported because that module is TypeScript; the constants are pinned by the
# board tests on both sides.
CELL, GAP, M = 50, 10, 28
STEP = CELL + GAP
SPAN = 9 * CELL + 8 * GAP
SIZE = SPAN + 2 * M
FILES = "abcdefghi"

BG = "#161512"
SURFACE = "#201f1c"
LINE = "#383632"
TEXT = "#dad7d1"
DIM = "#918d85"
ACCENT = "#7fa650"
P1, P2, WALL, CELLC = "#e0a458", "#6aa1d8", "#b98a52", "#34322d"


def square_xy(token: str) -> tuple[int, int]:
    f = FILES.index(token[0])
    r = int(token[1:]) - 1
    return M + f * STEP, M + (8 - r) * STEP


def wall_rect(token: str) -> tuple[int, int, int, int]:
    f = FILES.index(token[1])
    r = int(token[2:]) - 1
    top = M + (7 - r) * STEP
    if token[0] == "h":
        return M + f * STEP, top + CELL, 2 * CELL + GAP, GAP
    return M + f * STEP + CELL, top, GAP, 2 * CELL + GAP


def board_svg(view: dict, size: int) -> str:
    parts = [f'<svg viewBox="0 0 {SIZE} {SIZE}" width="{size}" height="{size}" '
             'xmlns="http://www.w3.org/2000/svg">']
    for r in range(9):
        for f in range(9):
            parts.append(
                f'<rect x="{M + f * STEP}" y="{M + r * STEP}" width="{CELL}" '
                f'height="{CELL}" rx="3" fill="{CELLC}"/>')
    for t in list(view["wallsH"]) + list(view["wallsV"]):
        x, y, w, h = wall_rect(t)
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" '
                     f'fill="{WALL}"/>')
    for token, colour in ((view["p1"], P1), (view["p2"], P2)):
        x, y = square_xy(token)
        parts.append(f'<circle cx="{x + CELL // 2}" cy="{y + CELL // 2}" '
                     f'r="{int(CELL * 0.34)}" fill="{colour}"/>')
    parts.append("</svg>")
    return "".join(parts)


OG_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
  * {{ margin: 0; box-sizing: border-box; }}
  body {{ width: 1200px; height: 630px; background: {bg};
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: {text}; display: flex; align-items: center; gap: 56px; padding: 0 64px; }}
  .board {{ flex: none; line-height: 0;
    filter: drop-shadow(0 12px 40px rgba(0,0,0,.55)); }}
  h1 {{ font-size: 76px; font-weight: 700; letter-spacing: -.01em; }}
  .dot {{ color: {accent}; }}
  p {{ font-size: 30px; line-height: 1.4; color: {text}; margin-top: 18px; }}
  .sub {{ font-size: 22px; color: {dim}; margin-top: 26px; }}
  .rule {{ width: 72px; height: 4px; background: {accent}; margin-top: 30px;
    border-radius: 2px; }}
</style></head><body>
  <div class="board">{svg}</div>
  <div>
    <h1>murus<span class="dot">.</span></h1>
    <p>The wall game — for people <em>and</em> engines.</p>
    <div class="rule"></div>
    <div class="sub">One ladder. An open bot API.<br>murus.net</div>
  </div>
</body></html>"""


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "murus-promo"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="https://murus.net")
    ap.add_argument("--out", default="promo")
    ap.add_argument("--ply", type=int, default=34,
                    help="which position of the sample game to draw")
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # A real mid-game position: both pawns committed, walls doing real work.
    games = fetch(f"{args.site}/api/user/Selina")["recent"]
    gid = next(g["id"] for g in games if g["reason"] == "mate")
    views = fetch(f"{args.site}/api/game/{gid}/views")["views"]
    view = views[min(args.ply, len(views) - 1)]
    print(f"drawing {gid} at ply {args.ply}: "
          f"{len(view['wallsH']) + len(view['wallsV'])} walls placed")

    og = OG_HTML.format(bg=BG, text=TEXT, dim=DIM, accent=ACCENT,
                        svg=board_svg(view, 470))
    (out / "og.html").write_text(og, encoding="utf-8")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        b = pw.chromium.launch()

        # 1. The link-preview card.
        p = b.new_page(viewport={"width": 1200, "height": 630},
                       device_scale_factor=1)
        p.goto((out / "og.html").resolve().as_uri())
        p.wait_for_timeout(400)
        p.screenshot(path=str(out / "og.png"))
        print("  og.png            1200x630  link preview")
        p.close()

        # 2. The site itself, at the sizes LinkedIn shows well.
        shots = [
            ("lobby", "/#/", 1200, 900, None),
            ("game", f"/#/game/{gid}", 1200, 900, ".board-col"),
            ("engines", "/#/engines", 1200, 900, None),
        ]
        for name, path, w, h, clip_sel in shots:
            p = b.new_page(viewport={"width": w, "height": h},
                           device_scale_factor=2)
            p.goto(args.site + path, wait_until="networkidle")
            p.wait_for_timeout(2500)
            # Dismiss the newcomer's introduction: it is the right thing for a
            # first visit and the wrong thing in a screenshot of the product.
            p.evaluate("localStorage.setItem('murus.intro.seen','1')")
            p.reload(wait_until="networkidle")
            p.wait_for_timeout(2500)
            p.screenshot(path=str(out / f"{name}.png"))
            print(f"  {name}.png{' ' * (16 - len(name))}{w}x{h}  @2x")
            p.close()

        # 3. A phone, because that is where the drag mechanism shows.
        p = b.new_page(viewport={"width": 390, "height": 844},
                       device_scale_factor=3, is_mobile=True,
                       has_touch=True)
        p.goto(args.site + f"/#/game/{gid}", wait_until="networkidle")
        p.evaluate("localStorage.setItem('murus.intro.seen','1')")
        p.reload(wait_until="networkidle")
        p.wait_for_timeout(2500)
        p.screenshot(path=str(out / "phone.png"))
        print("  phone.png         390x844   @3x")
        p.close()

        # 4. The introduction, which is the newcomer's first impression.
        p = b.new_page(viewport={"width": 1200, "height": 800},
                       device_scale_factor=2)
        p.goto(args.site, wait_until="networkidle")
        p.evaluate("localStorage.removeItem('murus.intro.seen')")
        p.reload(wait_until="networkidle")
        p.wait_for_timeout(2500)
        p.screenshot(path=str(out / "intro.png"))
        print("  intro.png         1200x800  @2x")
        p.close()
        b.close()

    (out / "og.html").unlink(missing_ok=True)
    print(f"\nwrote {len(list(out.glob('*.png')))} images to {out.resolve()}")


if __name__ == "__main__":
    main()
