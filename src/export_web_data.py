"""4단계(웹): 웹 서비스 '덜붐빌때'가 읽을 데이터 파일(JSON)을 만든다.

웹은 분석을 직접 하지 않고, 이 스크립트가 만든 작은 파일만 읽는다.
출력: web/app/data/
  show_profile.json  공연일 시간대별 주차 지수 (평일 / 주말·공휴일), 비 오는 날 보정 비율
  park_mode.json     공원 나들이용: 요일 x 시간대 붐빔 정도 (공연 있는 날 포함, 그 달 평균 = 1)
  parking_zones.json 주차장(P1A~P11)별 혼잡·만차 기록, 만차가 몰리는 시간대

모든 입력은 공공데이터포털 자료(한국체육산업개발주식회사)다.
"""
import glob
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics_2025 import load  # noqa: E402  (같은 달·요일유형·시각 기준 지수, 이상일 표시)

CLEAN = ROOT / "data" / "clean"
OUT = ROOT / "web" / "app" / "data"
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def show_profile():
    prof = pd.read_csv(CLEAN / "m25_profile.csv")
    weather = pd.read_csv(CLEAN / "m25_weather.csv").set_index("조건")
    kpi = json.loads((CLEAN / "m25_kpi.json").read_text(encoding="utf-8"))
    out = {}
    for key, name in [("weekday", "평일"), ("weekend", "주말·휴일")]:
        s = prof[prof["요일유형"] == name].set_index("시")["지수"].reindex(range(24))
        out[key] = [int(v) for v in s.interpolate().round()]
    return {
        "설명": "2025년 공연일 시간대별 주차장 차량 수. 같은 달·같은 요일유형·같은 시각의 공연 없는 날 = 100",
        "기간": kpi["기간"], "공연일수": kpi["공연일수"],
        "profile": out,
        "rain_factor": round(1 + float(weather.loc["비 옴", "mean"]) / 100, 3),
        "rain_hours": int(weather.loc["비 옴", "size"]),
        "levels": {"busy": 130, "very_busy": 200},
    }


def park_mode():
    df, _, _ = load()
    # 나들이 방문객도 그날 공연 인파를 똑같이 겪으므로 공연 유무와 상관없이 실제 붐빔을 본다 (결함일만 제외)
    # (2025년엔 공연 없는 토요일이 하루도 없어서, 공연 없는 날만으로는 주말을 계산할 수도 없다)
    calm = df[~df["이상일"]].copy()
    # 달마다 집계 수준이 달라서(8~9월 급감) 그 달 평균을 1로 놓고 비교
    calm["상대"] = calm["주차대수"] / calm.groupby("월")["주차대수"].transform("mean")
    g = calm.groupby(["요일번호", "시"])["상대"].mean().unstack().reindex(columns=range(24))
    days = calm.groupby("요일번호")["날짜"].nunique()
    return {
        "설명": "2025년 요일 x 시각별 주차장 차량 수(공연 있는 날 포함, 결함일 제외). 그 달 평균 = 1",
        "weekdays": WEEKDAYS,
        "hours": list(range(24)),
        "ratio": [[round(float(v), 2) for v in g.loc[d]] for d in range(7)],
        "days": [int(days.get(d, 0)) for d in range(7)],
    }


def parking_zones():
    f = glob.glob(str(ROOT / "data" / "raw" / "15164156_*.csv"))[0]
    z = pd.read_csv(f, encoding="cp949")
    z["일시"] = pd.to_datetime(z["등록일"] + " " + z["등록시간"], errors="coerce")
    t = z.pivot_table(index="주차구역", columns="혼잡도", values="일련번호", aggfunc="count", fill_value=0)
    full_days = z[z["혼잡도"] == "만차"].groupby("주차구역")["일시"].apply(lambda s: s.dt.date.nunique())
    zones = []
    for name, r in t.iterrows():
        total = int(r.sum())
        zones.append({"zone": name, "records": total, "full": int(r.get("만차", 0)), "busy": int(r.get("혼잡", 0)),
                      "free": int(r.get("원활", 0)), "full_share": round(r.get("만차", 0) / total, 2),
                      "full_days": int(full_days.get(name, 0))})
    zones.sort(key=lambda x: -x["full_share"])
    hours = z[z["혼잡도"] == "만차"]["일시"].dt.hour.value_counts().reindex(range(24), fill_value=0)
    return {
        "설명": "주차장 혼잡도 정보(공공데이터포털). 주차장별 '원활·혼잡·만차' 상태 기록",
        "기간": f"{z['일시'].min():%Y-%m-%d} ~ {z['일시'].max():%Y-%m-%d}",
        "기록일수": int(z["일시"].dt.date.nunique()),
        "zones": zones,
        "full_by_hour": [int(v) for v in hours],
        "한계": "기록 간격이 불규칙하고 주차장 위치 정보가 없어, 경향으로만 안내한다",
    }


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in [("show_profile", show_profile), ("park_mode", park_mode), ("parking_zones", parking_zones)]:
        data = fn()
        (OUT / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{name}.json 저장")
