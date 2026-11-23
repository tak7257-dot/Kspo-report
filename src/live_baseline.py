"""웹 실시간 줄의 비교 기준값: 2025년 공연 날, 월 x 요일유형 x 시각별 주차대수 중앙값.

웹은 "지금 주차장 N대"를 보여 줄 때, 기준값이 있으면 "2025년 이맘때 공연 날 M대"를 나란히 적는다.
- 입력: 2025 연계 데이터 (공공데이터포털, 한국체육산업개발주식회사)
- 공연 있는 날만, 결함일(이상일) 제외
- 8~9월은 집계 수준이 급감한 기간이라 제외 (export_web_data.py 와 같은 판단)
- 칸마다 표본이 3일 미만이면 null (중앙값을 믿기 어려움)
- "all": 8~9월을 뺀 1년 전체 기준 (그 달 값이 없을 때 웹이 대신 씀)
출력: web/app/data/live_baseline.json
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "app" / "data" / "live_baseline.json"
SKIP_MONTHS = {8, 9}
MIN_DAYS = 3
KIND = {"평일": "weekday", "주말·휴일": "weekend"}


def build(df: pd.DataFrame) -> dict:
    d = df[df["공연일"] & ~df["이상일"] & ~df["월"].isin(SKIP_MONTHS)]
    def table(part: pd.DataFrame) -> dict:
        g = part.groupby(["요일유형", "시"])["주차대수"].agg(["median", "count"])
        res = {}
        for kor, key in KIND.items():
            res[key] = [int(round(g.loc[(kor, h), "median"])) if (kor, h) in g.index and g.loc[(kor, h), "count"] >= MIN_DAYS
                        else None for h in range(24)]
        return res

    out = {str(int(m)): table(d[d["월"] == m]) for m in sorted(d["월"].unique())}
    # 그 달 표본이 모자랄 때(2025년 11~12월은 수집 중단 구간이 있음) 쓰는 1년 전체 기준
    out["all"] = table(d)
    return {"설명": "2025년 공연 날 월·요일유형·시각별 주차대수 중앙값(8~9월 제외, 표본 3일 미만 null)", "show_day": out}


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from metrics_2025 import load  # noqa: E402
    df, _, _ = load()
    data = build(df)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    filled = sum(v is not None for m in data["show_day"].values() for k in m.values() for v in k)
    print(f"live_baseline.json 저장 (값이 있는 칸 {filled}개)")
