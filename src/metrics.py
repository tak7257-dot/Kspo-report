"""3단계: 정리된 데이터(visits.csv)로 보고서에 들어갈 지표 표를 만든다.

입력:  data/clean/visits.csv
출력:  data/clean/ 아래 지표 CSV 여러 개 + 화면에 핵심 숫자 출력

만드는 지표
  1) daily       : 날짜별 입차 대수
  2) heatmap     : 요일 x 입차시각별 '하루 평균' 입차 대수
  3) occupancy   : 시간대별 동시 주차 대수(그 시간에 주차장 안에 있던 차) - 평일/주말 평균
  4) kpi         : 한 줄 요약 숫자
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean"
WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def load() -> pd.DataFrame:
    df = pd.read_csv(CLEAN / "visits.csv", parse_dates=["입차시각", "출차시각", "날짜"])
    return df


def daily_entries(df):
    d = df.groupby("날짜").size().rename("입차대수").reset_index()
    d["요일"] = d["날짜"].dt.dayofweek.map(lambda i: WEEKDAY_KO[i])
    d["주말"] = d["날짜"].dt.dayofweek >= 5
    return d


def weekday_hour_heatmap(df):
    # 요일마다 날짜 수가 달라서(예: 7월은 월·화·수가 5번) '합계'가 아닌 '하루 평균'으로 비교
    counts = df.groupby(["요일", "입차시"]).size()
    days_per_weekday = df.groupby("요일")["날짜"].nunique()
    avg = counts.div(days_per_weekday, level="요일").rename("평균입차").reset_index()
    table = avg.pivot(index="요일", columns="입차시", values="평균입차").reindex(WEEKDAY_KO).fillna(0)
    return table


def hourly_occupancy(df):
    """그 시간대에 주차장 안에 있던 차량 수의 '최대값'을 시간별로 구한다.
    방법: 입차 = +1, 출차 = -1 이벤트를 시간순으로 누적합 -> 매 순간의 재차 대수."""
    events = pd.concat([
        pd.Series(1, index=df["입차시각"]),
        pd.Series(-1, index=df["출차시각"]),
    ]).sort_index()
    inside = events.cumsum()
    hourly = inside.resample("h").max().ffill()
    # 7/1 이전에 들어온 차는 데이터에 없으므로 첫날은 과소 집계됨 -> 7/2부터 사용
    # 7/31 입차 차량의 8/1 출차 기록만 남는 구간도 제외
    hourly = hourly["2024-07-02":"2024-07-31"]
    h = hourly.rename("재차대수").reset_index().rename(columns={"index": "시각"})
    h.columns = ["시각", "재차대수"]
    h["시"] = h["시각"].dt.hour
    h["구분"] = h["시각"].dt.dayofweek.map(lambda i: "주말" if i >= 5 else "평일")
    return h.groupby(["구분", "시"])["재차대수"].mean().round(0).reset_index(), h


def kpis(df, daily, occ_raw):
    normal = df[df["체류구분"] == "일반"]
    peak_row = occ_raw.loc[occ_raw["재차대수"].idxmax()]
    top_day = daily.loc[daily["입차대수"].idxmax()]
    return {
        "기간": f"{df['날짜'].min():%Y-%m-%d} ~ {df['날짜'].max():%Y-%m-%d}",
        "총입차": int(len(df)),
        "일평균입차": int(round(daily["입차대수"].mean())),
        "주말일평균": int(round(daily[daily["주말"]]["입차대수"].mean())),
        "평일일평균": int(round(daily[~daily["주말"]]["입차대수"].mean())),
        "최다입차일": f"{top_day['날짜']:%m/%d}({top_day['요일']})",
        "최다입차일대수": int(top_day["입차대수"]),
        "최대재차대수": int(peak_row["재차대수"]),
        "최대재차시각": f"{peak_row['시각']:%m/%d %H}시",
        "체류중앙값분": int(normal["체류분"].median()),
        "단시간비율": round((df["체류구분"] == "단시간(5분 미만)").mean() * 100, 1),
    }


if __name__ == "__main__":
    df = load()
    daily = daily_entries(df)
    heat = weekday_hour_heatmap(df)
    occ, occ_raw = hourly_occupancy(df)
    k = kpis(df, daily, occ_raw)

    daily.to_csv(CLEAN / "m_daily.csv", index=False, encoding="utf-8-sig")
    heat.to_csv(CLEAN / "m_heatmap.csv", encoding="utf-8-sig")
    occ.to_csv(CLEAN / "m_occupancy.csv", index=False, encoding="utf-8-sig")
    pd.Series(k).to_json(CLEAN / "m_kpi.json", force_ascii=False, indent=1)

    for key, v in k.items():
        print(f"{key:>10}: {v}")
    print("\n[시간대별 평균 최대 재차대수]")
    print(occ.pivot(index="시", columns="구분", values="재차대수").T.to_string())
