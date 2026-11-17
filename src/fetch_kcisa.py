"""1단계(API): 문화공공데이터광장 '올림픽공원 2025 차량입출차, 공연, 날씨정보 등 연계 데이터'를 받는다.

API: https://api.kcisa.kr/openapi/API_CPM_009/request   (serviceKey, numOfRows, pageNo)
  - 인증키는 코드에 쓰지 않는다. 실행 전에 환경변수로 넣는다:
        (리눅스/맥)  export KCISA_KEY=발급받은키
        (윈도우)     set KCISA_KEY=발급받은키
  - 호출 제한: 2초에 1번  →  매 요청 사이 3초 쉰다.
  - 한 API 안에 두 종류 기록이 섞여 있다
        '입출차정보(추가정보)' : 시간대별 요약(주차대수·날씨·공연)  ← 이번 분석의 핵심
        '입출차정보'          : 차량 1대 단위 기록(약 240만 건)

사용법:  python src/fetch_kcisa.py 1 16      # 1~16페이지(페이지당 500건, 약 8,000건) 받기
출력:    data/raw/kcisa/kcisa_p0001.xml ... (페이지별 원본 저장, 이미 받은 페이지는 건너뜀)
"""
import os
import sys
import time
from pathlib import Path

import requests

URL = "https://api.kcisa.kr/openapi/API_CPM_009/request"
RAW = Path(__file__).resolve().parent.parent / "data" / "raw" / "kcisa"
ROWS = 500   # 1000건씩 요청하면 서버 시간초과(504)가 잦아서 500건으로


def get_page(key: str, page: int, tries: int = 4) -> str | None:
    """성공하면 XML 텍스트, 끝내 실패하면 None (전체 실행은 멈추지 않는다)."""
    for t in range(tries):
        try:
            r = requests.get(URL, params={"serviceKey": key, "numOfRows": ROWS, "pageNo": page}, timeout=120)
            if r.status_code == 200 and r.text.startswith("<response>"):
                return r.text
            reason = f"HTTP {r.status_code}"
        except requests.RequestException:
            reason = "응답 없음(시간 초과)"
        wait = 10 * (t + 1)
        print(f"  page {page} 재시도 {t + 1}/{tries} ({reason}) → {wait}초 대기")
        time.sleep(wait)
    return None


if __name__ == "__main__":
    key = os.environ.get("KCISA_KEY")
    if not key:
        sys.exit("환경변수 KCISA_KEY 가 없습니다. 위 사용법을 보세요.")
    start, end = int(sys.argv[1]), int(sys.argv[2])
    RAW.mkdir(parents=True, exist_ok=True)
    missing = []
    for page in range(start, end + 1):
        out = RAW / f"kcisa_p{page:04d}.xml"
        if out.exists():
            continue
        text = get_page(key, page)
        if text is None:
            print(f"page {page}: 실패 → 건너뜀 (나중에 같은 명령으로 다시 실행하면 채워짐)")
            missing.append(page)
        else:
            out.write_text(text, encoding="utf-8")
            n_sum = text.count("(추가정보)</TITLE>")
            print(f"page {page}: {text.count('<item>')}건 (그중 시간대별 요약 {n_sum}건)")
        time.sleep(3)
    print("완료. 빠진 페이지:", missing if missing else "없음")
