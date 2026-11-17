"""올림픽홀 간이 3D 모델(GLB) 자체 제작

기관이 제공한 '공연장 실감형 콘텐츠'에 올림픽홀은 없어서, 기관 홈페이지의 공식 도면으로 직접 만든다.
  - 평면 배치: 올림픽홀 2층 평면도(olympichall_2.pdf) — 원형 건물, 무대동, 플로어, 4종류 객석, 모서리 계단실
  - 축척: 1층 평면도의 기준선 치수(X2~X3 6,000mm 등)로 계산한 '도면 1pt = 0.1415m'
  - 높이: 무대 평면도·단면도(olympichall_4.pdf) — 무대 1.3m, 무대 상부(그리드) 23.4m
  - 객석 단 높이·벽 높이는 도면에 없어서 일반적인 값으로 정함 (간이 모델)

좌표: 2층 평면도를 1.2배로 그린 이미지의 픽셀 좌표(P)로 위치를 적고, 미터로 바꾼다.
glTF 좌표: X = 도면 가로, Z = 도면 세로(아래쪽 = 무대 반대편), Y = 높이

사용법:  python src/build_olympichall_3d.py
출력:    output/3d/olympichall.glb
"""
import math
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

OUT = Path(__file__).resolve().parent.parent / "output" / "3d"
PX2M = (1 / 1.2) * 0.1415          # 미리보기 이미지 1px → m
CENTER = (430, 400)                 # 건물 중심(px)

COLOR = {  # RGBA
    "wall": [225, 223, 216, 255], "ground": [200, 205, 195, 255], "floor": [196, 160, 112, 255],
    "stage": [45, 45, 50, 255], "tower": [150, 150, 150, 255], "seat": [178, 52, 52, 255], "seat_alt": [120, 30, 34, 255],
    "seat_floor": [150, 60, 60, 255], "lobby": [235, 233, 226, 255],
}


def P(x, y):
    """미리보기 픽셀 좌표 → (x, z) 미터, 건물 중심 기준"""
    return ((x - CENTER[0]) * PX2M, (y - CENTER[1]) * PX2M)


def poly(*pts):
    return Polygon([P(*p) for p in pts])


def extrude(shape, z0, h, color):
    """shapely 평면 도형을 바닥 높이 z0 에서 h 만큼 세운다 (glTF: Y가 위)"""
    meshes = []
    for g in getattr(shape, "geoms", [shape]):
        if g.is_empty or g.area < 1e-4:
            continue
        m = trimesh.creation.extrude_polygon(g, h)
        # extrude_polygon 은 (x, y) 평면에서 z 로 세운다 → (x, z) 평면에서 y 로 세우도록 회전
        m.apply_transform(trimesh.transformations.rotation_matrix(-math.pi / 2, [1, 0, 0]))
        m.apply_translation([0, z0, 0])
        m.metadata["color"] = tuple(color)
        meshes.append(m)
    return meshes


def ring(r_out, r_in):
    c = Point(0, 0)
    return c.buffer(r_out, 128).difference(c.buffer(r_in, 128))


def tiers_linear(shape, direction, n, rise, base=0.3, gap=0.0):
    """shape 을 direction(단위벡터, 높아지는 쪽) 방향으로 n 줄로 잘라 계단식으로 세운다"""
    dx, dz = direction
    coords = np.array(shape.exterior.coords)
    t = coords @ np.array([dx, dz])
    lo, hi = t.min(), t.max()
    out = []
    for i in range(n):
        a, b = lo + (hi - lo) * i / n, lo + (hi - lo) * (i + 1) / n
        # 방향축 기준 띠 [a, b] 를 큰 사각형으로 만들어 교집합
        L = 500
        px, pz = -dz, dx
        strip = Polygon([(dx * a + px * L, dz * a + pz * L), (dx * b + px * L, dz * b + pz * L),
                         (dx * b - px * L, dz * b - pz * L), (dx * a - px * L, dz * a - pz * L)])
        part = shape.intersection(strip)
        out += extrude(part, 0, base + rise * (i + 1), COLOR["seat" if i % 2 == 0 else "seat_alt"])  # 줄마다 색을 바꿔 단 구분
    return out


def tiers_arc(r_in, r_out, a0, a1, n, rise, base=0.5):
    """중심 기준 반지름 r_in~r_out, 각도 a0~a1(도) 부채꼴 띠를 바깥쪽이 높아지게 n 줄로"""
    out = []
    for i in range(n):
        r1 = r_in + (r_out - r_in) * i / n
        r2 = r_in + (r_out - r_in) * (i + 1) / n
        angs = np.radians(np.linspace(a0, a1, 64))
        pts = [(r2 * math.cos(a), r2 * math.sin(a)) for a in angs] + \
              [(r1 * math.cos(a), r1 * math.sin(a)) for a in angs[::-1]]
        out += extrude(Polygon(pts), 0, base + rise * (i + 1), COLOR["seat" if i % 2 == 0 else "seat_alt"])
    return out


def build():
    parts = []
    R_OUT, R_IN = 318 * PX2M, 300 * PX2M          # 외벽 바깥/안쪽 반지름
    stage_house = poly((330, 85), (540, 85), (540, 237), (330, 237))
    hall = Point(0, 0).buffer(R_IN, 128)

    # 바닥(건물 전체) + 외벽(지붕 없이 안이 보이게 높이 9m로 자름)
    parts += extrude(unary_union([Point(0, 0).buffer(R_OUT, 128), stage_house]), -0.3, 0.3, COLOR["ground"])
    parts += extrude(ring(R_OUT, R_IN).difference(stage_house), 0, 9.0, COLOR["wall"])

    # 무대동: 무대(1.3m) + 무대 상부 뒷벽·옆벽(23.4m, 단면도)
    stage = poly((338, 92), (532, 92), (532, 236), (338, 236))
    parts += extrude(stage, 0, 1.3, COLOR["stage"])
    for w in [poly((330, 85), (540, 85), (540, 92), (330, 92)),
              poly((330, 85), (338, 85), (338, 236), (330, 236)),
              poly((532, 85), (540, 85), (540, 236), (532, 236))]:
        parts += extrude(w, 0, 23.4, COLOR["wall"])

    # 플로어(평면) + 이동식 좌석(플로어 뒤쪽, 낮은 계단)
    floor = poly((333, 237), (540, 237), (540, 555), (333, 555))
    parts += extrude(floor, 0, 0.05, COLOR["floor"])
    floor_seats = poly((352, 460), (515, 460), (515, 552), (352, 552))
    parts += [m for m in tiers_linear(floor_seats, (0, 1), 6, 0.12, base=0.05)]

    # 플로어 좌우 대각선 경사 객석 (바깥쪽이 높아짐)
    left_diag = poly((300, 300), (333, 280), (333, 555), (300, 580), (250, 520), (250, 330))
    right_diag = poly((540, 280), (572, 300), (618, 330), (618, 520), (570, 580), (540, 555))
    parts += tiers_linear(left_diag, (-1, 0), 12, 0.45)
    parts += tiers_linear(right_diag, (1, 0), 12, 0.45)

    # 바깥 좌우 세로 줄 객석 (벽 쪽이 가장 높음)
    left_out = poly((145, 265), (238, 265), (238, 530), (145, 530)).intersection(hall)
    right_out = poly((630, 265), (722, 265), (722, 530), (630, 530)).intersection(hall)
    parts += tiers_linear(left_out, (-1, 0), 10, 0.55, base=1.5)
    parts += tiers_linear(right_out, (1, 0), 10, 0.55, base=1.5)

    # 무대 맞은편 곡선형 뒤쪽 객석 (각도: 도면 아래쪽 = +Z = 90도)
    parts += tiers_arc(165 * PX2M, 292 * PX2M, 52, 128, 14, 0.5)

    # 모서리 계단실 4곳 (원기둥, 외벽 높이)
    for cx, cy in [(215, 195), (645, 195), (215, 600), (645, 600)]:
        parts += extrude(Point(*P(cx, cy)).buffer(40 * PX2M, 48), 0, 10.5, COLOR["tower"])

    # 같은 색끼리 합치고, 색은 재질(PBR baseColor)로 지정 → 웹 뷰어 표준 방식, 파일도 가벼움
    scene = trimesh.Scene()
    name_of = {tuple(v): k for k, v in COLOR.items()}
    for color in sorted({m.metadata["color"] for m in parts}):
        merged = trimesh.util.concatenate([m for m in parts if m.metadata["color"] == color])
        mat = trimesh.visual.material.PBRMaterial(baseColorFactor=list(color), metallicFactor=0.0,
                                                  roughnessFactor=0.9, name=name_of[color])
        merged.visual = trimesh.visual.TextureVisuals(material=mat)
        scene.add_geometry(merged, node_name=name_of[color])
    return scene


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    scene = build()
    path = OUT / "olympichall.glb"
    scene.export(path)
    b = scene.bounds
    print(f"저장: {path} ({path.stat().st_size / 1e6:.1f}MB), 부품 {len(scene.geometry)}개, "
          f"크기 {b[1][0] - b[0][0]:.1f} x {b[1][2] - b[0][2]:.1f} m, 높이 {b[1][1]:.1f} m")
