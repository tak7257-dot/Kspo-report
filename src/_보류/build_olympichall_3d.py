"""올림픽홀 3D 모델(GLB) 자체 제작 — 공식 도면 기반 (v2: 좌석 개별 배치)

기관이 제공한 '공연장 실감형 콘텐츠'에 올림픽홀은 없어서, 기관 홈페이지의 공식 도면으로 직접 만든다.
  입력  data/raw/drawings/olympichall_2.pdf  2층 평면도 (좌석·벽 배치)
        (축척) 1층 평면도 기준선 치수: X2~X3 6,000mm 등 → 도면 1pt = 0.1415m
        (높이) olympichall_4.pdf 무대 단면도: 무대 1.3m, 무대 상부(그리드) 23.4m
  출력  output/3d/olympichall.glb

방법
  1) 좌석: 도면을 이미지로 그린 뒤 '검은 테두리로 둘러싸인 작은 흰 네모'(방석)를 찾는다 → 좌석 1개
     방향: 좌석 주변 검은 선(등받이)이 몰린 쪽의 반대 = 좌석이 바라보는 쪽
  2) 벽: 두 줄 벽선 사이를 메우고(closing) 가는 선·글자는 지운 뒤(opening), 건물 가장자리 띠(외벽·로비 벽)만 세운다
     객석 사이 난간·통로 선은 세우지 않는다. 무대동(뒷벽·옆벽·무대 입구 아치)은 무대 영역 치수로 직접 만든다.
     모서리 계단실은 안쪽 세부선이 많아 원통으로 대신한다
  3) 단 높이: 도면에 없음 → 플로어에서 멀어질수록 높아지는 경사(약 23도)로 추정
     (이동식 객석은 플로어 위 낮은 경사)

사용법:  python src/build_olympichall_3d.py
"""
import math
from pathlib import Path

import cv2
import numpy as np
import pymupdf as fitz
import trimesh
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
PDF2 = ROOT / "data" / "raw" / "drawings" / "olympichall_2.pdf"
OUT = ROOT / "output" / "3d"

M_PER_PT = 0.1415                      # 1층 평면도 치수로 계산한 축척
Z = 4.0                                # 도면 1pt = 4px 로 그려서 분석
CLIP = (270, 180, 840, 760)            # 2층 평면도에서 올림픽홀 본관 영역(pt)
CENTER = (560, 461)                    # 건물 중심(pt)
TOWERS = [(379, 292), (737, 292), (379, 630), (737, 630)]   # 모서리 계단실 중심(pt)
TOWER_R = 33
FLOOR = (477, 332, 650, 592)           # 플로어(평면) 영역(pt): x0, y0, x1, y1
STAGE = (479, 211, 645, 330)           # 무대 영역(pt)
RETRACT_Y0 = 516                       # 플로어 위 이동식 객석이 시작하는 y(pt)
WALL_H, STAGE_WALL_H, STAGE_H = 12.0, 23.4, 1.3
RAKE = 0.42                            # 객석 경사(높이/거리), 약 23도
OUTER_BAND = (205, 262)                # 외벽·로비 벽으로 인정하는 중심 거리 범위(pt)
PROSC_OPEN_H = 11.0                    # 무대 입구(프로시니엄) 개구부 높이 (추정)

COLOR = {
    "ground": [206, 208, 202, 255], "wall": [232, 230, 224, 255], "tower": [190, 192, 196, 255],
    "floor": [190, 150, 102, 255], "stage": [40, 40, 46, 255], "step": [150, 150, 154, 255],
    "seat": [176, 38, 44, 255], "seat_back": [128, 24, 32, 255],
}


def to_m(x, y):
    """도면 pt → (x, z) 미터, 건물 중심 기준 (glTF: X 오른쪽, Z 아래쪽=무대 반대편, Y 위)"""
    return ((x - CENTER[0]) * M_PER_PT, (y - CENTER[1]) * M_PER_PT)


def render():
    x0, y0, x1, y1 = CLIP
    pg = fitz.open(PDF2)[0]
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(x0, y0, x1, y1), colorspace=fitz.csGRAY)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w).copy()


def px2pt(px, py):
    return px / Z + CLIP[0], py / Z + CLIP[1]


def find_seats(img):
    """방석(작은 흰 네모)을 찾아 좌석 위치·방향을 돌려준다: [(x_pt, y_pt, 바라보는 각도)]"""
    white = (img > 160).astype(np.uint8)
    ink = (img < 128).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(white, 4)
    seats = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if not (6 <= w <= 18 and 6 <= h <= 18 and 0.6 <= w / h <= 1.6) or a / (w * h) < 0.42:
            continue
        cnts, _ = cv2.findContours((lab[y:y + h, x:x + w] == i).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if a / max(cv2.contourArea(cv2.convexHull(cnts[0])), 1) < 0.85:     # 네모에 가까운 모양만
            continue
        cx, cy = cen[i]
        sx, sy = px2pt(cx, cy)
        if (sy < 330 or sy > 688 or math.hypot(sx - CENTER[0], sy - CENTER[1]) > 245
                or any(math.hypot(sx - tx, sy - ty) < TOWER_R + 3 for tx, ty in TOWERS)):
            continue
        # 방향: 주변 검은 선(등받이)의 무게중심이 방석 중심에서 어느 쪽으로 치우쳤는지
        r = 14
        ox, oy = max(0, int(cx) - r), max(0, int(cy) - r)
        win = ink[oy: int(cy) + r, ox: int(cx) + r]
        ys, xs = np.nonzero(win)
        dx, dy = (xs.mean() + ox - cx, ys.mean() + oy - cy) if len(xs) else (0.0, 0.0)
        if math.hypot(dx, dy) < 0.8:      # 판단이 어려우면 무대 쪽을 보게
            dx, dy = sx - (STAGE[0] + STAGE[2]) / 2, sy - STAGE[3]
        seats.append((sx, sy, math.atan2(-dy, -dx)))   # 등받이 반대쪽 = 바라보는 쪽
    return seats


def seat_height(sx, sy):
    x0, y0, x1, y1 = FLOOR
    if x0 <= sx <= x1 and y0 <= sy <= y1:            # 플로어 위 이동식 객석
        return max(0.0, (sy - RETRACT_Y0) * M_PER_PT * 0.28) + 0.05
    d = Point(sx, sy).distance(box(x0, y0, x1, y1)) * M_PER_PT
    return 0.8 + RAKE * d


def oriented_box(size, center_xz, y0, angle):
    """size=(가로, 깊이, 높이) 상자를 바닥 높이 y0에 놓고, 도면 각도 angle 쪽을 바라보게 돌린다"""
    w, d, h = size
    m = trimesh.creation.box(extents=(w, h, d))
    m.apply_translation((0, y0 + h / 2, 0))
    # 상자의 '깊이'축(z)을 바라보는 방향(도면 각도: x오른쪽, y아래 = glTF x, z)에 맞춘다
    m.apply_transform(trimesh.transformations.rotation_matrix(-(angle - math.pi / 2), (0, 1, 0)))
    m.apply_translation((center_xz[0], 0, center_xz[1]))
    return m


def walls_from_plan(img, seats):
    ink = (img < 128).astype(np.uint8) * 255
    for sx, sy, _ in seats:                                   # 좌석 그림 지우기
        cv2.circle(ink, (int((sx - CLIP[0]) * Z), int((sy - CLIP[1]) * Z)), int(3.2 * Z), 0, -1)
    for tx, ty in TOWERS:                                     # 계단실은 원통으로 대신
        cv2.circle(ink, (int((tx - CLIP[0]) * Z), int((ty - CLIP[1]) * Z)), int((TOWER_R + 2) * Z), 0, -1)
    x0, y0, x1, y1 = FLOOR                                    # 플로어 테두리선 지우기
    cv2.rectangle(ink, (int((x0 - 3 - CLIP[0]) * Z), int((y0 + 3 - CLIP[1]) * Z)),
                  (int((x1 + 3 - CLIP[0]) * Z), int((y1 + 3 - CLIP[1]) * Z)), 0, -1)
    k = lambda r: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r, r))
    wall = cv2.morphologyEx(cv2.morphologyEx(ink, cv2.MORPH_CLOSE, k(9)), cv2.MORPH_OPEN, k(7))
    cnts, hier = cv2.findContours(wall, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    conv = lambda cc: [to_m(*px2pt(*p[0])) for p in cv2.approxPolyDP(cc, 1.5, True)]
    polys = []
    for i, c in enumerate(cnts):
        if hier[0][i][3] != -1 or cv2.contourArea(c) < 3000:   # 바깥 윤곽 + 큰 덩어리만
            continue
        holes = [conv(cnts[j]) for j in range(len(cnts)) if hier[0][j][3] == i and cv2.contourArea(cnts[j]) > 50]
        shell = conv(c)
        if len(shell) < 3:
            continue
        p = Polygon(shell, [hh for hh in holes if len(hh) >= 3]).buffer(0)
        if not p.is_empty:
            polys.append(p)
    return unary_union(polys)


def extrude(shape, y0, h, color, out):
    for g in getattr(shape, "geoms", [shape]):
        if g.is_empty or g.area < 0.05:
            continue
        m = trimesh.creation.extrude_polygon(g, h)
        # (x, 도면y) 평면에서 z 로 세운 것을 → (x, z=도면y) 평면에서 y(위)로 세우도록: X축 +90도 회전 후 h 만큼 올림
        m.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, (1, 0, 0)))
        m.apply_translation((0, y0 + h, 0))
        out.setdefault(tuple(color), []).append(m)


def build():
    img = render()
    seats = find_seats(img)
    parts = {}

    hall_r = 255 * M_PER_PT
    rect = lambda x0, y0, x1, y1: Polygon([to_m(x0, y0), to_m(x1, y0), to_m(x1, y1), to_m(x0, y1)])
    stage_house = rect(STAGE[0] - 8, 186, STAGE[2] + 8, 335)
    extrude(unary_union([Point(0, 0).buffer(hall_r, 128), stage_house]), -0.3, 0.3, COLOR["ground"], parts)

    # 외벽·로비 벽: 도면 벽선 중 건물 가장자리 띠에 있는 것만 (무대동 자리는 제외)
    band = Point(0, 0).buffer(OUTER_BAND[1] * M_PER_PT, 128).difference(Point(0, 0).buffer(OUTER_BAND[0] * M_PER_PT, 128))
    walls = walls_from_plan(img, seats).intersection(band).difference(stage_house.buffer(0.5))
    extrude(walls, 0, WALL_H, COLOR["wall"], parts)

    # 무대동: 뒷벽·옆벽 23.4m(단면도) + 무대 입구 아치(개구부 위만 벽)
    t = 1.2 / M_PER_PT                                         # 벽 두께 약 1.2m (pt)
    sx0, sx1, sy0, sy1 = STAGE[0] - 8, STAGE[2] + 8, 186, STAGE[3]
    for w in [rect(sx0, sy0, sx1, sy0 + t), rect(sx0, sy0, sx0 + t, sy1), rect(sx1 - t, sy0, sx1, sy1)]:
        extrude(w, 0, STAGE_WALL_H, COLOR["wall"], parts)
    extrude(rect(sx0, sy1 - t, sx1, sy1), PROSC_OPEN_H, STAGE_WALL_H - PROSC_OPEN_H, COLOR["wall"], parts)
    extrude(rect(sx0, sy1 - t, STAGE[0], sy1), 0, PROSC_OPEN_H, COLOR["wall"], parts)
    extrude(rect(STAGE[2], sy1 - t, sx1, sy1), 0, PROSC_OPEN_H, COLOR["wall"], parts)
    for tx, ty in TOWERS:
        extrude(Point(*to_m(tx, ty)).buffer(TOWER_R * M_PER_PT, 48), 0, WALL_H + 1.5, COLOR["tower"], parts)

    # 플로어·무대
    extrude(rect(*FLOOR), 0, 0.05, COLOR["floor"], parts)
    extrude(rect(*STAGE), 0, STAGE_H, COLOR["stage"], parts)

    # 좌석: 단(계단) + 방석 + 등받이
    for sx, sy, ang in seats:
        h = seat_height(sx, sy)
        c = to_m(sx, sy)
        fx, fz = math.cos(ang), math.sin(ang)          # 바라보는 방향
        parts.setdefault(tuple(COLOR["step"]), []).append(oriented_box((0.58, 0.95, h), (c[0] - fx * 0.15, c[1] - fz * 0.15), 0, ang))
        parts.setdefault(tuple(COLOR["seat"]), []).append(oriented_box((0.48, 0.44, 0.12), c, h + 0.38, ang))
        parts.setdefault(tuple(COLOR["seat_back"]), []).append(
            oriented_box((0.48, 0.07, 0.5), (c[0] - fx * 0.24, c[1] - fz * 0.24), h + 0.38, ang))

    scene = trimesh.Scene()
    name_of = {tuple(v): k for k, v in COLOR.items()}
    for color, meshes in parts.items():
        merged = trimesh.util.concatenate(meshes)
        merged.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
            baseColorFactor=list(color), metallicFactor=0.0, roughnessFactor=0.85, name=name_of[color]))
        scene.add_geometry(merged, node_name=name_of[color])
    return scene, len(seats)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    scene, n_seats = build()
    path = OUT / "olympichall.glb"
    scene.export(path)
    b = scene.bounds
    tris = sum(len(g.faces) for g in scene.geometry.values())
    print(f"저장: {path} ({path.stat().st_size / 1e6:.1f}MB) | 좌석 {n_seats}개 | 삼각형 {tris:,}개 | "
          f"크기 {b[1][0] - b[0][0]:.1f} x {b[1][2] - b[0][2]:.1f} m, 높이 {b[1][1]:.1f} m")
