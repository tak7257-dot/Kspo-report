"""3단계(공연장): 공연 '시작 시각 기준'으로 공연장별 주차 혼잡 곡선을 만든다.

입력:  data/clean/hourly_2025.csv, data/clean/show_venue_2025.csv
       (지수 계산은 metrics_2025.load() 를 그대로 사용: 같은 달·요일유형·시각의 공연 없는 날 = 100)
출력:  data/clean/mv_relative.csv  (공연장 x 시작 기준 상대시각별 평균 지수)
       data/clean/mv_summary.csv   (공연장별 요약: 공연일 수, 대표 시작 시각, 혼잡 시작 시점, 정점)

원칙
  - 같은 날 여러 공연장에서 공연이 겹치면 '주 공연장' 하나로 본다: PRIORITY 순서(규모가 큰 곳 우선)
    (공식 수용인원: KSPO DOME 15,000석, 핸드볼경기장 5,003석 / 야외 페스티벌은 관람객 1.5~2만 명 규모)
  - 상대시각 = 시각 - 시작시  (예: 18시 시작 공연의 15시 = -3)
  - 혼잡 시작 = 지수가 처음으로 150(평소의 1.5배)을 넘는 상대시각
  - 공연일이 MIN_DAYS 미만인 공연장은 요약에서 '표본 부족'으로 표시
"""
from pathlib import Path

import pandas as pd

from metrics_2025 import load

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean"
REL = range(-6, 5)   # 시작 6시간 전 ~ 4시간 후
MIN_DAYS = 5
PRIORITY = ["야외·기타시설", "KSPO DOME", "SK핸드볼경기장", "올림픽홀", "우리금융아트홀", "K-아트홀", "뮤즈라이브",
            "88잔디마당", "수변무대"]


def day_venue(sv: pd.DataFrame) -> pd.DataFrame:
    ok = sv[sv["매칭"] != "미매칭"].dropna(subset=["공연장", "시작시"])
    ok = ok[ok["공연장"].isin(PRIORITY)].copy()
    ok["순위"] = ok["공연장"].map(PRIORITY.index)
    main = ok.sort_values(["날짜", "순위", "시작시"]).groupby("날짜").first().reset_index()
    main["겹침"] = main["날짜"].map(ok.groupby("날짜")["공연장"].nunique()) > 1
    return main[["날짜", "공연장", "시작시", "가까운주차장", "겹침"]]


if __name__ == "__main__":
    df, bad, period = load()
    sv = pd.read_csv(CLEAN / "show_venue_2025.csv", parse_dates=["날짜"])
    dv = day_venue(sv)
    dv["날짜"] = pd.to_datetime(dv["날짜"])

    x = df[~df["이상일"] & df["지수"].notna()].merge(dv, on="날짜")
    x["상대시각"] = x["시"] - x["시작시"].astype(int)
    x = x[x["상대시각"].isin(REL)]
    rel = (x.groupby(["공연장", "요일유형", "상대시각"])["지수"].agg(["mean", "size"]).round(0)
             .rename(columns={"mean": "지수", "size": "표본"}).reset_index())
    rel.to_csv(CLEAN / "mv_relative.csv", index=False, encoding="utf-8-sig")

    rows = []
    for (venue, dtype), g in rel.groupby(["공연장", "요일유형"]):
        days = x[(x["공연장"] == venue) & (x["요일유형"] == dtype)]["날짜"].nunique()
        s = g.set_index("상대시각")["지수"]
        over = s[s >= 150]
        rows.append({
            "공연장": venue, "요일유형": dtype, "공연일수": days,
            "대표시작시": int(dv[dv["공연장"] == venue]["시작시"].mode().iloc[0]),
            "혼잡시작_상대시각": int(over.index.min()) if len(over) else None,
            "정점_상대시각": int(s.idxmax()), "정점지수": int(s.max()),
            "판단": "표본 부족" if days < MIN_DAYS else "",
        })
    summ = pd.DataFrame(rows).sort_values(["요일유형", "공연일수"], ascending=[True, False])
    summ.to_csv(CLEAN / "mv_summary.csv", index=False, encoding="utf-8-sig")

    print(f"공연일 {len(dv)}일 (그중 공연장 겹침 {int(dv['겹침'].sum())}일은 주 공연장 기준), 분석 가능 {x['날짜'].nunique()}일")
    print(summ.to_string(index=False))
