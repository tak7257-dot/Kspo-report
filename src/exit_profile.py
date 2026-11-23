"""웹 '공연 날 하루' 퇴장 단계: 공연이 끝나고 차가 언제 몰려 나가는지 계산한다.

입력 (모두 공공데이터포털, 한국체육산업개발주식회사)
  1) 올림픽공원 입출차 정보 (2024-07, 차량 한 대마다 입차·출차 시각)
     → 10분 단위 출차 대수. 저녁(20:30 이후)에 출차가 뾰족하게 몰린 날을 '저녁 행사 날'로 보고,
       가장 몰린 10분을 기준(1.0)으로 10분 뒤, 20분 뒤 ... 출차 대수 비율의 중앙값을 낸다.
       (공연 일정 자료를 쓰지 않으므로 '어떤 공연이었는지'는 모른다. 몰림의 모양만 본다.)
  2) 2025 연계 데이터 (시간대별 주차대수, 공연 여부)
     → 공연 있는 날과 없는 날의 시간대별 주차대수 변화(= 그 시간에 빠져나간 차, 순감소)
  3) 공연행사정보 API (공연장, 공연 시간)
     → 공연장별 공연 시간 중앙값 (퇴장 시각 추정용)
출력: web/app/data/exit_profile.json
"""
import glob
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics_2025 import load  # noqa: E402

OUT = ROOT / "web" / "app" / "data" / "exit_profile.json"
SHARP = 2.5          # 그날 20:30 이후 10분 최대 출차가 같은 시간대 평균의 2.5배 이상이면 '뾰족한 몰림'
OFFSETS = list(range(0, 70, 10))
VENUE_KEYS = {"kspo-dome": "체조|KSPO", "handball": "핸드볼", "woori": "역도|우리금융", "jandi": "잔디", "lakeside": "수변"}


def exit_decay():
    f = glob.glob(str(ROOT / "data" / "raw" / "15138735_*.csv"))[0]
    d = pd.read_csv(f, encoding="cp949", parse_dates=["입차일시", "출차일시"]).dropna(subset=["출차일시"])
    cnt = d.groupby(d["출차일시"].dt.floor("10min")).size()
    start, end = cnt.index.min().normalize(), cnt.index.max().normalize() + pd.Timedelta(days=1)
    cnt = cnt.reindex(pd.date_range(start, end, freq="10min", inclusive="left"), fill_value=0)
    df = cnt.to_frame("n")
    df["day"] = df.index.normalize()
    df["tod"] = df.index.hour * 60 + df.index.minute
    peaks = []
    for day, g in df[df["tod"] >= 20 * 60 + 30].groupby("day"):
        s = g["n"]
        if s.mean() > 0 and s.max() / s.mean() >= SHARP:
            peaks.append((day, s.idxmax(), int(s.max())))
    rel = {o: [] for o in OFFSETS}
    for _, pk, mx in peaks:
        for o in OFFSETS:
            v = df["n"].get(pk + pd.Timedelta(minutes=o))
            if v is not None:
                rel[o].append(v / mx)
    return {
        "설명": "저녁에 출차가 가장 몰린 10분 = 1.0, 그 뒤 10분 단위 출차 대수 비율(중앙값)",
        "기간": f"{start:%Y-%m-%d} ~ {end - pd.Timedelta(days=1):%Y-%m-%d}",
        "저녁수": len(peaks),
        "최대출차_10분_중앙값": int(np.median([p[2] for p in peaks])),
        "offsets_min": OFFSETS,
        "ratio": [round(float(np.median(rel[o])), 2) for o in OFFSETS],
    }


def outflow_2025():
    df, _, _ = load()
    d = df[~df["이상일"]].sort_values("시각").copy()
    d["감소"] = -d.groupby("날짜")["주차대수"].diff()
    # 공연 여부는 '그날 공연이 있었는지'(공연일)로 나눈다
    out = {}
    for key, typ in [("weekday", "평일"), ("weekend", "주말·휴일")]:
        s = d[d["요일유형"] == typ]
        t = s.groupby(["공연일", "시"])["감소"].median().unstack(0).reindex(range(24))
        out[key] = {"show": [int(round(v)) if pd.notna(v) else None for v in t[True]],
                    "normal": [int(round(v)) if pd.notna(v) else None for v in t[False]]}
    return {"설명": "2025년 시간대별로 주차장에서 줄어든 차량 수(순감소, 중앙값). 공연 있는 날 / 없는 날", **out}


def show_minutes():
    items = []
    for f in sorted(glob.glob(str(ROOT / "data" / "raw" / "kscperf" / "*.json"))):
        j = json.loads(Path(f).read_text(encoding="utf-8"))

        def find(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == "item":
                        return v
                    r = find(v)
                    if r is not None:
                        return r
            return None
        it = find(j)
        items += [it] if isinstance(it, dict) else (it or [])
    df = pd.DataFrame(items)

    def minutes(s):
        s = str(s)
        h, m = re.search(r"(\d+)\s*시간", s), re.search(r"(\d+)\s*분", s)
        return (int(h.group(1)) * 60 if h else 0) + (int(m.group(1)) if m else 0) if (h or m) else None
    df["분"] = df["extent"].map(minutes)
    out = {}
    for vid, pat in VENUE_KEYS.items():
        s = df[df["spatial"].astype(str).str.contains(pat)]["분"].dropna()
        s = s[(s >= 40) & (s <= 300)]
        out[vid] = {"median": int(s.median()), "q1": int(s.quantile(.25)), "q3": int(s.quantile(.75)), "n": int(len(s))}
    return {"설명": "공연행사정보 API의 공연 시간(extent) 중앙값, 분", **out}


if __name__ == "__main__":
    data = {"exit_decay": exit_decay(), "outflow_2025": outflow_2025(), "show_minutes": show_minutes()}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    e = data["exit_decay"]
    print(f"저녁 {e['저녁수']}일, 최대 10분 출차 중앙값 {e['최대출차_10분_중앙값']}대, 감소 비율 {dict(zip(e['offsets_min'], e['ratio']))}")
    print("공연 시간:", {k: v["median"] for k, v in data["show_minutes"].items() if k != "설명"})
