"""기획서에 들어갈 숫자를 분석 결과 파일에서 직접 모은다 (손으로 옮겨 적지 않기 → 허위 기재 방지).

출력: docs/기획서/facts.json  — 값마다 {"value": ..., "source": "어느 파일의 어느 항목"}
       docs/기획서/숫자_출처.md — 사람이 확인하는 표
사용법: python tools/proposal_facts.py   (그다음 node docs/기획서/build_docx.js)
"""
import csv
import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "web" / "app" / "data"
OUT = ROOT / "docs" / "기획서"
facts = {}


def put(key, value, source):
    facts[key] = {"value": value, "source": source}


def j(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


# 2025 연계 데이터 분석 (m25)
kpi = json.loads((ROOT / "data" / "clean" / "m25_kpi.json").read_text(encoding="utf-8"))
src = "data/clean/m25_kpi.json"
put("m25_기간", kpi["기간"], src + " 기간")
put("m25_시간대수", kpi["시간대수"], src + " 시간대수")
put("m25_일수", kpi["일수"], src + " 일수 (결함일 제외)")
put("m25_공연일수", kpi["공연일수"], src + " 공연일수")
put("주말_저녁최고시", kpi["저녁최고시_주말"], src + " 저녁최고시_주말")
put("주말_저녁최고배", round(kpi["저녁최고지수_주말"] / 100, 1), src + " 저녁최고지수_주말 ÷ 100")
put("평일_저녁최고시", kpi["저녁최고시_평일"], src + " 저녁최고시_평일")
put("평일_저녁최고배", round(kpi["저녁최고지수_평일"] / 100, 1), src + " 저녁최고지수_평일 ÷ 100")
put("피크증가_주말", round(kpi["공연일피크증가율_주말"]), src + " 공연일피크증가율_주말 (%)")
put("피크증가_평일", round(kpi["공연일피크증가율_평일"]), src + " 공연일피크증가율_평일 (%)")
put("관객_피크_상관", kpi["관객_피크_상관"], src + " 관객_피크_상관")
notes = json.loads((ROOT / "data" / "clean" / "m25_notes.json").read_text(encoding="utf-8"))
put("결함일수", int(re.search(r"(\d+)일을 제외", notes[0]).group(1)), "data/clean/m25_notes.json [0]")
m = re.search(r"([\d,]+)대 → ([\d,]+)대", notes[1])
put("8월_급변", f"{m.group(1)}대 → {m.group(2)}대", "data/clean/m25_notes.json [1]")

sp = j("show_profile.json")
put("화면_공연일수", sp["공연일수"], "web/app/data/show_profile.json 공연일수")
put("비_보정률", round((1 - sp["rain_factor"]) * 100), "show_profile.json rain_factor (1 − 값, %)")
put("비_시간수", sp["rain_hours"], "show_profile.json rain_hours")
put("붐빔_기준", sp["levels"]["busy"] / 100, "show_profile.json levels.busy ÷ 100 (배)")
put("매우붐빔_기준", sp["levels"]["very_busy"] / 100, "show_profile.json levels.very_busy ÷ 100 (배)")

ex = j("exit_profile.json")
d = ex["exit_decay"]
put("출차_기간", d["기간"], "exit_profile.json exit_decay.기간")
put("출차_저녁수", d["저녁수"], "exit_profile.json exit_decay.저녁수")
put("출차_최대10분", d["최대출차_10분_중앙값"], "exit_profile.json exit_decay.최대출차_10분_중앙값")
for o, r in zip(d["offsets_min"], d["ratio"]):
    put(f"출차_{o}분", round(r * 100), f"exit_profile.json exit_decay.ratio[{o}분] (%)")
sm = {k: v for k, v in ex["show_minutes"].items() if k != "설명"}
put("공연시간_중앙값", sorted({v["median"] for v in sm.values()}), "exit_profile.json show_minutes.*.median (분)")
put("공연시간_표본", sum(v["n"] for v in sm.values()), "exit_profile.json show_minutes.*.n 합")

nc = j("nowcast_check.json")
put("예보검증", {k: nc[k] for k in ("weekday", "weekend")}, "web/app/data/nowcast_check.json")

pf = j("park_facts.json")
for k in ("capacity", "fee_per_10min", "discount_pct", "car_open", "car_close", "spare_minutes", "walk_minutes"):
    put("FAQ_" + k, pf[k], f"park_facts.json {k} (자주 묻는 질문정보: {pf['sources'].get(k, '')})")
put("FAQ_booths", pf["booths"], "park_facts.json booths")

put("시야_시점수", len(j("seat_views.json")["views"]), "seat_views.json views 개수")
put("3D_공연장수", len(glob.glob(str(ROOT / "web" / "app" / "models" / "*.glb*"))), "web/app/models 파일 수")

# 원자료 규모
f24 = glob.glob(str(ROOT / "data" / "raw" / "15138735_*.csv"))[0]
with open(f24, encoding="cp949") as f:
    put("입출차2024_건수", sum(1 for _ in f) - 1, "data/raw/15138735_*.csv 행 수")
kscperf = 0
for fp in glob.glob(str(ROOT / "data" / "raw" / "kscperf" / "*.json")):
    it = json.loads(Path(fp).read_text(encoding="utf-8"))["response"]["body"]["items"]["item"]
    kscperf += len(it) if isinstance(it, list) else 1
put("공연정보_건수", kscperf, "data/raw/kscperf/*.json item 수")

live = sorted(glob.glob(str(ROOT / "data" / "live" / "*.csv")))
rows = []
for fp in live:
    with open(fp, encoding="utf-8") as f:
        rows += list(csv.DictReader(f))
put("실시간기록_건수", len(rows), "data/live/*.csv 행 수")
put("실시간기록_시작", rows[0]["시각"][:10] if rows else None, "data/live/*.csv 첫 기록")

put("계산테스트_수", len(re.findall(r"^test\(", (ROOT / "tests" / "web" / "logic.test.js").read_text(encoding="utf-8"), re.M)),
    "tests/web/logic.test.js test( 개수")

# 전체구역 분석 (있으면)
zp = DATA / "zone_profile.json"
if zp.exists():
    z = json.loads(zp.read_text(encoding="utf-8"))
    put("전체구역", z, "web/app/data/zone_profile.json")

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
lines = ["# 기획서 숫자 출처", "", "`python tools/proposal_facts.py`가 만든다. 기획서의 숫자는 모두 이 표의 값에서 온다.", "",
         "| 항목 | 값 | 출처 |", "|---|---|---|"]
for k, v in facts.items():
    val = v["value"]
    shown = json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else str(val)
    if len(shown) > 80:
        shown = shown[:77] + "…"
    lines.append(f"| {k} | {shown} | {v['source']} |")
(OUT / "숫자_출처.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(facts)}개 →", OUT / "facts.json")
