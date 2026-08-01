"""Draw the logo and cover art for the LinkedIn organization page.

The mark is the game reduced to its one idea: two players, a wall between
them. Nothing else survives being shown at 48 pixels, which is the size a
company logo is actually seen at in a feed.

    python tools/brand_assets.py --out promo/brand
"""

from __future__ import annotations

import argparse
import json
import pathlib
import urllib.request

BG, CELL, WALL, P1, P2 = "#161512", "#34322d", "#b98a52", "#e0a458", "#6aa1d8"
TEXT, DIM, ACCENT = "#dad7d1", "#918d85", "#7fa650"

# Board geometry, matching web/src/lib/geometry.ts.
C, G, M = 50, 10, 28
STEP, SPAN = C + G, 9 * C + 8 * G
SIZE = SPAN + 2 * M
FILES = "abcdefghi"


def square_xy(t):
    f, r = FILES.index(t[0]), int(t[1:]) - 1
    return M + f * STEP, M + (8 - r) * STEP


def wall_rect(t):
    f, r = FILES.index(t[1]), int(t[2:]) - 1
    top = M + (7 - r) * STEP
    if t[0] == "h":
        return M + f * STEP, top + C, 2 * C + G, G
    return M + f * STEP + C, top, G, 2 * C + G


def board_svg(view, px):
    out = [f'<svg viewBox="0 0 {SIZE} {SIZE}" width="{px}" height="{px}" '
           'xmlns="http://www.w3.org/2000/svg">']
    for r in range(9):
        for f in range(9):
            out.append(f'<rect x="{M+f*STEP}" y="{M+r*STEP}" width="{C}" '
                       f'height="{C}" rx="3" fill="{CELL}"/>')
    for t in list(view["wallsH"]) + list(view["wallsV"]):
        x, y, w, h = wall_rect(t)
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="{WALL}"/>')
    for t, col in ((view["p1"], P1), (view["p2"], P2)):
        x, y = square_xy(t)
        out.append(f'<circle cx="{x+C//2}" cy="{y+C//2}" r="{int(C*0.34)}" fill="{col}"/>')
    return "".join(out) + "</svg>"


# The mark: a 3x3 fragment, one wall, one pawn either side of it. At a feed's
# logo size the board grid reads as texture and the two dots either side of a
# bar still read as "two players, blocked" — which is the whole game.
LOGO = """<!doctype html><meta charset="utf-8"><style>
 *{{margin:0;box-sizing:border-box}}
 body{{width:{s}px;height:{s}px;background:{bg};display:flex;
   align-items:center;justify-content:center}}
</style>
<svg width="{inner}" height="{inner}" viewBox="0 0 340 340"
     xmlns="http://www.w3.org/2000/svg">
  <rect x="10"  y="10"  width="100" height="100" rx="8" fill="{cell}"/>
  <rect x="120" y="10"  width="100" height="100" rx="8" fill="{cell}"/>
  <rect x="230" y="10"  width="100" height="100" rx="8" fill="{cell}"/>
  <rect x="10"  y="120" width="100" height="100" rx="8" fill="{cell}"/>
  <rect x="120" y="120" width="100" height="100" rx="8" fill="{cell}"/>
  <rect x="230" y="120" width="100" height="100" rx="8" fill="{cell}"/>
  <rect x="10"  y="230" width="100" height="100" rx="8" fill="{cell}"/>
  <rect x="120" y="230" width="100" height="100" rx="8" fill="{cell}"/>
  <rect x="230" y="230" width="100" height="100" rx="8" fill="{cell}"/>
  <circle cx="170" cy="60"  r="38" fill="{p1}"/>
  <circle cx="170" cy="280" r="38" fill="{p2}"/>
  <rect x="10" y="163" width="320" height="14" rx="7" fill="{wall}"/>
</svg>"""

COVER = """<!doctype html><meta charset="utf-8"><style>
 *{{margin:0;box-sizing:border-box}}
 body{{width:1128px;height:191px;background:{bg};display:flex;
   align-items:center;overflow:hidden;
   font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
 /* LinkedIn drops the page logo over the lower left of the cover, so the
    first 280px carry nothing that matters. */
 .pad{{width:290px;flex:none}}
 .words{{flex:1;color:{text}}}
 h1{{font-size:44px;font-weight:700;letter-spacing:-.01em;line-height:1}}
 .dot{{color:{accent}}}
 p{{font-size:19px;color:{dim};margin-top:10px}}
 .strip{{flex:none;display:flex;gap:0;opacity:.9;
   mask-image:linear-gradient(to right,transparent,#000 22%);
   -webkit-mask-image:linear-gradient(to right,transparent,#000 22%)}}
</style>
<div class="pad"></div>
<div class="words">
  <h1>murus<span class="dot">.</span></h1>
  <p>The wall game — for people <em>and</em> engines</p>
</div>
<div class="strip">{svg}</div>"""


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "murus-brand"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="https://murus.net")
    ap.add_argument("--out", default="promo/brand")
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    games = fetch(f"{args.site}/api/user/Selina")["recent"]
    gid = next(g["id"] for g in games if g["reason"] == "mate")
    view = fetch(f"{args.site}/api/game/{gid}/views")["views"][34]

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for px, name in ((400, "logo-400.png"), (300, "logo-300.png")):
            f = out / "l.html"
            f.write_text(LOGO.format(s=px, inner=int(px * 0.78), bg=BG,
                                     cell=CELL, wall=WALL, p1=P1, p2=P2),
                         encoding="utf-8")
            p = b.new_page(viewport={"width": px, "height": px})
            p.goto(f.resolve().as_uri())
            p.wait_for_timeout(300)
            p.screenshot(path=str(out / name))
            p.close()
            print(f"  {name:<14} {px}x{px}")

        f = out / "c.html"
        f.write_text(COVER.format(bg=BG, text=TEXT, dim=DIM, accent=ACCENT,
                                  svg=board_svg(view, 191)), encoding="utf-8")
        p = b.new_page(viewport={"width": 1128, "height": 191})
        p.goto(f.resolve().as_uri())
        p.wait_for_timeout(300)
        p.screenshot(path=str(out / "cover.png"))
        p.close()
        print("  cover.png      1128x191")
        b.close()

    for junk in ("l.html", "c.html"):
        (out / junk).unlink(missing_ok=True)
    print(f"\nwrote to {out.resolve()}")


if __name__ == "__main__":
    main()
