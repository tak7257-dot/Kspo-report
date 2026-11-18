"""KSPO DOME 3D 변환: 공공데이터 「올림픽공원 공연장 실감형 콘텐츠」의 DAE(475MB) → GLB

왜 직접 만드는가
  원본은 SketchUp에서 내보낸 COLLADA(DAE)로, 형상 10만 개·배치 8.3만 개로 쪼개져 있다.
  범용 변환기(assimp)는 1시간 안에 끝나지 않았다. 이 파일 구조에 맞춰 한 번에 읽고 재질별로 합친다.

원본을 최대한 그대로 옮기는 원칙
  - 형상 단순화(폴리곤 줄이기) 없음: 모든 삼각형·법선·텍스처 좌표를 그대로 쓴다
  - 재질 86종의 색·투명도, 텍스처 9장을 원본 해상도 그대로 쓴다
  - 바꾸는 것: 단위(인치 → 미터), 축(Z가 위 → Y가 위), 재질별로 부품 합치기
  - SketchUp 모델은 면 뒷면이 보이는 경우가 많아 양면 렌더링(doubleSided)으로 둔다

사용법:  python src/convert_kspodome_3d.py <temp_export.dae 경로>
출력:    output/3d/kspodome.raw.glb  (압축 전)
웹용 압축(형상 단순화 없이, 정밀 양자화):
  gltf-transform weld kspodome.raw.glb a.glb
  gltf-transform draco a.glb kspodome.glb --quantize-position 16 --quantize-normal 12 --quantize-texcoord 14
"""
import io
import mmap
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import trimesh
from lxml import etree
from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "output" / "3d"
INCH = 0.0254
# 건물이 아닌 요소: 'material' = SketchUp 방위 표시(N·S·E·W 글자, 211x247m). 모델 크기를 부풀려 화면이 작게 잡히므로 뺀다.
EXCLUDE = {"material"}
# 건물 전체를 감싼 외피(지름 131m). 지우지 않고 남겨서, 웹 화면에서 켜고 끌 수 있게 한다.
SHELL = "외부"


def section(mm, start_tag: bytes, end_tag: bytes) -> bytes:
    a = mm.find(start_tag)
    b = mm.find(end_tag, a) + len(end_tag)
    return b"<root>" + mm[a:b] + b"</root>"


def floats(text) -> np.ndarray:
    return np.array(text.split(), dtype=np.float32)


def parse_materials(xml: bytes, base: Path):
    """material id → dict(color RGBA, alpha, texture PIL.Image | None)"""
    root = etree.fromstring(xml, etree.XMLParser(huge_tree=True))
    images = {im.get("id"): base / im.findtext("init_from") for im in root.iter("image")}
    effects = {}
    for ef in root.iter("effect"):
        params = {np_.get("sid"): np_ for np_ in ef.iter("newparam")}
        diffuse = ef.find(".//diffuse")
        color = [1.0, 1.0, 1.0, 1.0]
        tex = None
        if diffuse is not None:
            c = diffuse.find("color")
            if c is not None:
                color = [float(v) for v in c.text.split()]
            t = diffuse.find("texture")
            if t is not None:                       # texture → sampler2D → surface → image
                sampler = params.get(t.get("texture"))
                surf = params.get(sampler.findtext(".//source")) if sampler is not None else None
                img_id = surf.findtext(".//init_from") if surf is not None else None
                if img_id in images and images[img_id].exists():
                    tex = Image.open(images[img_id]).convert("RGBA" if images[img_id].suffix == ".png" else "RGB")
        effects[ef.get("id")] = {"color": color, "texture": tex}
    mats = {}
    for m in root.iter("material"):
        eff = m.find("instance_effect").get("url").lstrip("#")
        mats[m.get("id")] = dict(effects[eff], name=m.get("name") or m.get("id"))
    return mats


def parse_geometries(xml: bytes):
    """geometry id → [(재질 심볼, 위치(N,3), 법선(N,3), UV(N,2)|None)]  (삼각형 꼭짓점 순서대로 펼친 배열)"""
    geoms = {}
    ctx = etree.iterparse(io.BytesIO(xml), events=("end",), tag="geometry", huge_tree=True)
    for _, g in ctx:
        sources = {}
        for s in g.iter("source"):
            arr = floats(s.findtext("float_array"))
            stride = int(s.find(".//accessor").get("stride"))
            sources[s.get("id")] = arr.reshape(-1, stride)
        verts = {}
        for v in g.iter("vertices"):
            verts[v.get("id")] = {i.get("semantic"): sources[i.get("source").lstrip("#")] for i in v.iter("input")}
        parts = []
        for tri in g.iter("triangles"):
            inputs = {i.get("semantic"): (int(i.get("offset")), i.get("source").lstrip("#")) for i in tri.iter("input")}
            n_in = max(o for o, _ in inputs.values()) + 1
            p = np.array(tri.findtext("p").split(), dtype=np.int64).reshape(-1, n_in)
            vo, vsrc = inputs["VERTEX"]
            vi = p[:, vo]
            pos = verts[vsrc]["POSITION"][vi]
            nrm = verts[vsrc]["NORMAL"][vi] if "NORMAL" in verts[vsrc] else None
            uv = None
            if "TEXCOORD" in inputs:
                to, tsrc = inputs["TEXCOORD"]
                uv = sources[tsrc][p[:, to]][:, :2]
            parts.append((tri.get("material"), pos, nrm, uv))
        geoms[g.get("id")] = parts
        g.clear()
        while g.getprevious() is not None:
            del g.getparent()[0]
    return geoms


def walk(node, parent_m, geoms, out, stats):
    m = parent_m
    mx = node.find("matrix")
    if mx is not None:                                   # COLLADA matrix: 행 우선 4x4
        m = parent_m @ floats(mx.text).reshape(4, 4).astype(np.float64)
    for ig in node.findall("instance_geometry"):
        bind = {im.get("symbol"): im.get("target").lstrip("#") for im in ig.iter("instance_material")}
        R, t = m[:3, :3], m[:3, 3]
        nmat = np.linalg.inv(R).T
        for sym, pos, nrm, uv in geoms.get(ig.get("url").lstrip("#"), []):
            mat = bind.get(sym, sym)
            P = pos.astype(np.float64) @ R.T + t
            N = None
            if nrm is not None:
                N = nrm.astype(np.float64) @ nmat.T
                N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
            if np.linalg.det(R) < 0:                     # 거울 배치면 삼각형 감김 방향을 뒤집는다
                P = P.reshape(-1, 3, 3)[:, ::-1].reshape(-1, 3)
                N = None if N is None else N.reshape(-1, 3, 3)[:, ::-1].reshape(-1, 3)
                uv = None if uv is None else uv.reshape(-1, 3, 2)[:, ::-1].reshape(-1, 2)
            out[mat].append((P, N, uv))
            stats["tris"] += len(P) // 3
        stats["instances"] += 1
    for child in node.findall("node"):
        walk(child, m, geoms, out, stats)


def to_gltf_axes(P):
    """인치·Z위 → 미터·Y위"""
    return np.column_stack([P[:, 0], P[:, 2], -P[:, 1]]) * INCH


def build(dae: Path):
    t0 = time.time()
    with open(dae, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        mats = parse_materials(section(mm, b"<library_materials", b"</library_images>"), dae.parent)  # 이미지 경로는 DAE 파일 폴더 기준
        print(f"재질 {len(mats)}종 (텍스처 {sum(m['texture'] is not None for m in mats.values())}종)  {time.time() - t0:.0f}s")
        geoms = parse_geometries(section(mm, b"<library_geometries", b"</library_geometries>"))
        print(f"형상 {len(geoms):,}개 읽음  {time.time() - t0:.0f}s")
        scene_xml = etree.fromstring(section(mm, b"<library_visual_scenes", b"</library_visual_scenes>"),
                                     etree.XMLParser(huge_tree=True))
    out, stats = defaultdict(list), defaultdict(int)
    vs = scene_xml.find(".//visual_scene")
    for n in vs.findall("node"):
        walk(n, np.eye(4), geoms, out, stats)
    print(f"배치 {stats['instances']:,}개, 삼각형 {stats['tris']:,}개  {time.time() - t0:.0f}s")

    # 전체 위치를 미터·Y위로 바꾸고, 바닥 중심을 원점으로
    all_min, all_max = np.full(3, np.inf), np.full(3, -np.inf)
    for mat_id, parts in out.items():
        if mats.get(mat_id, {}).get("name") in EXCLUDE:
            continue
        for P, _, _ in parts:
            Q = to_gltf_axes(P)
            all_min, all_max = np.minimum(all_min, Q.min(0)), np.maximum(all_max, Q.max(0))
    offset = np.array([-(all_min[0] + all_max[0]) / 2, -all_min[1], -(all_min[2] + all_max[2]) / 2])

    scene = trimesh.Scene()
    for mat_id, parts in out.items():
        info = mats.get(mat_id, {"color": [0.8, 0.8, 0.8, 1], "texture": None, "name": mat_id})
        if info["name"] in EXCLUDE:
            print(f"제외: {info['name']} (삼각형 {sum(len(p) for p, _, _ in parts) // 3:,}개)")
            continue
        P = np.concatenate([to_gltf_axes(p) for p, _, _ in parts]) + offset
        has_n = all(n is not None for _, n, _ in parts)
        N = np.concatenate([np.column_stack([n[:, 0], n[:, 2], -n[:, 1]]) for _, n, _ in parts]) if has_n else None
        tex = info["texture"]
        use_uv = tex is not None and all(u is not None for _, _, u in parts)
        mesh = trimesh.Trimesh(vertices=P.astype(np.float32), faces=np.arange(len(P)).reshape(-1, 3),
                               vertex_normals=None if N is None else N.astype(np.float32), process=False)
        r, g, b, a = info["color"]
        pbr = trimesh.visual.material.PBRMaterial(
            name=info["name"], baseColorFactor=[1.0, 1.0, 1.0, 1.0] if use_uv else [float(r), float(g), float(b), float(a)],  # 0~1 실수로 (정수 1은 1/255로 해석됨)
            baseColorTexture=tex if use_uv else None, metallicFactor=0.0, roughnessFactor=0.9,
            doubleSided=True, alphaMode="BLEND" if a < 0.999 else "OPAQUE")
        uv = np.concatenate([u for _, _, u in parts]).astype(np.float32) if use_uv else None
        mesh.visual = trimesh.visual.TextureVisuals(uv=uv, material=pbr)
        scene.add_geometry(mesh, node_name=info["name"])
    b = scene.bounds
    print(f"크기 {b[1][0] - b[0][0]:.1f} x {b[1][2] - b[0][2]:.1f} m, 높이 {b[1][1] - b[0][1]:.1f} m, 재질 묶음 {len(out)}개")
    return scene


if __name__ == "__main__":
    dae = Path(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    scene = build(dae)
    path = OUT / "kspodome.raw.glb"
    scene.export(path)
    print(f"저장: {path} ({path.stat().st_size / 1e6:.0f}MB)")
