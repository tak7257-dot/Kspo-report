"""1단계: 공공데이터포털(data.go.kr) '파일데이터'(CSV)를 자동으로 내려받는다.

사용법:  python src/fetch_filedata.py 15164156 15138735 ...
  - 숫자는 data.go.kr 데이터 주소의 번호  (https://www.data.go.kr/data/<번호>/fileData.do)
  - 인증키가 필요 없는 '파일데이터'만 대상
"""
import re
import sys
from pathlib import Path

import requests

BASE = "https://www.data.go.kr"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def download(public_data_pk: str) -> Path:
    s = requests.Session()
    # 1) 상세 페이지에서 '상세 키(uddi:...)'를 찾는다
    page = s.get(f"{BASE}/data/{public_data_pk}/fileData.do", timeout=60).text
    m = re.search(r"fn_fileDataDown\('(\d+)',\s*'(uddi:[^']+)'", page)
    if not m:
        raise RuntimeError(f"{public_data_pk}: 다운로드 버튼을 찾지 못함")
    detail_pk = m.group(2)

    # 2) 포털이 버튼 클릭 때 부르는 주소로 실제 파일 ID를 받는다
    info = s.get(f"{BASE}/tcs/dss/selectFileDataDownload.do",
                 params={"publicDataPk": public_data_pk, "publicDataDetailPk": detail_pk},
                 timeout=60).json()
    if not info.get("status"):
        raise RuntimeError(f"{public_data_pk}: 다운로드 정보 요청 실패")

    # 3) 파일 받기
    r = s.get(f"{BASE}/cmm/cmm/fileDownload.do",
              params={"atchFileId": info["atchFileId"], "fileDetailSn": info["fileDetailSn"]},
              timeout=120)
    r.raise_for_status()
    name = info["dataSetFileDetailInfo"]["dataNm"]
    ext = info["dataSetFileDetailInfo"].get("atchFileExtsn", "csv") or "csv"
    out = RAW_DIR / f"{public_data_pk}_{name}.{ext.lower()}"
    out.write_bytes(r.content)
    return out


if __name__ == "__main__":
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for pk in sys.argv[1:]:
        try:
            p = download(pk)
            print(f"[OK] {p.name}  ({p.stat().st_size:,} bytes)")
        except Exception as e:
            print(f"[실패] {pk}: {e}")
