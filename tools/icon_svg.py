"""앱 아이콘 원본(SVG)을 만든다. 크기별 PNG는 tools/export_icons.js 가 이 SVG에서 뽑는다.

디자인 규칙 (design/아이콘/README.md 에 설명)
  - 바탕: 브랜드 초록(#00A86B)을 가운데 둔 위→아래 옅은 명암 + 위쪽 은은한 빛. 평면 단색보다 깊이가 생긴다.
  - 글자: DBT Sans(Pretendard 기반, OFL) 윤곽선을 그대로 벡터로 옮긴다. 글꼴 칸이 아니라 '잉크' 기준으로
    글자 사이를 같은 간격으로 좁힌다(로고타입 자간). 한글은 무게중심이 위에 있어 정중앙보다 살짝 위에 둔다.
  - 원본은 1024 정사각형, 모서리 없음(아이폰·안드로이드가 자기 모양으로 자른다).
    모서리가 필요한 곳(브라우저·데스크톱 설치 아이콘)은 앱 아이콘 비율(22.37%)의 부드러운 모서리로 자른다.
사용법: python tools/icon_svg.py   → design/아이콘/*.svg, web/app/icons/icon.svg
"""
import io
import math
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "web" / "app" / "fonts" / "DBTSans-Variable.woff2"
DESIGN = ROOT / "design" / "아이콘"
WEB = ROOT / "web" / "app" / "icons"
N = 1024

_cache = {}


def load_font(path=FONT, weight=None):
    """글꼴 파일(ttf/otf/woff2)을 읽는다. 가변 글꼴이면 weight 굵기로 고정한다."""
    key = (str(path), weight)
    if key not in _cache:
        f = TTFont(path)
        f.flavor = None
        if "fvar" in f and weight is not None:
            instancer.instantiateVariableFont(f, {"wght": weight}, inplace=True)
        buf = io.BytesIO()
        f.save(buf)
        _cache[key] = TTFont(io.BytesIO(buf.getvalue()))
    return _cache[key]


def font_at(weight):
    return load_font(FONT, weight)


def glyph(font, ch):
    gs = font.getGlyphSet()
    name = font.getBestCmap()[ord(ch)]
    bp = BoundsPen(gs)
    gs[name].draw(bp)
    return gs[name], bp.bounds  # (xMin, yMin, xMax, yMax), 글꼴 단위(위가 +)


def wordmark(lines, weight, width_frac, gap_em, line_gap_em, center_y=0.485, height_frac=None, font=None):
    """글자 윤곽을 잉크 기준 자간으로 배치해 SVG path 문자열 하나로 돌려준다."""
    font = font or font_at(weight)
    em = font["head"].unitsPerEm
    rows = []
    for text in lines:
        gl = [glyph(font, ch) for ch in text]
        x, placed = 0.0, []
        for g, (x0, y0, x1, y1) in gl:
            placed.append((g, x - x0))       # 잉크 왼쪽 끝을 x에 맞춘다
            x += (x1 - x0) + gap_em * em
        width = x - gap_em * em
        top = max(b[3] for _, b in gl); bot = min(b[1] for _, b in gl)
        rows.append((placed, width, top, bot))
    block_w = max(r[1] for r in rows)
    line_h = max(r[2] - r[3] for r in rows)
    block_h = line_h * len(rows) + line_gap_em * em * (len(rows) - 1)
    s = (N * width_frac) / block_w
    if height_frac:
        s = min(s, (N * height_frac) / block_h)
    y_top = N * center_y - block_h * s / 2
    pen = SVGPathPen(font.getGlyphSet())
    for i, (placed, width, top, bot) in enumerate(rows):
        x_off = (N - width * s) / 2
        base = y_top + i * (line_h + line_gap_em * em) * s + top * s   # 이 줄의 글꼴 기준선(화면 좌표)
        for g, dx in placed:
            g.draw(TransformPen(pen, (s, 0, 0, -s, x_off + dx * s, base)))
    return pen.getCommands()


def squircle(n=N, r=0.2237):
    """앱 아이콘 모서리: 반지름 22.37%(아이폰 홈 아이콘 비율)의 둥근 사각형."""
    R = n * r
    return (f"M{R:.1f},0 H{n - R:.1f} A{R:.1f},{R:.1f} 0 0 1 {n},{R:.1f} V{n - R:.1f} "
            f"A{R:.1f},{R:.1f} 0 0 1 {n - R:.1f},{n} H{R:.1f} A{R:.1f},{R:.1f} 0 0 1 0,{n - R:.1f} "
            f"V{R:.1f} A{R:.1f},{R:.1f} 0 0 1 {R:.1f},0 Z")


PALETTES = {
    "brand": ("#1FC386", "#00A86B", "#008F5A"),   # 위 · 가운데(브랜드) · 아래
    "deep": ("#0FA572", "#008A57", "#006B43"),
}


def svg(path_d, palette="brand", shape="full", shadow=True):
    top, mid, bot = PALETTES[palette]
    clip = f'<clipPath id="c"><path d="{squircle()}"/></clipPath>' if shape == "squircle" else ""
    g_open = '<g clip-path="url(#c)">' if shape == "squircle" else "<g>"
    filt = ('<filter id="s" x="-10%" y="-10%" width="120%" height="130%">'
            '<feDropShadow dx="0" dy="10" stdDeviation="14" flood-color="#003F28" flood-opacity="0.22"/></filter>') if shadow else ""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {N} {N}" width="{N}" height="{N}">
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/><stop offset=".5" stop-color="{mid}"/><stop offset="1" stop-color="{bot}"/></linearGradient>
<radialGradient id="glow" cx=".5" cy="0" r=".85"><stop offset="0" stop-color="#FFFFFF" stop-opacity=".16"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></radialGradient>
{clip}{filt}
</defs>
{g_open}<rect width="{N}" height="{N}" fill="url(#bg)"/><rect width="{N}" height="{N}" fill="url(#glow)"/>
<path d="{path_d}" fill="#FFFFFF"{' filter="url(#s)"' if shadow else ''}/></g>
</svg>
'''


VARIANTS = {
    # 이름: (줄, 굵기, 폭 비율, 자간(em), 줄 간격(em), 높이 비율, 색)
    "A_한줄": (["덜붐빌때"], 680, 0.64, 0.06, 0, None, "brand"),
    "B_두줄": (["덜붐", "빌때"], 760, 0.50, 0.05, 0.08, 0.52, "brand"),
    "C_한줄_깊은초록": (["덜붐빌때"], 680, 0.64, 0.06, 0, None, "deep"),
}
CHOSEN = "A_한줄"


if __name__ == "__main__":
    DESIGN.mkdir(parents=True, exist_ok=True)
    WEB.mkdir(parents=True, exist_ok=True)
    for name, (lines, w, wf, gap, lgap, hf, pal) in VARIANTS.items():
        d = wordmark(lines, w, wf, gap, lgap, height_frac=hf)
        (DESIGN / f"icon_{name}.svg").write_text(svg(d, pal), encoding="utf-8")
        (DESIGN / f"icon_{name}_squircle.svg").write_text(svg(d, pal, "squircle"), encoding="utf-8")
    lines, w, wf, gap, lgap, hf, pal = VARIANTS[CHOSEN]
    d = wordmark(lines, w, wf, gap, lgap, height_frac=hf)
    (WEB / "icon-full.svg").write_text(svg(d, pal), encoding="utf-8")                     # 아이폰·안드로이드 마스크용
    (WEB / "icon.svg").write_text(svg(d, pal, "squircle"), encoding="utf-8")               # 브라우저·설치 아이콘
    small = wordmark(["덜"], 820, 0.62, 0, 0, center_y=0.5, height_frac=0.62)
    (WEB / "favicon.svg").write_text(svg(small, pal, "squircle", shadow=False), encoding="utf-8")
    print("SVG:", sorted(p.name for p in DESIGN.glob("*.svg")), sorted(p.name for p in WEB.glob("*.svg")))
