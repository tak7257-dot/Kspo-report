"""1단계(API): 문화공공데이터광장 '한국체육산업개발 공연행사정보'(올림픽공원 공연정보)를 받는다.

API: https://api.kcisa.kr/openapi/service/rest/meta/KSCperf   (serviceKey, numOfRows, pageNo)
  - 인증키는 코드에 쓰지 않는다. 실행 전에 환경변수로 넣는다:
        (리눅스/맥)  export KSCPERF_KEY=발급받은키
        (윈도우)     set KSCPERF_KEY=발급받은키
  - 주요 항목: title(공연명), spatial(공연장소), temporalCoverage(시작 시각, 형식 제각각), extent(공연 시간)

사용법:  python src/fetch_kscperf.py
출력:    data/raw/kscperf/kscperf_p0001.json ... (이미 받은 페이지는 건너뜀)
"""
import json
import math
import os
import sys
import time
from pathlib import Path

import requests

URL = "https://api.kcisa.kr/openapi/service/rest/meta/KSCperf"
RAW = Path(__file__).resolve().parent.parent / "data" / "raw" / "kscperf"
ROWS = 100


def get_page(key: str, page: int, tries: int = 4):
    for t in range(tries):
        try:
            r = requests.get(URL, params={"serviceKey": key, "numOfRows": ROWS, "pageNo": page},
                             headers={"accept": "application/json"}, timeout=120)
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                return r.json()
            reason = f"HTTP {r.status_code}"
        except requests.RequestException:
            reason = "응답 없음(시간 초과)"
        wait = 10 * (t + 1)
        print(f"  page {page} 재시도 {t + 1}/{tries} ({reason}) → {wait}초 대기")
        time.sleep(wait)
    return None


if __name__ == "__main__":
    key = os.environ.get("KSCPERF_KEY")
    if not key:
        sys.exit("환경변수 KSCPERF_KEY 가 없습니다. 위 사용법을 보세요.")
    RAW.mkdir(parents=True, exist_ok=True)

    first = get_page(key, 1)
    if first is None:
        sys.exit("첫 페이지를 받지 못했습니다.")
    total = int(first["response"]["body"]["totalCount"])
    pages = math.ceil(total / ROWS)
    print(f"전체 {total:,}건, {pages}페이지")
    (RAW / "kscperf_p0001.json").write_text(json.dumps(first, ensure_ascii=False), encoding="utf-8")

    missing = []
    for page in range(2, pages + 1):
        out = RAW / f"kscperf_p{page:04d}.json"
        if out.exists():
            continue
        time.sleep(3)  # 호출 제한(2초에 1번) 대비
        data = get_page(key, page)
        if data is None:
            missing.append(page)
            print(f"page {page}: 실패 → 건너뜀")
            continue
        out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(f"page {page}: {len(data['response']['body']['items']['item'])}건")
    print("완료. 빠진 페이지:", missing if missing else "없음")
