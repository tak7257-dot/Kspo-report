"""3단계(2025): 시간대별 요약(hourly_2025.csv)으로 공연·날씨가 방문 흐름에 주는 영향을 계산한다.

입력:  data/clean/hourly_2025.csv
출력:  data/clean/m25_*.csv, m25_kpi.json

용어
  - 주차대수 = 그 시간 주차장 안에 있는 차량 수(재차대수). 새벽에도 수백 대로 평평한 것으로 확인.
  - 공연일   = 그날 하루 중 한 시간이라도 공연명이 있는 날
  - 비교 기준 = '같은 달 + 같은 요일유형(평일/주말·휴일)'의 공연 없는 날 평균
                (공연이 주말에 몰려 있어서, 그냥 비교하면 주말 효과가 공연 효과로 잘못 잡힘)

지표
  1) m25_profile   : 요일유형 x 공연여부별 시간대 평균 주차대수 (곡선 비교용)
  2) m25_shows     : 공연일별 관람객수, 피크 주차대수, 비교 기준 대비 증가율
  3) m25_weather   : 강수 여부, 기온 구간별 평균 주차대수 (같은 시간대·요일유형 기준으로 보정)
  4) m25_monthly   : 월별 하루 평균 피크 주차대수
  5) m25_kpi.json  : 요약 숫자
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean"


def load():
    df = pd.read_csv(CLEAN / "hourly_2025.csv", parse_dates=["시각"])
    df["날짜"] = df["시각"].dt.normalize()
    df["월"] = df["시각"].dt.month
    df["주말휴일"] = (df["요일번호"] >= 5) | df["휴일여부"]
    df["요일유형"] = np.where(df["주말휴일"], "주말·휴일", "평일")
    show_days = set(df.loc[df["공연있음"], "날짜"])
    df["공연일"] = df["날짜"].isin(show_days)

    # 이상일(데이터 결함) → 분석에서 제외. '방문이 적은 날'(연휴·악천후)은 결함이 아니므로 남긴다.
    #   ① 기록이 20시간 미만인 날 (예: 11월 중순~, 12월 중순~ 수집 중단 구간)
    #   ② 낮에도 새벽(0~3시) 수준에서 오르지 않는 날 = 피크가 새벽 평균의 1.3배 미만 (예: 매달 말일)
    day = df.groupby("날짜").agg(피크=("주차대수", "max"), 시간수=("주차대수", "size"), 월=("월", "first"))
    dawn = df[df["시"] <= 3].groupby("날짜")["주차대수"].mean()
    day["새벽"] = dawn
    bad = day[(day["시간수"] < 20) | (day["피크"] < 1.3 * day["새벽"])]
    df["이상일"] = df["날짜"].isin(bad.index)

    # 집계 수준 구간: 월별 피크 중앙값이 전달 대비 2배 이상/절반 이하로 바뀌면 새 구간 (예: 8~9월)
    ok_day = day[~day.index.isin(bad.index)]
    lvl = ok_day.groupby("월")["피크"].median()
    period, pid = {}, 0
    for i, m in enumerate(lvl.index):
        if i and not (0.5 <= lvl[m] / lvl[lvl.index[i - 1]] <= 2):
            pid += 1
        period[m] = pid
    df["구간"] = df["월"].map(period)

    # 지수: 같은 달 + 같은 요일유형 + 같은 시각의 '공연 없는 정상일' 평균 = 100
    #  → 달마다 집계 수준이 달라도(예: 8월 급감) 공연·날씨 효과를 공정하게 비교
    #  같은 달에 그런 날이 없으면(예: 주말마다 공연) 같은 구간의 앞뒤 달(±1개월) 평균으로 보완
    normal = df[~df["이상일"] & ~df["공연일"]]
    ref = baseline(normal, "주차대수", ["요일유형", "시"], period)
    df = df.join(ref, on=["월", "요일유형", "시"])
    df["지수"] = df["주차대수"] / df["기준"] * 100
    return df, bad, period


def baseline(frame, col, keys, period):
    """같은 달 평균, 없으면 같은 구간 앞뒤 달 평균. 결과: index=[월]+keys, 컬럼 기준/기준출처"""
    same = frame.groupby(["월", *keys])[col].mean()
    out = []
    for m in sorted(period):
        near = [x for x in (m - 1, m + 1) if period.get(x) == period[m]]
        near_mean = frame[frame["월"].isin(near)].groupby(keys)[col].mean()
        this = same.xs(m, level="월") if m in same.index.get_level_values("월") else near_mean.iloc[0:0]
        both = pd.DataFrame({"same": this, "near": near_mean})
        both["기준"] = both["same"].fillna(both["near"])
        both["기준출처"] = np.where(both["same"].notna(), "같은 달", np.where(both["near"].notna(), "앞뒤 달", "없음"))
        both["월"] = m
        out.append(both.reset_index())
    res = pd.concat(out, ignore_index=True).dropna(subset=["기준"])
    return res.set_index(["월", *keys])[["기준", "기준출처"]]


def daily_table(df, period):
    d = df[~df["이상일"]].groupby("날짜").agg(
        월=("월", "first"), 요일유형=("요일유형", "first"), 공연일=("공연일", "first"),
        피크주차=("주차대수", "max"), 평균주차=("주차대수", "mean"),
        관람객수=("공연관람객수", "max"), 강수합=("강수량", "sum"), 평균기온=("기온", "mean"),
        공연명=("공연명", lambda s: next((x for x in s if isinstance(x, str) and x), "")),
    ).reset_index()
    # 비교 기준: 같은 달(없으면 같은 구간 앞뒤 달)·같은 요일유형의 공연 없는 날 평균 피크
    base = baseline(d[~d["공연일"]], "피크주차", ["요일유형"], period).rename(columns={"기준": "기준피크"})
    d = d.join(base, on=["월", "요일유형"])
    d["증가율"] = (d["피크주차"] / d["기준피크"] - 1) * 100
    return d


def profiles(df):
    # 공연일의 시간대별 지수(같은 달 공연 없는 날 = 100) 평균
    ok = df[~df["이상일"] & df["공연일"]]
    return ok.groupby(["요일유형", "시"])["지수"].mean().round(0).reset_index()


def shows(daily):
    s = daily[daily["공연일"]].copy()
    return s.sort_values("피크주차", ascending=False)


def weather(df):
    # 지수(같은 달·요일유형·시각 평균=100) - 100 = 평균 대비 % → 달·시간대 효과를 걷어냄
    df = df.assign(상대=df["지수"] - 100)
    day = df[(df["시"] >= 9) & (df["시"] <= 20) & ~df["공연일"] & ~df["이상일"]]  # 공연·이상일 제외, 주간만
    rain = day.groupby(day["강수량"] > 0)["상대"].agg(["mean", "size"]).rename(index={False: "비 안 옴", True: "비 옴"})
    bins = [-30, 0, 10, 20, 28, 45]
    labels = ["0℃ 미만", "0~10℃", "10~20℃", "20~28℃", "28℃ 이상"]
    temp = day.groupby(pd.cut(day["기온"], bins=bins, labels=labels), observed=False)["상대"].agg(["mean", "size"])
    out = pd.concat([rain.assign(구분="강수"), temp.assign(구분="기온")])
    out.index.name = "조건"
    return out.round(1).reset_index()


def monthly(daily):
    return daily.groupby("월").agg(피크평균=("피크주차", "mean"), 공연일수=("공연일", "sum"),
                                   일수=("날짜", "size")).round(0).reset_index()


def quality_notes(bad, mon):
    notes = []
    if len(bad):
        days = ", ".join(f"{d:%m/%d}" for d in bad.index)
        notes.append(f"데이터 결함으로 판단한 {len(bad)}일을 제외했습니다(기록 20시간 미만, 또는 낮에도 새벽 수준에서 오르지 않는 날). "
                     f"연휴처럼 실제로 방문이 적은 날은 제외하지 않았습니다. 제외일: {days}")
    m = mon.set_index("월")["피크평균"]
    jumps = [(a, b) for a, b in zip(m.index[:-1], m.index[1:]) if m[b] < 0.5 * m[a] or m[b] > 2 * m[a]]
    for a, b in jumps:
        notes.append(f"{a}월 → {b}월 사이 하루 피크 평균이 {int(m[a]):,}대 → {int(m[b]):,}대로 급변했습니다. "
                     f"집계 범위 변경 가능성이 있어 월 간 직접 비교는 하지 않고, 모든 비교를 같은 달 안에서 했습니다(담당 기관 확인 필요).")
    return notes


def kpis(df, daily, s):
    fit = s.dropna(subset=["관람객수", "피크주차"])
    fit = fit[fit["관람객수"] > 0]
    slope = np.polyfit(fit["관람객수"], fit["피크주차"], 1)[0] if len(fit) >= 5 else float("nan")
    corr = fit["관람객수"].corr(fit["피크주차"]) if len(fit) >= 5 else float("nan")
    by_type = s.groupby("요일유형")["증가율"].median()
    prof = profiles(df).set_index(["요일유형", "시"])["지수"]
    def eve(t):  # 저녁(18~21시) 평균 지수와 가장 높은 시각
        try:
            p = prof.loc[t].loc[18:21]
            return round(float(p.mean()), 0), int(p.idxmax()), round(float(p.max()), 0)
        except KeyError:
            return float("nan"), -1, float("nan")
    we, wd = eve("주말·휴일"), eve("평일")
    return {
        "저녁지수_주말": we[0], "저녁최고시_주말": we[1], "저녁최고지수_주말": we[2],
        "저녁지수_평일": wd[0], "저녁최고시_평일": wd[1], "저녁최고지수_평일": wd[2],
        "기간": f"{df['시각'].min():%Y-%m-%d} ~ {df['시각'].max():%Y-%m-%d}",
        "시간대수": int(len(df)), "일수": int(daily["날짜"].nunique()),
        "공연일수": int(daily["공연일"].sum()),
        "기준있는공연일": int(s["증가율"].notna().sum()),
        "앞뒤달기준공연일": int((s["기준출처"] == "앞뒤 달").sum()),
        "최대주차": int(df["주차대수"].max()),
        "최대주차시각": f"{df.loc[df['주차대수'].idxmax(), '시각']:%m/%d %H}시",
        "공연일피크증가율_중앙값": round(float(s["증가율"].median()), 1),
        "공연일피크증가율_평일": round(float(by_type.get("평일", float("nan"))), 1),
        "공연일피크증가율_주말": round(float(by_type.get("주말·휴일", float("nan"))), 1),
        "관객1만명당_피크주차": round(float(slope) * 10000, 0),
        "관객_피크_상관": round(float(corr), 2),
    }


if __name__ == "__main__":
    df, bad, period = load()
    daily = daily_table(df, period)
    s = shows(daily)
    w = weather(df)
    m = monthly(daily)
    k = kpis(df, daily, s)

    profiles(df).to_csv(CLEAN / "m25_profile.csv", index=False, encoding="utf-8-sig")
    s.to_csv(CLEAN / "m25_shows.csv", index=False, encoding="utf-8-sig")
    w.to_csv(CLEAN / "m25_weather.csv", index=False, encoding="utf-8-sig")
    m.to_csv(CLEAN / "m25_monthly.csv", index=False, encoding="utf-8-sig")
    notes = quality_notes(bad, m)
    (CLEAN / "m25_notes.json").write_text(json.dumps(notes, ensure_ascii=False, indent=1), encoding="utf-8")
    (CLEAN / "m25_kpi.json").write_text(json.dumps(k, ensure_ascii=False, indent=1), encoding="utf-8")

    for key, v in k.items():
        print(f"{key:>16}: {v}")
    print("\n[데이터 품질]"); [print(" -", n) for n in notes]
    print("\n[공연일 시간대별 지수(같은 달 공연 없는 날=100)]\n", profiles(df).pivot(index="요일유형", columns="시", values="지수").to_string())
    print("\n[날씨: 같은 시간대·요일유형 평균 대비 %]\n", w.to_string(index=False))
    print("\n[월별]\n", m.to_string(index=False))
    print("\n[피크 주차 상위 공연일]\n", s[["날짜", "요일유형", "공연명", "관람객수", "피크주차", "기준피크", "증가율"]]
          .head(8).round({"기준피크": 0, "증가율": 0}).to_string(index=False))
