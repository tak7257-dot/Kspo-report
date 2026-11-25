"""오늘 예보(실시간 보정)가 실제로 나은지 2025년 공연 날 기록으로 되짚어 본다.

방법: 공연 날마다 '지금 시각'의 주차 대수를 2025년 공연 날 같은 시각 중앙값과 견줘 편차를 구하고,
      그 편차를 몇 시간 뒤 중앙값에 곱해 예보한 값과 실제 값을 비교한다.
      (비교: 편차 없이 중앙값만 쓴 예보) — 오차는 |예보 − 실제| / 실제 의 중앙값.
입력: 2025 연계 데이터 (공공데이터포털), 결함일·8~9월(집계 급감) 제외
출력: web/app/data/nowcast_check.json  (웹 사용법과 기획서에 인용)
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "app" / "data" / "nowcast_check.json"
PAIRS = [(13, 17), (14, 18), (15, 18), (16, 19), (17, 20), (12, 18)]
KIND = {"평일": "weekday", "주말·휴일": "weekend"}


def backtest(df: pd.DataFrame, pairs=PAIRS) -> dict:
    d = df[df["공연일"] & ~df["이상일"] & ~df["월"].isin([8, 9])]
    out = {}
    for kor, key in KIND.items():
        p = d[d["요일유형"] == kor].pivot_table(index="날짜", columns="시", values="주차대수")
        if p.empty:
            continue
        base = p.median()
        rows = []
        for now, tgt in pairs:
            if now not in p or tgt not in p:
                continue
            x = p[[now, tgt]].dropna()
            corrected = base[tgt] * x[now] / base[now]
            rows.append({
                "now": now, "target": tgt, "days": int(len(x)),
                "err_past": round(float(((base[tgt] - x[tgt]).abs() / x[tgt]).median()), 3),
                "err_corrected": round(float(((corrected - x[tgt]).abs() / x[tgt]).median()), 3),
            })
        out[key] = rows
    return out


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from metrics_2025 import load  # noqa: E402
    df, _, _ = load()
    data = {"설명": "2025년 공연 날로 되짚어 본 오늘 예보 오차(중앙값). err_past = 과거 중앙값만, err_corrected = 실시간 편차로 보정",
            **backtest(df)}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in KIND.values():
        for r in data.get(k, []):
            print(f"{k} {r['now']}시→{r['target']}시 ({r['days']}일): {r['err_past']:.0%} → {r['err_corrected']:.0%}")
