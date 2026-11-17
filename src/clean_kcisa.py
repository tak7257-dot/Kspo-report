"""2단계(API): 받아 둔 XML 페이지에서 '시간대별 요약' 기록만 골라 표로 정리한다.

입력:  data/raw/kcisa/kcisa_p*.xml
출력:  data/clean/hourly_2025.csv   (1행 = 날짜 x 시간대)

원본 DESCRIPTION 예:
  주차대수:2284,방문객:6852, 기온:32.8, 풍향:2.9, 강수량:, 습도:56,휴일:,공연명:,공연관람객수:0

정리 원칙
  - '입출차정보(추가정보)' 제목만 사용 (차량 1대 단위 기록은 이번 분석에서 제외)
  - 공연명 안에 쉼표가 있을 수 있어서, 항목 이름 순서를 기준으로 잘라낸다
  - '방문객' 은 주차대수 x 3(평일) / x 5(주말·휴일 추정) 로 계산된 값이라 독립 지표로 쓰지 않는다 (검증 결과를 출력)
  - 강수량 빈칸 = 0mm 로 본다 (기상청 관측자료에서 무강수는 빈칸으로 오는 경우가 많음)
  - 같은 날짜·시각이 여러 번 나오면 하나만 남긴다
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "kcisa"
CLEAN = ROOT / "data" / "clean"

PATTERN = re.compile(
    r"주차대수:(?P<주차대수>[^,]*),\s*방문객:(?P<방문객>[^,]*),\s*기온:(?P<기온>[^,]*),\s*"
    r"풍향:(?P<풍향>[^,]*),\s*강수량:(?P<강수량>[^,]*),\s*습도:(?P<습도>[^,]*),\s*"
    r"휴일:(?P<휴일>[^,]*),\s*공연명:(?P<공연명>.*),\s*공연관람객수:(?P<공연관람객수>[^,]*)$",
    re.S,
)


def parse_pages() -> tuple[pd.DataFrame, int]:
    rows, bad = [], 0
    for f in sorted(RAW.glob("kcisa_p*.xml")):
        for item in ET.parse(f).getroot().iter("item"):
            if "(추가정보)" not in (item.findtext("TITLE") or ""):
                continue
            m = PATTERN.search((item.findtext("DESCRIPTION") or "").strip())
            if not m:
                bad += 1
                continue
            row = m.groupdict()
            row["시각"] = item.findtext("ISSUED_DATE")
            rows.append(row)
    return pd.DataFrame(rows), bad


def tidy(df: pd.DataFrame) -> pd.DataFrame:
    df["시각"] = pd.to_datetime(df["시각"], errors="coerce")
    for c in ["주차대수", "방문객", "기온", "풍향", "습도", "공연관람객수"]:
        df[c] = pd.to_numeric(df[c].str.strip(), errors="coerce")
    df["강수량"] = pd.to_numeric(df["강수량"].str.strip().replace("", "0"), errors="coerce")
    for c in ["휴일", "공연명"]:
        df[c] = df[c].str.strip()
    df = df.dropna(subset=["시각"]).drop_duplicates(subset=["시각"]).sort_values("시각")
    df["날짜"] = df["시각"].dt.date
    df["시"] = df["시각"].dt.hour
    df["요일번호"] = df["시각"].dt.dayofweek
    df["공연있음"] = df["공연명"] != ""
    df["휴일여부"] = df["휴일"] != ""
    return df.reset_index(drop=True)


if __name__ == "__main__":
    raw, bad = parse_pages()
    df = tidy(raw)
    CLEAN.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN / "hourly_2025.csv", index=False, encoding="utf-8-sig")

    print(f"시간대별 요약 {len(raw):,}건 읽음, 형식 오류 {bad}건 → 정리 후 {len(df):,}건")
    print(f"기간: {df['시각'].min()} ~ {df['시각'].max()}, 날짜 수 {df['날짜'].nunique()}")
    ratio = (df["방문객"] / df["주차대수"]).round(2)
    weekend = df["요일번호"] >= 5
    print("방문객/주차대수 배율 분포:", ratio.value_counts().head(4).to_dict())
    print("  평일 배율:", ratio[~weekend].value_counts().head(3).to_dict(), "/ 주말 배율:", ratio[weekend].value_counts().head(3).to_dict())
    print("결측:", df[["주차대수", "기온", "습도", "공연관람객수"]].isna().sum().to_dict())
    print("시간대 분포(시):", sorted(df["시"].unique()))
    print(f"공연 있는 시간대 {df['공연있음'].sum():,}건, 공연 종류 {df.loc[df['공연있음'], '공연명'].nunique()}개")
    print("휴일 값 예:", df.loc[df["휴일여부"], "휴일"].value_counts().head(5).to_dict())
    print(df.loc[df["공연있음"], ["시각", "주차대수", "공연명", "공연관람객수"]].head(5).to_string())
