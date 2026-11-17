"""1단계(홈페이지): 올림픽공원 홈페이지 '공연/행사 일정' 상세 페이지에서 공연장·시작 시각을 모은다.

왜 필요한가
  공연행사정보 API(KSCperf)에는 2024년 공연까지만 있어서, 2025년 공연의 공연장을 알 수 없다.
  기관 공식 홈페이지 일정 페이지에는 공연마다 공연장·기간·회차별 시간·가까운 주차장이 있다.
  (공공데이터포털 '올림픽공원 공연정보' 설명에서 안내하는 페이지)

방법
  상세 페이지 주소의 일련번호(evtSeq)를 최신 번호부터 거꾸로 읽는다.
  종료일이 STOP_BEFORE 이전인 공연이 연달아 STOP_STREAK 개 나오면 멈춘다.
  서버 부담을 줄이려고 요청 사이 3초 쉰다. 공연마다 결과를 저장해서 끊겨도 이어서 받을 수 있다.

사용법:  python src/fetch_events.py 5175        # 5175번부터 거꾸로
출력:    data/raw/events/<evtSeq>.json
"""
import html
import json
import re
import sys
import time
from pathlib import Path

import requests

URL = "https://www.ksponco.or.kr/olympicpark/eventInfo/eventInfoView.es"
RAW = Path(__file__).resolve().parent.parent / "data" / "raw" / "events"
STOP_BEFORE = "2025-01-01"
STOP_STREAK = 40


def text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def field(h: str, name: str) -> str:
    m = re.search(rf"<em>{name}</em>\s*<span[^>]*>(.*?)</span>", h, re.S)
    return text(m.group(1)) if m else ""


def car_info(h: str, name: str) -> str:
    m = re.search(rf"<td>{name}</td>\s*<td[^>]*>(.*?)</td>", h, re.S)
    return text(m.group(1)) if m else ""


def parse(seq: int, h: str):
    m = re.search(r'<strong class="title">(.*?)</strong>', h, re.S)
    if not m:
        return None
    period = field(h, "기간")
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", period)
    # 이 공연의 공연장 = '소개' 탭의 첫 번째 하위 탭 (탭 번호는 공연장마다 다름: conPlace01, 02 ...)
    tab = re.search(r'class="sub_tabs">\s*<li><a href="#(conPlace\d+)" class="tab_nav">([^<]+)</a>', h)
    venue, section = "", ""
    if tab:
        venue = text(tab.group(2))
        # 페이지에는 모든 공연장 안내가 들어 있으므로, 해당 공연장 구역에서만 입구·주차장을 읽는다
        start = h.find(f'id="{tab.group(1)}"')
        nxt = h.find('class="slide_tab_cont"', start + 10)
        section = h[start: nxt if nxt > 0 else start + 20000]
    return {
        "evtSeq": seq, "공연명": text(m.group(1)),
        "시작일": dates[0] if dates else "", "종료일": dates[-1] if dates else "",
        "시간": field(h, "시간"), "소요시간": field(h, "소요시간"),
        "공연장_원문": venue,
        "가까운입구": car_info(section, "가까운 입구"), "가까운주차장": car_info(section, "가까운 주차장"),
    }


if __name__ == "__main__":
    start = int(sys.argv[1])
    RAW.mkdir(parents=True, exist_ok=True)
    streak, n_ok = 0, 0
    for seq in range(start, 0, -1):
        out = RAW / f"{seq}.json"
        if out.exists():
            rec = json.loads(out.read_text(encoding="utf-8"))
        else:
            try:
                r = requests.get(URL, params={"mid": "a20301010100", "evtSeq": seq}, timeout=60)
                rec = parse(seq, r.text) if r.status_code == 200 else None
            except requests.RequestException:
                rec = None
            out.write_text(json.dumps(rec or {"evtSeq": seq, "없음": True}, ensure_ascii=False), encoding="utf-8")
            time.sleep(3)
        if not rec or rec.get("없음"):
            continue
        n_ok += 1
        if rec["종료일"] and rec["종료일"] < STOP_BEFORE:
            streak += 1
            if streak >= STOP_STREAK:
                print(f"{seq}번: 2025년 이전 공연이 {STOP_STREAK}개 연속 → 종료")
                break
        else:
            streak = 0
        if n_ok % 25 == 0:
            print(f"{seq}번까지 {n_ok}건 ({rec['시작일']} {rec['공연명'][:30]})", flush=True)
    print(f"완료: 공연 {n_ok}건 저장")
