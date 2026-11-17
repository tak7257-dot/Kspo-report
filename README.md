# 올림픽공원 방문 흐름 리포트 (2026 한국체육산업개발 공공데이터 활용 경진대회 출품용)

한국체육산업개발이 공개한 공공데이터로 **수집 → 정리 → 지표 → HTML 보고서**를 자동으로 만드는 파이프라인입니다.

## 실행
```bash
pip install -r requirements.txt
python run_all.py --fetch
```

## 구조
| 단계 | 파일 | 하는 일 |
|---|---|---|
| 1 수집 | `src/fetch_filedata.py` | data.go.kr 파일데이터(CSV) 자동 다운로드 → `data/raw/` |
| 2 정리 | `src/clean.py` | 날짜 변환, 체류시간·요일·주말 컬럼 추가, 이상치 표시 → `data/clean/visits.csv` |
| 3 지표 | `src/metrics.py` | 일별 입차, 요일×시간 히트맵, 시간대별 재차 대수, KPI |
| 4 보고서 | `src/report.py` | Plotly 차트 + 숫자 기반 자동 해설 → `output/report.html` |

## 사용 데이터와 이용 조건 (출처 표시)
모두 공공데이터포털(data.go.kr)에서 제공하는 한국체육산업개발주식회사 개방 데이터이며, 이용허락범위를 확인했다 (2026-11-17).

| 데이터 | 형태 | 이용허락범위 |
|---|---|---|
| 올림픽공원 차량입출차, 공연, 날씨정보 등 연계 데이터 (15164822, 2025) | API (문화공공데이터광장 경유) | 제한 없음 |
| 올림픽공원 입출차 정보 (15138735, 2024-07) | CSV | 제한 없음 |
| 주차장 혼잡도 정보 (15164156) | CSV | 제한 없음 |
| 월별주차현황 (15131671) | CSV | 제한 없음 |
| 올림픽공원 공연장 실감형 콘텐츠 (15127487) | GLB/DAE | 제한 없음 |
| 올림픽공원 공연정보 (3037877, 공연행사정보 API) | API | 공공누리 제1유형(출처표시) |

출처: 한국체육산업개발주식회사, 공공데이터포털(www.data.go.kr)

### 사용하지 않는 자료
- 올림픽공원 홈페이지 자료(공연/행사 일정, 공연장 도면)는 공공누리 표시가 없어 기관 저작권정책상 사전 협의가 필요하다.
  협의 전까지 관련 코드는 `src/_보류/` 에 보관하고 결과물에서 뺐다.

## 외부 프로그램 라이선스
pandas·numpy(BSD), requests(Apache-2.0), plotly(MIT), jinja2(BSD), trimesh(MIT), shapely(BSD), opencv(Apache-2.0),
@google/model-viewer·three.js Draco 해독기(Apache-2.0), glTF-Transform(MIT), assimp(BSD)
