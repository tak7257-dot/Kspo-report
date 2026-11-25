#!/bin/sh
# 실시간 주차현황 API 값을 쌓아 둔다 → data/live/YYYY-MM.csv  (시각(KST), 주차대수)
# GitHub Actions가 매시간 실행하고, 한 번 실행에 10분 간격으로 SAMPLES번(기본 6번) 기록한다.
# 「올림픽공원 실시간 주차현황」(공공데이터포털 15168686, 이용허락범위 제한 없음, 인증키는 기관 공개값)
set -u
URL='https://www.ksponco.or.kr/online/main/parkingorsApi.do?apiKey=PARKING21803504'
SAMPLES=${SAMPLES:-6}
GAP=${GAP:-600}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
i=1
while [ "$i" -le "$SAMPLES" ]; do
  body=$(curl -s -m 20 "$URL" || true)
  n=$(printf '%s' "$body" | sed -n 's/.*"parking_sum":\([0-9][0-9]*\).*/\1/p')
  ts=$(TZ=Asia/Seoul date '+%Y-%m-%dT%H:%M')
  f="$ROOT/data/live/$(TZ=Asia/Seoul date '+%Y-%m').csv"
  [ -f "$f" ] || echo "시각,주차대수" > "$f"
  if [ -n "$n" ]; then echo "$ts,$n" >> "$f"; echo "기록 $ts $n"; else echo "건너뜀 $ts (응답: $(printf '%s' "$body" | head -c 40))"; fi
  [ "$i" -lt "$SAMPLES" ] && sleep "$GAP"
  i=$((i + 1))
done
