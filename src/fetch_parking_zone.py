"""1단계(API): 문화공공데이터광장 '올림픽공원 입출차정보(전체구역)'(API_CPM_008, 2025년, 약 241만 건)를 받는다.

API: https://api.kcisa.kr/openapi/API_CPM_008/request   (serviceKey, numOfRows ≤ 10000, pageNo)
  - 호출 제한: 5초에 1번. 한 페이지 최대 1만 건 → 약 242페이지, 1시간쯤 걸린다.
  - 인증키는 코드에 쓰지 않는다. 실행 전에 환경변수로 넣는다:  export KCISA_ZONE_KEY=발급받은키
  - 응답 항목: DESCRIPTION "입구:동2문입구#1, 입차시간:2025-08-24 13:48:38, 출구:동2문출구#1, 출차시간:..."
    차량번호 같은 개인정보는 없다. 저장할 때도 문·시각 다섯 칸만 남긴다.

사용법:  python src/fetch_parking_zone.py
출력:    data/raw/zone/zone_p0001.csv.gz ... (용량이 커서 git에 올리지 않는다. 이미 받은 페이지는 건너뜀)
"""
import csv
import gzip
import io
import math
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

URL = "https://api.kcisa.kr/openapi/API_CPM_008/request"
RAW = Path(__file__).resolve().parent.parent / "data" / "raw" / "zone"
ROWS = 10000
GAP = 12  # 초. "5초에 1번" 제한이 실제로는 더 엄격해 7초 간격도 막혔다
FIELDS = ["in_gate", "in_time", "out_gate", "out_time"]
DESC = re.compile(r"입구:(?P<in_gate>[^,]*),\s*입차시간:(?P<in_time>[^,]*),\s*"
                  r"출구:(?P<out_gate>[^,]*),\s*출차시간:(?P<out_time>.*)$")


def parse_items(xml_text: str):
    """응답 XML → (전체 건수, [{in_gate, in_time, out_gate, out_time}, ...])."""
    root = ET.fromstring(xml_text)
    total = int(root.findtext(".//totalCount") or 0)
    rows = []
    for it in root.iter("item"):
        m = DESC.match((it.findtext("DESCRIPTION") or "").strip())
        if m:
            rows.append({k: m.group(k).strip() for k in FIELDS})
    return total, rows


def get_page(key: str, page: int, tries: int = 6):
    for t in range(tries):
        try:
            r = requests.get(URL, params={"serviceKey": key, "numOfRows": ROWS, "pageNo": page}, timeout=180)
            if r.status_code == 200 and r.text.lstrip().startswith("<response"):
                return parse_items(r.text)
            reason = f"HTTP {r.status_code}"
        except (requests.RequestException, ET.ParseError) as e:
            reason = type(e).__name__
        wait = 15 * (t + 1)
        print(f"  page {page} 재시도 {t + 1}/{tries} ({reason}) → {wait}초 대기", flush=True)
        time.sleep(wait)
    return None


def save(page: int, rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)
    tmp = RAW / f"zone_p{page:04d}.csv.gz.part"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        f.write(buf.getvalue())
    tmp.rename(RAW / f"zone_p{page:04d}.csv.gz")


if __name__ == "__main__":
    key = os.environ.get("KCISA_ZONE_KEY")
    if not key:
        sys.exit("환경변수 KCISA_ZONE_KEY 가 없습니다. 위 사용법을 보세요.")
    RAW.mkdir(parents=True, exist_ok=True)

    first = get_page(key, 1)
    if first is None:
        sys.exit("첫 페이지를 받지 못했습니다.")
    total, rows = first
    pages = math.ceil(total / ROWS)
    print(f"전체 {total:,}건, {pages}페이지", flush=True)
    if not (RAW / "zone_p0001.csv.gz").exists():
        save(1, rows)

    missing = []
    for page in range(2, pages + 1):
        if (RAW / f"zone_p{page:04d}.csv.gz").exists():
            continue
        time.sleep(GAP)
        got = get_page(key, page)
        if got is None:
            missing.append(page)
            print(f"page {page}: 실패 → 건너뜀 (다시 실행하면 이어 받음)", flush=True)
            continue
        save(page, got[1])
        print(f"page {page}/{pages}: {len(got[1])}건", flush=True)
    print("완료. 빠진 페이지:", missing if missing else "없음", flush=True)
