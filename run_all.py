"""전체 파이프라인을 한 번에 실행: 수집 → 정리 → 지표 → 보고서

    python run_all.py            # 이미 받은 원본으로 다시 만들기
    python run_all.py --fetch    # 원본부터 새로 받기
                                 #  (2025 연계 데이터 API는 환경변수 KCISA_KEY, 공연행사정보 API는 KSCPERF_KEY 가 있을 때만)
                                 #  ※ 홈페이지 자료를 쓰는 단계(공연장 매칭 등)는 사전 협의 전까지 src/_보류/ 에 보관
"""
import os
import subprocess
import sys
from pathlib import Path

FILE_DATA = ["15138735", "15164156", "15131671"]  # 입출차(2024-07), 주차장 혼잡도, 월별주차현황
KCISA_PAGES = ["1", "17"]                         # 500건 x 17페이지 ≒ 시간대별 요약 전체(7,803건)

steps = []
if "--fetch" in sys.argv:
    steps.append(["src/fetch_filedata.py", *FILE_DATA])
    if os.environ.get("KCISA_KEY"):
        steps.append(["src/fetch_kcisa.py", *KCISA_PAGES])
    else:
        print("KCISA_KEY 가 없어 2025 연계 데이터 수집은 건너뜁니다.")
    if os.environ.get("KSCPERF_KEY"):
        steps.append(["src/fetch_kscperf.py"])
steps += [["src/clean.py"], ["src/metrics.py"]]
if any(Path("data/raw/kcisa").glob("kcisa_p*.xml")):
    steps += [["src/clean_kcisa.py"], ["src/metrics_2025.py"], ["src/export_web_data.py"], ["src/seat_views.py"]]
steps.append(["src/report.py"])

for step in steps:
    print(f"\n===== {step[0]} =====")
    subprocess.run([sys.executable, *step], check=True)
print("\n완료: output/report.html 을 브라우저로 여세요.")
