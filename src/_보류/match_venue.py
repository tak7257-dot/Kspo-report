"""2단계(공연장): 2025 시간대별 데이터의 공연에 공연장·시작 시각·가까운 주차장을 붙인다.

입력:  data/raw/events/*.json         (fetch_events.py: 올림픽공원 홈페이지 공연 일정, 2025~)
       data/raw/kscperf/*.json        (fetch_kscperf.py: 공연행사정보 API, ~2024 → 공연장별 시작 시각 경향)
       data/clean/hourly_2025.csv     (clean_kcisa.py 결과)
출력:  data/clean/events.csv          (홈페이지 공연 일정 정리본, 1행 = 공연 x 날짜)
       data/clean/perf_info.csv       (공연행사정보 API 정리본)
       data/clean/show_venue_2025.csv (2025 날짜 x 공연명 → 공연장·시작시·주차장, 매칭 방식)

매칭 원칙
  - 공연명을 소문자로 바꾸고 기호·공백을 지운 뒤 비교: ① 완전히 같으면 '일치' ② 한쪽이 다른 쪽을 포함(8글자 이상)하면 '포함'
  - 같은 이름의 공연이 여러 해에 있으면, 그 날짜가 공연 기간 안에 드는 것을 고른다
  - 공연장 표기는 하나로 통일 (예: KSPO-DOME / 체조경기장 → KSPO DOME, 티켓링크 라이브 아레나 → SK핸드볼경기장)
"""
import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean"

VENUE_RULES = [  # (찾을 글자, 통일 이름) - 위에서부터 먼저 맞는 것 사용
    (r"뮤즈라이브", "뮤즈라이브"),
    (r"kspo[\s\-]*dome|체조", "KSPO DOME"),
    (r"핸드볼|티켓링크", "SK핸드볼경기장"),
    (r"우리금융|역도", "우리금융아트홀"),
    (r"k-?아트홀", "K-아트홀"),
    (r"올림픽홀", "올림픽홀"),
    (r"88\s*잔디", "88잔디마당"),
    (r"수변", "수변무대"),
    (r"기타시설|옥외", "야외·기타시설"),   # 홈페이지에 '기타시설'로만 적힌 야외 페스티벌 등
]
WEEKDAYS = "월화수목금토일"
TIME_RE = re.compile(
    r"(\d{1,2})\s*(?::\s*(\d{2}))?\s*(PM|pm|AM|am)"                     # 6PM / 7:30PM  (HH:MM 보다 먼저 검사)
    r"|(오전|오후|저녁|밤|낮|아침|새벽)\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?"  # 오후 7시 / 저녁 8시
    r"|(\d{1,2})\s*:\s*(\d{2})"                                          # 18:00
    r"|(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?"                              # 19시 / 19시 30분
)
PM_WORDS = {"오후", "저녁", "밤", "낮"}


def norm(s) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", str(s).lower())


def std_venue(s) -> str:
    s = str(s).lower()
    for pat, name in VENUE_RULES:
        if re.search(pat, s):
            return name
    return "기타/미상"


def to_hour(m) -> int | None:
    if m.group(1):   # N PM / N:MM PM
        h = int(m.group(1))
        return h + 12 if m.group(3).lower() == "pm" and h < 12 else h
    if m.group(4):   # 오후/저녁/밤 N시
        h = int(m.group(5))
        return h + 12 if m.group(4) in PM_WORDS and h < 12 else h
    if m.group(7):   # HH:MM
        return int(m.group(7))
    if m.group(9):   # N시
        return int(m.group(9))
    return None


def schedule(text: str, start: str, end: str) -> dict:
    """공연 기간의 날짜별 시작 시각(시)을 추정한다. 반환: {date: hour}
    ① '11월 27일 ... 오후 7시' 처럼 날짜 뒤에 시각이 오면 그 날짜에
    ② '토 오후 6시 / 일 오후 5시' 처럼 요일 뒤에 시각이 오면 그 요일의 날짜에
    ③ 시각이 하나뿐이면 모든 날짜에 (회차가 여러 번이면 첫 회차)"""
    try:
        d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        return {}
    days = [d0 + timedelta(i) for i in range((d1 - d0).days + 1)]
    times = [(m.start(), to_hour(m)) for m in TIME_RE.finditer(text)]
    times = [(i, h) for i, h in times if h is not None and 0 <= h < 24]
    if not times:
        return {}
    out = {}
    # ① 날짜 + 시각
    for dm in re.finditer(r"(?<!\d)(\d{1,2})\s*[월.]\s*(\d{1,2})(?!\d)\s*일?", text):  # 2026.11.21 의 '26' 은 월로 읽지 않음
        nxt = [h for i, h in times if i >= dm.end() and i - dm.end() < 30]
        if nxt:
            for d in days:
                if d.month == int(dm.group(1)) and d.day == int(dm.group(2)):
                    out.setdefault(d, nxt[0])
    # ② 요일 + 시각
    for wm in re.finditer(rf"[({{\s/]?([{WEEKDAYS}])[)\s]", text):
        nxt = [h for i, h in times if i >= wm.end() and i - wm.end() < 15]
        if nxt:
            for d in days:
                if WEEKDAYS[d.weekday()] == wm.group(1):
                    out.setdefault(d, nxt[0])
    # ③ 남은 날짜는 가장 많이 나온 시각
    common = Counter(h for _, h in times).most_common(1)[0][0]
    for d in days:
        out.setdefault(d, common)
    return out


def load_events() -> pd.DataFrame:
    rows = []
    for f in (ROOT / "data" / "raw" / "events").glob("*.json"):
        e = json.loads(f.read_text(encoding="utf-8"))
        if not e or e.get("없음") or not e.get("시작일"):
            continue
        sch = schedule(e["시간"], e["시작일"], e["종료일"])
        for d in pd.date_range(e["시작일"], e["종료일"]):
            rows.append({
                "evtSeq": e["evtSeq"], "공연명": e["공연명"], "날짜": d.date(),
                "공연장": std_venue(e["공연장_원문"]), "시작시": sch.get(d.date()),
                "가까운입구": e["가까운입구"], "가까운주차장": e["가까운주차장"], "시간_원문": e["시간"],
            })
    ev = pd.DataFrame(rows)
    ev["키"] = ev["공연명"].map(norm)
    return ev


def load_perf() -> pd.DataFrame:
    rows = []
    for f in sorted((ROOT / "data" / "raw" / "kscperf").glob("kscperf_p*.json")):
        rows += json.loads(f.read_text(encoding="utf-8"))["response"]["body"]["items"]["item"]
    pf = pd.DataFrame(rows)
    hour = pf["temporalCoverage"].map(lambda s: next((to_hour(m) for m in TIME_RE.finditer(str(s))), None))
    return pd.DataFrame({"공연명": pf["title"].str.strip(), "공연장": pf["spatial"].map(std_venue),
                         "공연장_원문": pf["spatial"], "시작시": hour, "시작_원문": pf["temporalCoverage"]})


def split_names(s: str) -> list[str]:
    # 같은 시간에 공연이 여러 개면 ", " 로 이어져 있다. 공연명 안의 쉼표와 구분하려고 뒤에 오는 글자를 본다.
    return [x.strip() for x in re.split(r",\s(?=[0-9A-Za-z가-힣\[［〈<(（『「])", s) if x.strip()]


def match(name: str, day: date, ev: pd.DataFrame):
    k = norm(name)
    on_day = ev[ev["날짜"] == day]
    for how, cond in [("일치", on_day["키"] == k),
                      ("포함", on_day["키"].map(lambda x: len(k) >= 8 and len(x) >= 8 and (x in k or k in x)))]:
        c = on_day[cond]
        if not c.empty:
            return c.iloc[0], how
    return None, "미매칭"


if __name__ == "__main__":
    perf = load_perf()
    perf.to_csv(CLEAN / "perf_info.csv", index=False, encoding="utf-8-sig")
    ev = load_events()
    ev.drop(columns="키").to_csv(CLEAN / "events.csv", index=False, encoding="utf-8-sig")

    h = pd.read_csv(CLEAN / "hourly_2025.csv", parse_dates=["시각"])
    pairs = sorted({(t.date(), n) for t, s in zip(h["시각"], h["공연명"]) if isinstance(s, str) and s
                    for n in split_names(s)})
    res = []
    for day, name in pairs:
        row, how = match(name, day, ev)
        res.append({"날짜": day, "공연명": name, "매칭": how,
                    **({k: row[k] for k in ["공연장", "시작시", "가까운입구", "가까운주차장"]} if row is not None else {})})
    sv = pd.DataFrame(res)
    sv.to_csv(CLEAN / "show_venue_2025.csv", index=False, encoding="utf-8-sig")

    print(f"홈페이지 공연 일정: 공연 {ev['evtSeq'].nunique()}개, 공연일 {len(ev)}일 "
          f"(시작 시각 추출 {ev['시작시'].notna().mean() * 100:.0f}%)")
    print(f"2025 (날짜, 공연) {len(sv)}쌍 매칭:", sv["매칭"].value_counts().to_dict())
    if "공연장" in sv:
        print("공연장:", sv["공연장"].value_counts().to_dict())
        print("시작시:", sv["시작시"].value_counts().sort_index().to_dict())
    miss = sv.loc[sv["매칭"] == "미매칭", "공연명"].unique()
    print(f"\n[미매칭 공연 {len(miss)}개]\n" + "\n".join(miss[:40]))
