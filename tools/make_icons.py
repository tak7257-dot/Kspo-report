"""앱 아이콘: 초록 바탕 + 흰 글씨(DBT Sans, OFL). 큰 아이콘은 '덜붐빌때' 한 줄 가운데, 탭 아이콘은 '덜' 한 글자.
사용법: python tools/make_icons.py   → web/app/icons/*.png 를 다시 그린다 (Pillow, fontTools, brotli 필요)
"""
import io
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = str(ROOT / "web" / "app" / "icons") + "/"
_buf = io.BytesIO()
_f = TTFont(ROOT / "web" / "app" / "fonts" / "DBTSans-Variable.woff2"); _f.flavor = None; _f.save(_buf)
TTF = io.BytesIO(_buf.getvalue())
GREEN, WHITE = (0, 168, 107, 255), (255, 255, 255, 255)

def font(px, weight=800):
    TTF.seek(0)
    f = ImageFont.truetype(TTF, px)
    f.set_variation_by_axes([weight])
    return f

def draw(size, lines, safe, rounded, weight=800):
    S = size * 4
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if rounded: d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=GREEN)
    else: d.rectangle([0, 0, S, S], fill=GREEN)
    area = S * safe
    # 가장 긴 줄이 안전 영역 폭에 맞도록 글자 크기를 정한다
    px = int(area)
    while True:
        f = font(px, weight)
        boxes = [d.textbbox((0, 0), t, font=f) for t in lines]
        w = max(b[2] - b[0] for b in boxes); lh = max(b[3] - b[1] for b in boxes)
        gap = lh * 0.12; h = lh * len(lines) + gap * (len(lines) - 1)
        if w <= area and h <= area: break
        px -= 4
    y = (S - h) / 2
    for t, b in zip(lines, boxes):
        x = (S - (b[2] - b[0])) / 2 - b[0]
        d.text((x, y - b[1]), t, font=f, fill=WHITE)
        y += lh + gap
    return im.resize((size, size), Image.LANCZOS)

one = ['덜붐빌때']
draw(192, one, 0.70, True).save(OUT + 'icon-192.png')
draw(512, one, 0.70, True).save(OUT + 'icon-512.png')
draw(512, one, 0.62, False).save(OUT + 'icon-maskable-512.png')   # 안드로이드가 원으로 잘라도 남는 폭
draw(180, one, 0.70, False).convert('RGB').save(OUT + 'apple-touch-icon.png')
draw(32, ['덜'], 0.74, True, 860).save(OUT + 'favicon-32.png')
