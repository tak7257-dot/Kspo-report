"""2단계: 원본 입출차 CSV를 분석하기 좋은 형태로 정리한다.

입력:  data/raw/15138735_*.csv   (올림픽공원 입출차 정보, 1행 = 차량 1대)
출력:  data/clean/visits.csv      (1행 = 차량 1대, 분석용 컬럼 추가)

정리 원칙 (보고서 '데이터 한계'에도 그대로 적는다)
  - 결측/날짜 오류 행은 제거 (현재 데이터에는 0건)
  - 완전히 같은 행(중복)은 '지우지 않는다': 차량 ID가 없어 같은 분에 들고 난
    서로 다른 차인지 구분할 수 없기 때문. 대신 건수를 기록해 둔다.
  - 체류 5분 미만 = '단시간(통과·하차)', 24시간 초과 = '장기주차' 로 표시만 한다.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def load_raw() -> pd.DataFrame:
    path = next(RAW.glob("15138735_*.csv"))
    # 공공데이터 CSV는 대부분 한글 윈도우 인코딩(cp949)
    return pd.read_csv(path, encoding="cp949")


def clean(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["입차시각"] = pd.to_datetime(df["입차일시"], errors="coerce")
    out["출차시각"] = pd.to_datetime(df["출차일시"], errors="coerce")
    out = out.dropna()  # 날짜로 못 바꾼 행 제거

    out["날짜"] = out["입차시각"].dt.date
    out["입차시"] = out["입차시각"].dt.hour            # 0~23
    out["요일"] = out["입차시각"].dt.dayofweek.map(lambda i: WEEKDAY_KO[i])
    out["주말"] = out["입차시각"].dt.dayofweek >= 5
    out["체류분"] = (out["출차시각"] - out["입차시각"]).dt.total_seconds() / 60

    out["체류구분"] = "일반"
    out.loc[out["체류분"] < 5, "체류구분"] = "단시간(5분 미만)"
    out.loc[out["체류분"] > 24 * 60, "체류구분"] = "장기주차(24시간 초과)"
    return out


if __name__ == "__main__":
    raw = load_raw()
    visits = clean(raw)
    CLEAN.mkdir(parents=True, exist_ok=True)
    visits.to_csv(CLEAN / "visits.csv", index=False, encoding="utf-8-sig")

    print(f"원본 {len(raw):,}행 → 정리 후 {len(visits):,}행")
    print(f"완전 중복행(유지함): {raw.duplicated().sum():,}행")
    print(f"기간: {visits['날짜'].min()} ~ {visits['날짜'].max()}")
    print(visits["체류구분"].value_counts().to_string())
    print(visits.head().to_string())
