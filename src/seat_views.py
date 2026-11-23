"""웹 '내 자리에서 보기': KSPO DOME 3D 모델 안의 객석 구역별 카메라 위치를 만든다.

근거 (기관 제공 3D 모델 「올림픽공원 공연장 실감형 콘텐츠」의 객석 부품 위치를 직접 측정, 단위 m)
  - 모델 좌표: X 오른쪽, Y 위, Z 앞. 경기장 중심이 원점.
  - 1층 객석: 중심에서 25~43m, 높이 0.9~6.4m
  - 2층 객석: 중심에서 46~58m, 높이 6.2~12.0m
  - 객석이 +Z 끝(각도 0° 부근)에만 드문드문해, 무대가 놓이는 끝을 +Z로 본다.
가정
  - 무대는 +Z 끝에 놓인 '끝 무대'로 가정한다. 실제 무대 위치와 객석 배치는 공연마다 다르다.
  - 눈높이 = 그 자리 객석 바닥 + 1.2m (앉은 키)
  - 좌석배치도(홈페이지 자료)는 쓰지 않는다. 구역 이름도 공식 구역명이 아니라 방향으로만 붙인다.
출력: web/app/data/seat_views.json  (model-viewer의 camera-orbit / camera-target 값)
"""
import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "web" / "app" / "data" / "seat_views.json"
STAGE = (0.0, 3.0, 20.0)   # 카메라가 바라보는 점: 무대 쪽 끝 바닥 위 3m
EYE = 1.2


def seat_height(r, tier):
    """객석은 계단식이라 중심에서 멀수록 높다 (측정한 범위를 직선으로 이음)."""
    if tier == 1:
        return 0.9 + (r - 25) / 18 * 5.5
    return 6.2 + (r - 46.5) / 12 * 5.8


def on_ring(angle, r, tier):
    """angle: 무대(+Z) 방향이 0°, 관객이 무대를 볼 때 왼쪽(+X)이 90°."""
    a = math.radians(angle)
    return (r * math.sin(a), seat_height(r, tier) + EYE, r * math.cos(a))


ZONES = [
    # id, 이름, 층, 눈 위치
    ("floor-front", "플로어 앞쪽", "플로어", (0.0, 0.7 + 1.6, 6.0)),   # 플로어는 서 있거나 낮은 의자
    ("floor-back", "플로어 뒤쪽", "플로어", (0.0, 0.7 + 1.6, -16.0)),
    ("l1-left", "1층 왼쪽", "1층", on_ring(90, 33, 1)),
    ("l1-center", "1층 정면", "1층", on_ring(180, 33, 1)),
    ("l1-right", "1층 오른쪽", "1층", on_ring(270, 33, 1)),
    ("l2-left", "2층 왼쪽", "2층", on_ring(90, 52, 2)),
    ("l2-center", "2층 정면", "2층", on_ring(180, 52, 2)),
    ("l2-right", "2층 오른쪽", "2층", on_ring(270, 52, 2)),
]


def view(zid, label, tier, eye):
    d = [eye[i] - STAGE[i] for i in range(3)]
    r = math.sqrt(sum(c * c for c in d))
    theta = math.degrees(math.atan2(d[0], d[2]))
    phi = math.degrees(math.acos(d[1] / r))
    return {
        "id": zid, "label": label, "tier": tier,
        "eye_m": [round(c, 1) for c in eye],
        "to_stage_m": round(math.hypot(d[0], d[2])),          # 무대 쪽 끝까지 수평 거리
        "height_m": 0.0 if tier == "플로어" else round(eye[1] - EYE - 0.7, 1),   # 플로어 바닥보다 얼마나 높은 자리인지
        "orbit": f"{theta:.1f}deg {phi:.1f}deg {r:.1f}m",
        "target": f"{STAGE[0]}m {STAGE[1]}m {STAGE[2]}m",
    }


if __name__ == "__main__":
    data = {
        "설명": "KSPO DOME 3D 모델의 객석 구역별 시점. 무대는 +Z 끝 '끝 무대'로 가정",
        "stage_m": list(STAGE),
        "views": [view(*z) for z in ZONES],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    for v in data["views"]:
        print(f"{v['label']:8} 무대까지 {v['to_stage_m']:>3}m  높이 {v['height_m']:>4}m  {v['orbit']}")
