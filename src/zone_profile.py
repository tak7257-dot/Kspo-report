"""2025년 입출차정보(전체구역)로 공연 날 주차장 흐름을 문(구역)별로 본다.

입력 (모두 한국체육산업개발주식회사 공공데이터)
  1) 올림픽공원 입출차정보(전체구역) API_CPM_008 — 2025년, 차 한 대마다 들어온 문·입차 시각·나간 문·출차 시각
     (src/fetch_parking_zone.py 로 받은 data/raw/zone/*.csv.gz. 용량이 커서 git에는 결과만 올린다)
  2) 2025 연계 데이터 — 그날 공연이 있었는지(공연일), 요일유형, 결함일(이상일)
계산
  - exit_decay: 공연 날 저녁(20:30 이후) 출차가 뾰족하게 몰린 날마다 가장 몰린 10분 = 1.0,
    10분 뒤·20분 뒤 ... 출차 대수 비율의 중앙값 (2024-07 한 달 → 2025년 공연 날 전체로 넓힘)
  - gates: 공연 날과 공연 없는 날(같은 요일유형)의 저녁 입차(17~19시)·밤 출차(21~23시) 문별 비중과 하루 평균 대수
  - stay: 공연 날 16~19시에 들어온 차가 머문 시간(분) 사분위
출력: web/app/data/zone_profile.json
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

RAW = ROOT / "data" / "raw" / "zone"
OUT = ROOT / "web" / "app" / "data" / "zone_profile.json"
SHARP = 2.5
OFFSETS = list(range(0, 70, 10))
ARRIVE = (17, 20)   # 17:00 ~ 19:59 입차
LEAVE = (21, 24)    # 21:00 ~ 23:59 출차
STAY_IN = (16, 20)  # 16:00 ~ 19:59 입차한 차의 머문 시간
KIND = {"평일": "weekday", "주말·휴일": "weekend"}


def gate_zone(s: pd.Series) -> pd.Series:
    """'동2문입구#1', '북2문CMB' → '동2', '북2'."""
    return s.astype(str).str.extract(r"^(.+?)문", expand=False)


def prepare(raw: pd.DataFrame) -> pd.DataFrame:
    d = raw.copy()
    d["in_time"] = pd.to_datetime(d["in_time"], errors="coerce")
    d["out_time"] = pd.to_datetime(d["out_time"], errors="coerce")
    d["in_zone"] = gate_zone(d["in_gate"])
    d["out_zone"] = gate_zone(d["out_gate"])
    return d.dropna(subset=["in_time", "out_time", "in_zone", "out_zone"])


def exit_decay(d: pd.DataFrame, show_days: set) -> dict:
    out = d[d["out_time"].dt.normalize().isin(show_days)]
    cnt = out.groupby(out["out_time"].dt.floor("10min")).size()
    peaks, rel = [], {o: [] for o in OFFSETS}
    for day in sorted(show_days):
        idx = pd.date_range(day + pd.Timedelta(minutes=20 * 60 + 30), day + pd.Timedelta(days=1), freq="10min", inclusive="left")
        s = cnt.reindex(idx, fill_value=0)
        if s.mean() > 0 and s.max() / s.mean() >= SHARP:
            pk, mx = s.idxmax(), int(s.max())
            peaks.append((day, pk, mx))
            for o in OFFSETS:
                rel[o].append(cnt.get(pk + pd.Timedelta(minutes=o), 0) / mx)
    if not peaks:
        return {}
    return {
        "설명": "공연 날 저녁 출차가 가장 몰린 10분 = 1.0, 그 뒤 10분 단위 출차 대수 비율(중앙값)",
        "자료": "올림픽공원 입출차정보(전체구역) 2025",
        "저녁수": len(peaks),
        "최대출차_10분_중앙값": int(np.median([p[2] for p in peaks])),
        "최대출차_시각_중앙값": pd.Series([p[1].hour * 60 + p[1].minute for p in peaks]).median().item(),
        "offsets_min": OFFSETS,
        "ratio": [round(float(np.median(rel[o])), 2) for o in OFFSETS],
    }


def _window_share(times: pd.Series, zones: pd.Series, days: set, hours: tuple) -> dict:
    m = times.dt.normalize().isin(days) & (times.dt.hour >= hours[0]) & (times.dt.hour < hours[1])
    z = zones[m]
    n_days = max(len(days), 1)
    vc = z.value_counts()
    total = int(vc.sum())
    return {
        "일수": len(days),
        "하루평균": round(total / n_days, 1),
        "zones": [{"zone": k, "share": round(v / total, 3), "per_day": round(v / n_days, 1)} for k, v in vc.items()] if total else [],
    }


def gates(d: pd.DataFrame, day_info: pd.DataFrame) -> dict:
    res = {}
    for kor, key in KIND.items():
        part = day_info[day_info["요일유형"] == kor]
        show = set(part.loc[part["공연일"], "날짜"])
        normal = set(part.loc[~part["공연일"], "날짜"])
        res[key] = {
            "arrive": {"hours": list(ARRIVE), "show": _window_share(d["in_time"], d["in_zone"], show, ARRIVE),
                       "normal": _window_share(d["in_time"], d["in_zone"], normal, ARRIVE)},
            "leave": {"hours": list(LEAVE), "show": _window_share(d["out_time"], d["out_zone"], show, LEAVE),
                      "normal": _window_share(d["out_time"], d["out_zone"], normal, LEAVE)},
        }
    return res


def stay(d: pd.DataFrame, show_days: set) -> dict:
    m = d["in_time"].dt.normalize().isin(show_days) & (d["in_time"].dt.hour >= STAY_IN[0]) & (d["in_time"].dt.hour < STAY_IN[1])
    mins = (d.loc[m, "out_time"] - d.loc[m, "in_time"]).dt.total_seconds() / 60
    mins = mins[(mins > 0) & (mins <= 24 * 60)]
    if mins.empty:
        return {}
    return {"설명": "공연 날 16~19시에 들어온 차가 머문 시간(분)", "대수": int(len(mins)),
            "q1": int(mins.quantile(.25)), "median": int(mins.median()), "q3": int(mins.quantile(.75))}


def day_table() -> pd.DataFrame:
    from metrics_2025 import load
    df, _, _ = load()
    t = df.drop_duplicates("날짜")[["날짜", "요일유형", "공연일", "이상일"]].copy()
    t["날짜"] = pd.to_datetime(t["날짜"]).dt.normalize()
    return t[~t["이상일"]]


def load_raw() -> pd.DataFrame:
    files = sorted(glob.glob(str(RAW / "zone_p*.csv.gz")))
    if not files:
        sys.exit("data/raw/zone/ 이 비어 있습니다. 먼저 python src/fetch_parking_zone.py 를 실행하세요.")
    return pd.concat((pd.read_csv(f) for f in files), ignore_index=True), len(files)


if __name__ == "__main__":
    raw, n_files = load_raw()
    d = prepare(raw)
    days = day_table()
    show_days = set(days.loc[days["공연일"], "날짜"])
    data = {
        "자료": "올림픽공원 입출차정보(전체구역), 2025 연계 데이터 (공공데이터포털, 한국체육산업개발주식회사)",
        "기간": f"{d['in_time'].min():%Y-%m-%d} ~ {d['in_time'].max():%Y-%m-%d}",
        "대수": int(len(d)),
        "페이지": n_files,
        "exit_decay": exit_decay(d, show_days),
        "gates": gates(d, days),
        "stay": stay(d, show_days),
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    e = data["exit_decay"]
    print(f"{data['기간']} {data['대수']:,}대 (페이지 {n_files})")
    if e:
        print(f"공연 날 저녁 {e['저녁수']}일, 최대 10분 출차 중앙값 {e['최대출차_10분_중앙값']}대, 비율 {dict(zip(e['offsets_min'], e['ratio']))}")
    print("머문 시간:", data["stay"])
