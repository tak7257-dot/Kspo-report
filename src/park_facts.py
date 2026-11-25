"""웹 안내용 공원 사실: 「자주 묻는 질문정보」(공공데이터포털 15089962, 한국체육산업개발)에서 숫자를 뽑는다.

손으로 적지 않고 FAQ 원문에서 정규식으로 찾아 쓰고, 각 숫자가 어느 질문에서 왔는지(sources)도 함께 남긴다.
FAQ 문구가 바뀌어 찾지 못하면 그 값은 None 이 되고, 웹은 그 줄을 숨긴다.
출력: web/app/data/park_facts.json
"""
import glob
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "app" / "data" / "park_facts.json"


def _find(faq: pd.DataFrame, title_kw: str, pattern: str):
    """제목에 title_kw 가 들어간 질문의 답에서 pattern 을 찾는다 → (match, 질문 제목)"""
    for _, r in faq.iterrows():
        if title_kw in str(r["제목"]):
            m = re.search(pattern, str(r["내용"]))
            if m:
                return m, str(r["제목"]).strip()
    return None, None


def extract(faq: pd.DataFrame) -> dict:
    out, src = {}, {}

    m, t = _find(faq, "주차시설", r"(\d[\d,]*)\s*여?대")
    out["capacity"] = int(m.group(1).replace(",", "")) if m else None
    src["capacity"] = t
    m, t = _find(faq, "주차시설", r"매표소는\s*\d+개소로\s*(.*?)이 있습니다")
    out["booths"] = re.findall(r"[동서남북]\d문", m.group(1)) if m else []
    src["booths"] = t

    m, t = _find(faq, "요금", r"10분당\s*(\d[\d,]*)원")
    out["fee_per_10min"] = int(m.group(1).replace(",", "")) if m else None
    src["fee_per_10min"] = t
    m, t = _find(faq, "요금", r"(\d+)%\s*할인")
    out["discount_pct"] = int(m.group(1)) if m else None
    out["discount_who"] = "경차·장애인·국가유공자·저공해·다자녀(3자녀 이상)" if m else None
    src["discount_pct"] = t

    m, t = _find(faq, "이용시간", r"차량을 이용하여\s*출입하실 경우\s*오전\s*(\d+)시\s*~\s*밤\s*(\d+)시")
    out["car_open"], out["car_close"] = (int(m.group(1)), int(m.group(2)) + 12) if m else (None, None)
    src["car_open"] = t

    m, t = _find(faq, "주차 예상 소요", r"(\d+)\s*시간가량 여유")
    out["spare_minutes"] = int(m.group(1)) * 60 if m else None
    src["spare_minutes"] = t
    m, t = _find(faq, "공연장까지", r"도보로\s*(\d+)\s*분")
    out["walk_minutes"] = int(m.group(1)) if m else None
    src["walk_minutes"] = t

    out["sources"] = src
    return out


if __name__ == "__main__":
    f = glob.glob(str(ROOT / "data" / "raw" / "15089962_*.csv"))[0]
    faq = pd.read_csv(f, encoding="cp949")
    data = {"설명": "「자주 묻는 질문정보」에서 뽑은 주차·이용 사실 (출처 질문 제목 포함)", **extract(faq)}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("park_facts.json 저장:", {k: v for k, v in data.items() if k not in ("설명", "sources")})
