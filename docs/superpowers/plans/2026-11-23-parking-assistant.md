# 덜붐빌때 주차 비서 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 관람객 웹을 "차를 가져가도 될까?"부터 답하는 공연 날 주차 비서로 개편한다 (답 카드, 나가기 모드, 실시간 줄, 하루 미리 보기, 일정표·캘린더).

**Architecture:** 판단 로직은 DOM 없는 순수 함수 파일 `web/app/js/logic.js` 하나에 모아 Node 내장 테스트로 검증하고, 화면(`web/app/index.html`)은 그 함수만 불러 그린다. 새 숫자(실시간 비교 기준)는 파이프라인 단계 `src/live_baseline.py`가 JSON으로 내보낸다. 실시간 주차 API는 브라우저가 직접 부르고, 실패하면 그 줄만 숨긴다.

**Tech Stack:** 정적 HTML/CSS/JS (빌드 없음), `@google/model-viewer@4.0.0`, Node 22 `node:test`, Python 3 + pandas + `unittest`, Playwright(설치되어 있음, `require('playwright')`), GitHub Pages(Actions 배포, `.github/workflows/pages.yml` 이미 있음).

**Spec:** `docs/superpowers/specs/2026-11-23-parking-assistant-design.md` (10절·11절의 결정이 우선)

## Global Constraints

- 공공데이터만 사용. 홈페이지 자료(공연 일정·도면·좌석배치도)는 쓰지 않고, 공연 일정은 링크(`https://www.ksponco.or.kr/olympicpark/eventInfo/eventInfoList?mid=a20301010100`)로만.
- 화면의 모든 숫자는 데이터 JSON에서 읽고, 근처에 출처를 짧게 밝힌다. 하드코딩한 통계 숫자 금지.
- 혼잡 단계: 지수 < 130 보통, 130 이상 붐빔, 200 이상 매우 붐빔 (`show_profile.json`의 `levels`).
- 권장 도착: 시작 1시간 전부터 거꾸로, 지수 < 200인 가장 늦은 시각(10시까지만 봄). **시작 − 권장 도착 > 2시간이면 첫 답은 지하철**, 둘째 줄 "그래도 차로 온다면 HH:00 전". 권장 도착이 없으면 지하철만.
- 비 오는 날: 지수 × `rain_factor`(0.907).
- 공연 시간 = `exit_profile.json`의 `show_minutes[venue].median` (현재 모두 120).
- 출차 비율은 `exit_decay.ratio`(0,10,20,…분: 1.0, 0.68, 0.42, …)에서 읽고, **예상 종료가 20:00 이후인 공연에만** 보여 준다. 절대 대수(113대)는 화면에 쓰지 않는다.
- 실시간 API: `https://www.ksponco.or.kr/online/main/parkingorsApi.do?apiKey=PARKING21803504` → `[{"parking_sum":N}]`. 보여 주기만 하고 권장 답을 바꾸지 않는다. "빠르다/느리다" 판정 문장 금지.
- 주차 데이터는 공원 전체 기준: 화면에 "올림픽공원 주차장은 공연장들이 함께 써요. 공연 날 공원 전체 기준이에요."
- 디자인 유지: IBM Plex Sans KR, 강조색 #A9E4C3 한 가지(글자 #14332A), 선 #2F7A5D, 종이 #F5F9F6, 어두운 화면 대응, 휴대폰 우선, 터치 영역 44px 이상, `word-break: keep-all`, 오른쪽 위 `?` 사용법.
- 아티팩트 규칙: 해시 라우팅은 `#home`, `#exit`, `#day`, `#seat`, `#plan` 같은 평범한 이름만. 외부 스크립트는 jsdelivr 고정 버전만. 3D 파일은 `.glb.wasm`.
- 코드 주석은 한국어, 초보자가 읽을 수 있게.

## Review Focus

1. **실시간 API가 실패·차단될 때** (아티팩트 미리보기는 CSP로 막힘, 기관 점검 시 `9999`, 시간 초과): 실시간 줄만 사라지고 나머지 화면과 콘솔은 멀쩡해야 한다. → Task 2 테스트 `parseLive`, Task 6 스모크.
2. **경계값**: 주말 17:00 시작은 권장 15:00(2시간 차)로 차 괜찮음, 18:00은 3시간 차로 지하철. 이른 시작(11:00)이나 비 체크로 답이 바뀌는 경우. → Task 1 테스트.
3. **자정 넘는 종료** (22:00 시작 → 24:00 종료): 시각은 "00:00 (다음 날)"로 보이고 나가기 모드 판정이 날짜를 넘어도 맞아야 한다. → Task 2 테스트.
4. **localStorage 불가**(사파리 개인 모드, 미리보기): 기본값(KSPO DOME, 다음 토요일, 18:00)으로 정상 표시. → Task 5 스모크(스토리지 차단 컨텍스트).
5. **2025년 8~9월·자료 없는 달의 실시간 비교**: 비교 문구 없이 "지금 N대"만. → Task 3 테스트.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `web/app/js/logic.js` (새로) | 순수 판단 함수 전부. 브라우저에서는 `window.Logic`, Node에서는 `module.exports` |
| `web/app/js/live.js` (새로) | 실시간 API 호출·표본 보관(브라우저 전용, 얇게) |
| `web/app/index.html` (다시 씀) | 화면 5개와 이벤트 연결. 로직은 `Logic.*`만 호출 |
| `src/live_baseline.py` (새로) | 2025 공연 날 월×요일유형×시각 주차대수 중앙값 → `web/app/data/live_baseline.json` |
| `tests/web/logic.test.js` (새로) | `node --test` 단위 테스트 |
| `tests/test_live_baseline.py` (새로) | `python -m unittest` |
| `tests/web/smoke.js` (새로) | Playwright 스모크 (데스크톱 1280×860, iPhone 13, 다크, 스토리지 차단) |
| `run_all.py` | `src/live_baseline.py` 단계 추가 |

---

### Task 1: 도착 판단 로직

**Files:**
- Create: `web/app/js/logic.js`
- Test: `tests/web/logic.test.js`

**Interfaces:**
- Produces:
  - `HOLIDAYS: string[]` — `'YYYY-MM-DD'` 공휴일(2026–2027, 대체공휴일 포함)
  - `dayType(dateISO: string) -> 'weekday'|'weekend'` — 토·일·`HOLIDAYS`면 weekend
  - `levelOf(index: number) -> 'normal'|'busy'|'very'`
  - `arrivalAdvice({profile: number[24], startHour: number, rain: boolean, rainFactor: number}) -> {mode: 'car'|'subway', arriveHour: number|null, leadHours: number|null, firstVeryBusyHour: number|null, indexAtArrive: number|null}`

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/web/logic.test.js`, `const L = require('../../web/app/js/logic.js')`, 프로필은 `web/app/data/show_profile.json`에서 읽음)

```js
test('주말 18시 → 지하철, 차라면 15시', () => {
  const r = L.arrivalAdvice({ profile: P.weekend, startHour: 18, rain: false, rainFactor: 0.907 });
  assert.deepEqual([r.mode, r.arriveHour, r.leadHours, r.firstVeryBusyHour], ['subway', 15, 3, 16]);
});
test('주말 17시 → 2시간 차라 차 괜찮음', () => {
  const r = L.arrivalAdvice({ profile: P.weekend, startHour: 17, rain: false, rainFactor: 0.907 });
  assert.deepEqual([r.mode, r.arriveHour], ['car', 15]);
});
test('주말 16시 → 차, 15시', () => assert.equal(L.arrivalAdvice({ profile: P.weekend, startHour: 16, rain: false, rainFactor: 0.907 }).mode, 'car'));
test('평일 20시 → 차, 19시', () => {
  const r = L.arrivalAdvice({ profile: P.weekday, startHour: 20, rain: false, rainFactor: 0.907 });
  assert.deepEqual([r.mode, r.arriveHour, r.firstVeryBusyHour], ['car', 19, null]);
});
test('비 오면 지수가 줄어 답이 바뀔 수 있음: 주말 18시 비 → 16시(204×0.907<200)', () => {
  assert.equal(L.arrivalAdvice({ profile: P.weekend, startHour: 18, rain: true, rainFactor: 0.907 }).arriveHour, 16);
});
test('도착 가능 시각이 없으면 arriveHour null, 지하철', () => {
  const all = Array(24).fill(250);
  assert.deepEqual(L.arrivalAdvice({ profile: all, startHour: 18, rain: false, rainFactor: 0.907 }).mode, 'subway');
});
test('dayType: 2026-11-28 토 weekend, 11-30 월 weekday, 2026-12-25 weekend', () => {
  assert.equal(L.dayType('2026-11-28'), 'weekend'); assert.equal(L.dayType('2026-11-30'), 'weekday'); assert.equal(L.dayType('2026-12-25'), 'weekend');
});
test('levelOf 경계', () => { assert.equal(L.levelOf(129), 'normal'); assert.equal(L.levelOf(130), 'busy'); assert.equal(L.levelOf(200), 'very'); });
```

- [ ] **Step 2: 실패 확인** — Run: `node --test tests/web/` · Expected: FAIL `Cannot find module`
- [ ] **Step 3: `logic.js` 구현** — UMD 한 줄 패턴(`(function(root, f){ typeof module==='object' ? module.exports=f() : root.Logic=f(); })(this, function(){ ... })`). `HOLIDAYS`는 2026: 01-01, 02-16, 02-17, 02-18, 03-01, 03-02, 05-05, 05-24, 05-25, 06-03, 06-06, 08-15, 08-17, 09-24, 09-25, 09-26, 10-03, 10-05, 10-09, 12-25 / 2027: 01-01, 02-06, 02-07, 02-08, 02-09, 03-01, 05-05, 05-13, 06-06, 08-15, 08-16, 09-14, 09-15, 09-16, 10-03, 10-04, 10-09, 10-11, 12-25, 12-27. 상수 위에 "행정안전부 공휴일 기준, 바뀌면 이 목록만 고치세요" 주석. 날짜 요일은 `new Date(dateISO + 'T00:00:00')` 로컬 기준.
- [ ] **Step 4: 통과 확인** — Run: `node --test tests/web/` · Expected: 8 pass
- [ ] **Step 5: Commit** — `git add web/app/js/logic.js tests/web/logic.test.js && git commit -m "웹: 도착 판단 로직(차/지하철 2시간 기준)과 테스트"`

### Task 2: 나가기 판단 로직과 실시간 값 해석

**Files:**
- Modify: `web/app/js/logic.js`
- Test: `tests/web/logic.test.js`

**Interfaces:**
- Consumes: Task 1의 UMD 틀
- Produces:
  - `exitPlan({startHour: number, startMinute: number, showMinutes: number, decay: {offsets_min: number[], ratio: number[]}}) -> {endHour: number, endMinute: number, nextDay: boolean, endLabel: string, showRatios: boolean, wait: {minutes: number, ratio: number}}` — `wait`은 20분 고정(`offsets_min`에서 20의 비율), `showRatios`는 종료가 20:00 이후(다음 날 포함)일 때 true, `endLabel` 예: `"20:00"`, `"00:00 (다음 날)"`
  - `exitModeActive({now: Date, showDateISO: string, startHour: number, startMinute: number, showMinutes: number}) -> boolean` — 종료 15분 전부터 종료 90분 뒤까지 true
  - `parseLive(text: string) -> number|null` — `[{"parking_sum":N}]`이면 N, 그 밖(빈 응답, `9999`, JSON 오류, 음수)은 null
  - `outflow10(samples: {t: number /*ms*/, n: number}[]) -> number|null` — 가장 최근 표본과 그보다 8~12분 앞선 표본의 차이(줄어든 대수, 0 미만이면 0). 맞는 표본이 없으면 null

- [ ] **Step 1: 실패하는 테스트 작성**

```js
const D = { offsets_min: [0,10,20,30,40,50,60], ratio: [1,0.68,0.42,0.41,0.44,0.57,0.54] };
test('18시+120분 → 20:00, 비율 표시, 20분 뒤 0.42', () => {
  const e = L.exitPlan({ startHour: 18, startMinute: 0, showMinutes: 120, decay: D });
  assert.deepEqual([e.endLabel, e.showRatios, e.wait.minutes, e.wait.ratio], ['20:00', true, 20, 0.42]);
});
test('14시 공연 → 16:00, 비율 숨김', () => assert.equal(L.exitPlan({ startHour: 14, startMinute: 0, showMinutes: 120, decay: D }).showRatios, false));
test('22시 공연 → 00:00 (다음 날)', () => {
  const e = L.exitPlan({ startHour: 22, startMinute: 0, showMinutes: 120, decay: D });
  assert.deepEqual([e.endLabel, e.nextDay, e.showRatios], ['00:00 (다음 날)', true, true]);
});
test('나가기 모드 창: 19:45 true, 19:44 false, 21:30 true, 21:31 false', () => {
  const a = h => L.exitModeActive({ now: new Date('2026-11-28T' + h + ':00'), showDateISO: '2026-11-28', startHour: 18, startMinute: 0, showMinutes: 120 });
  assert.deepEqual([a('19:45'), a('19:44'), a('21:30'), a('21:31')], [true, false, true, false]);
});
test('자정 넘김: 22시 공연, 다음 날 00:30 true', () => {
  assert.equal(L.exitModeActive({ now: new Date('2026-11-29T00:30:00'), showDateISO: '2026-11-28', startHour: 22, startMinute: 0, showMinutes: 120 }), true);
});
test('parseLive', () => {
  assert.equal(L.parseLive('[{"parking_sum":1961}]'), 1961);
  for (const bad of ['', '9999', '{', '[]', '[{"parking_sum":-3}]']) assert.equal(L.parseLive(bad), null);
});
test('outflow10: 10분 전 2000 → 지금 1860 = 140, 표본 부족이면 null', () => {
  const t0 = Date.parse('2026-11-28T20:00:00');
  assert.equal(L.outflow10([{ t: t0, n: 2000 }, { t: t0 + 10 * 60e3, n: 1860 }]), 140);
  assert.equal(L.outflow10([{ t: t0, n: 2000 }, { t: t0 + 3 * 60e3, n: 1990 }]), null);
});
```

- [ ] **Step 2: 실패 확인** — Run: `node --test tests/web/` · Expected: 새 테스트 FAIL (`L.exitPlan is not a function`)
- [ ] **Step 3: 함수 4개 구현** — 시각 계산은 분 단위 정수로, 날짜는 `showDateISO` 자정 기준 `Date`에 분을 더해 비교.
- [ ] **Step 4: 통과 확인** — Run: `node --test tests/web/` · Expected: all pass
- [ ] **Step 5: Commit** — `git commit -am "웹: 나가기 판단과 실시간 값 해석 로직"` (+ 테스트 파일 add)

### Task 3: 실시간 비교 기준값 (파이프라인)

**Files:**
- Create: `src/live_baseline.py`, `tests/test_live_baseline.py`
- Modify: `run_all.py` (steps 목록의 `src/exit_profile.py` 다음에 `["src/live_baseline.py"]`), `web/app/js/logic.js`, `tests/web/logic.test.js`

**Interfaces:**
- Consumes: `from metrics_2025 import load` → `(df, _, _)`, 열 `월, 요일유형('평일'|'주말·휴일'), 시, 주차대수, 공연일, 이상일`
- Produces:
  - `web/app/data/live_baseline.json`: `{"설명": str, "show_day": {"<월>": {"weekday": [24개 int|null], "weekend": [...]}}}` — 2025 **공연 날**, 이상일 제외, 월 8·9 제외, 칸별 표본 3일 미만이면 null
  - `baseline(table: dict, month: number, dayType: string, hour: number) -> number|null` (logic.js)
  - `src/live_baseline.py`의 `build(df: pd.DataFrame) -> dict`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_live_baseline.py` (`unittest`): 작은 가짜 DataFrame(11월 주말 공연일 3일, 18시 주차대수 4000/4200/4400 + 8월 하루)으로 `build(df)["show_day"]["11"]["weekend"][18] == 4200`, `"8" not in build(df)["show_day"]`, 표본 2일인 칸은 `None`. `tests/web/logic.test.js`에 `L.baseline({show_day:{'11':{weekend:[...18:4200...]}}}, 11, 'weekend', 18) === 4200`, `L.baseline(t, 8, 'weekend', 18) === null`, 없는 달 `null`.
- [ ] **Step 2: 실패 확인** — Run: `python -m unittest tests/test_live_baseline.py` · Expected: `ModuleNotFoundError`/`AttributeError`; `node --test tests/web/` FAIL
- [ ] **Step 3: `build(df)`와 `__main__` 구현** (`sys.path.insert`로 `src` 추가 후 `load()`, 결과를 JSON으로 저장, 칸 수 출력), `baseline()` 구현
- [ ] **Step 4: 통과·생성 확인** — Run: `python -m unittest tests/test_live_baseline.py && node --test tests/web/ && python src/live_baseline.py` · Expected: OK, all pass, `live_baseline.json 저장`
- [ ] **Step 5: Commit** — `git add src/live_baseline.py tests/test_live_baseline.py web/app/data/live_baseline.json run_all.py web/app/js/logic.js tests/web/logic.test.js && git commit -m "실시간 비교 기준: 2025 공연 날 월·요일유형·시각 중앙값"`

### Task 4: 캘린더 파일(.ics)과 공유 링크

**Files:**
- Modify: `web/app/js/logic.js`, `tests/web/logic.test.js`

**Interfaces:**
- Produces:
  - `buildIcs({dateISO: string, venueName: string, arriveHour: number|null, startHour: number, startMinute: number, showMinutes: number, mode: 'car'|'subway'}) -> string` — `BEGIN:VCALENDAR`…`END:VCALENDAR`, CRLF 줄바꿈, 일정 1개: 차면 도착 시각부터, 지하철이면 시작 1시간 전부터 종료까지, `TZID=Asia/Seoul`, `SUMMARY:<venueName> 공연 (덜붐빌때)`, `DESCRIPTION`에 권장 도착·출차 안내 한 줄, `BEGIN:VALARM` 30분 전
  - `shareText({dateISO: string, venueName: string, startHour: number, startMinute: number, advice: ReturnType<arrivalAdvice>, exit: ReturnType<exitPlan>, url: string}) -> string` — 공유는 링크 상태 저장이 아니라 **문구 복사**로 한다(아티팩트 해시 제약). 예: "11월 28일(토) KSPO DOME 18:00 · 차라면 15:00 전 도착, 끝나고 20분 뒤 출차 — 덜붐빌때 <url>"

- [ ] **Step 1: 실패하는 테스트** — `buildIcs`가 `DTSTART;TZID=Asia/Seoul:20261128T150000`(차, 15시), 지하철이면 `T170000`, `DTEND` `T200000`, `\r\n` 포함, `TRIGGER:-PT30M` 포함. `shareText(...)`가 위 예시 문구를 정확히 만든다.
- [ ] **Step 2: 실패 확인** — `node --test tests/web/` FAIL
- [ ] **Step 3: `buildIcs`, `shareText` 구현**
- [ ] **Step 4: 통과 확인** — `node --test tests/web/` all pass
- [ ] **Step 5: Commit** — `git commit -am "웹: 캘린더 파일과 공유 문구 만들기"`

### Task 5: 첫 화면(답 카드) 다시 짓기

**Files:**
- Modify (다시 씀): `web/app/index.html`
- Create: `tests/web/smoke.js`

**Interfaces:**
- Consumes: `Logic.dayType`, `Logic.levelOf`, `Logic.arrivalAdvice`, `Logic.baseline`; 데이터 `data/show_profile.json`, `data/exit_profile.json`, `data/live_baseline.json`, `data/seat_views.json`
- Produces: 전역 상태 `state = {venue, date, startHour, startMinute, rain}` (localStorage 키 `dbt.v3`, try/catch), 함수 `render()`, 라우트 `#home`(기본), DOM id: `#answer-title`, `#answer-sub`, `#live-line`, `#bars`, `#to-day`, `#to-seat`, `#to-plan`

- [ ] **Step 1: 스모크 테스트 작성** (`tests/web/smoke.js`, 기존 `scratchpad` 방식: 앞에 `<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">`를 붙인 임시 파일을 `python3 -m http.server`로 서빙, Chromium `proxy: { server: process.env.HTTPS_PROXY, bypass: 'localhost,127.0.0.1' }`). 검사: 날짜 2026-11-28·18:00을 고르면 `#answer-title`에 "지하철", `#answer-sub`에 "15:00"; 16:00으로 바꾸면 "차"; `document.documentElement.scrollWidth <= innerWidth`(390·1280); `pageerror` 0건; `localStorage`를 막은 컨텍스트(`addInitScript`로 getter가 throw)에서도 `#answer-title` 표시.
- [ ] **Step 2: 실패 확인** — Run: `node tests/web/smoke.js` · Expected: 선택자 없음으로 FAIL
- [ ] **Step 3: 화면 구현** — 설계 7-1 스케치대로. 입력: 공연장 5곳 칩, 날짜 띠(오늘부터 14일, 요일·주말 색), 시작 시각 칩(11:00–21:00, 30분 단위 아님 — 정시만), 비 체크. 답 카드: mode가 subway면 제목 "지하철을 권해요" + "그래도 차로 온다면 HH:00 전", car면 "차로 와도 돼요 · HH:00 전에 들어오세요". 시간대 막대(10–23시, 3단계 색, 도착·시작 표시)는 v2 설계안(`design/관람객화면_설계안/V2Arrive.dc.html`) 모양. 공원 전체 기준 문구, 지도 링크 `https://map.naver.com/p/search/올림픽공원역`, `https://map.kakao.com/?q=올림픽공원역`. 실시간 줄 자리(`#live-line`, 기본 hidden). 기존 `?` 사용법 대화상자 내용은 새 흐름에 맞게 고쳐 유지.
- [ ] **Step 4: 통과 확인** — Run: `node --test tests/web/ && node tests/web/smoke.js` · Expected: all pass, 스모크 "OK" 출력
- [ ] **Step 5: Commit** — `git add web/app/index.html tests/web/smoke.js && git commit -m "웹: 첫 화면을 차/지하철 답 카드로"`

### Task 6: 실시간 줄과 나가기 모드

**Files:**
- Create: `web/app/js/live.js`
- Modify: `web/app/index.html`, `tests/web/smoke.js`

**Interfaces:**
- Consumes: `Logic.parseLive`, `Logic.outflow10`, `Logic.exitPlan`, `Logic.exitModeActive`, `Logic.baseline`
- Produces: `Live.start(onUpdate: (n: number|null, samples) => void, everyMs = 90000)`, `Live.stop()` (`window.Live`); 라우트 `#exit`; DOM `#exit-now`, `#exit-wait`, `#exit-live`, `#timer-btn`, `#timer-left`

- [ ] **Step 1: 스모크 확장** — Playwright `page.route('**/parkingorsApi.do*', r => r.fulfill({ body: '[{"parking_sum":1961}]' }))`일 때 첫 화면(당일 날짜로 설정) `#live-line`에 "1,961"이 보임; `r.fulfill({ body: '9999' })`와 `r.abort()`일 때 `#live-line`이 hidden이고 pageerror 0건. `#exit`에서 18:00 공연: `#exit-wait`에 "42%", 14:00 공연: "42%" 없음.
- [ ] **Step 2: 실패 확인** — `node tests/web/smoke.js` FAIL
- [ ] **Step 3: 구현** — `live.js`: `fetch(URL, {cache: 'no-store'})`, 8초 `AbortController` 시간 초과, 표본은 최근 30분만 메모리에 보관, 실패하면 `onUpdate(null)`. 화면이 숨겨지면(`visibilitychange`) 멈춤. 첫 화면은 공연 당일일 때만 실시간 줄 "지금 주차장 N대" + 기준값 있으면 "· 2025년 이맘때 공연 날 M대". 첫 화면에서 `exitModeActive`가 true면 맨 위에 "공연 끝났나요? 나가기 안내 보기" 띠. `#exit` 화면은 설계 7-2 스케치: 지금 나가면 = 가장 몰리는 때, 20분 뒤 = `wait.ratio`를 %로, 실시간 "지금 N대 · 최근 10분 동안 K대 줄었어요"(`outflow10`이 null이면 앞부분만), 20분 타이머(남은 시간 표시, 끝나면 `navigator.vibrate?.(…)`과 짧은 소리 `AudioContext`, 실패해도 무시), 버튼 아래 "화면을 열어 둔 동안만 알려 드려요", 몰림 모양 출처 한 줄("2024년 7월 저녁 출차가 몰린 N일, 가장 몰린 10분 기준" — N은 `exit_decay.저녁수`).
- [ ] **Step 4: 통과 확인** — `node --test tests/web/ && node tests/web/smoke.js` all pass
- [ ] **Step 5: Commit** — `git add web/app/js/live.js web/app/index.html tests/web/smoke.js && git commit -m "웹: 실시간 주차 줄과 나가기 모드"`

### Task 7: 하루 미리 보기(3D)·내 자리·일정표

**Files:**
- Modify: `web/app/index.html`, `tests/web/smoke.js`

**Interfaces:**
- Consumes: 기존 3D 코드(현재 `index.html`의 `model-viewer` 설정, `seatCam`, `setShell`, 무거운 모델 누를 때 불러오기), `seat_views.json`, `Logic.exitPlan`, `Logic.buildIcs`, `Logic.shareText`
- Produces: 라우트 `#day`, `#seat`, `#plan`; DOM `#day-stops`(단계 버튼 4개), `#ics-btn`, `#share-btn`

- [ ] **Step 1: 스모크 확장** — `#day`에서 단계 버튼 4개(도착·공연·끝·출차), "끝" 누르면 3D 시점이 바뀌고(`mv.cameraOrbit` 값 변화) 안내에 "20분"; `#plan`에서 `#ics-btn` 클릭 시 `a[download$=".ics"]`가 만들어짐(내용에 `BEGIN:VCALENDAR`), `#share-btn` 클릭 시 클립보드 실패해도 문구가 선택 가능한 텍스트로 보임.
- [ ] **Step 2: 실패 확인** — `node tests/web/smoke.js` FAIL
- [ ] **Step 3: 구현** — 설계안 `V3Day`·`V3Plan` 모양(파일: `design/관람객화면_설계안/V3Day.dc.html`, `V3Plan.dc.html`). 단계별 카메라: 도착·출차 = `'205deg 70deg 190m'` target `'0m 12m 0m'` fov `'40deg'`(외피 끔), 공연 = `seatCam(현재 자리)`, 끝 = `'0deg 84deg 26m'` target `'0m 6m -10m'` fov `'68deg'`. KSPO DOME이 아닌 공연장은 공연 단계도 기본 시점. 단계 안내 숫자는 모두 `arrivalAdvice`/`exitPlan` 결과에서. 내 자리(`#seat`)는 현재 화면의 자리 고르기를 옮겨 오고 v2 설계처럼 그림 위 버튼으로. 일정표는 `V3Plan`처럼 세로 시간표 + 왼쪽 혼잡 띠. `.ics`는 `Blob` + `a.download`(아티팩트에서는 막힘 → 버튼 아래 "공개 주소에서 저장돼요" 문구).
- [ ] **Step 4: 통과 확인** — `node --test tests/web/ && node tests/web/smoke.js` all pass
- [ ] **Step 5: Commit** — `git commit -am "웹: 하루 미리 보기, 내 자리, 일정표·캘린더"`

### Task 8: 공개와 문서

**Files:**
- Modify: `README.md`(데이터 표에 실시간 주차현황 15168686 추가, 웹 실행·테스트 방법), `기획안.md`(서비스 정의·기능 목록을 설계 문서 기준으로), `web/app/index.html`(필요 시 문구)

- [ ] **Step 1: 전체 검증** — Run: `node --test tests/web/ && python -m unittest discover tests && node tests/web/smoke.js` · Expected: all pass
- [ ] **Step 2: 아티팩트 다시 올리기** — 같은 파일 경로 `web/app/index.html`로 publish, `files`에 `js/logic.js`, `js/live.js`, `data/live_baseline.json`, `data/exit_profile.json` 추가(기존 파일은 유지됨)
- [ ] **Step 3: 문서 고치기** — README 데이터 표에 "한국체육산업개발주식회사_실시간 주차현황 (15168686) | API | 제한 없음", 기획안 1-2 기능 목록을 답 카드 / 나가기 모드 / 실시간 / 하루 미리 보기 / 내 자리 / 일정표·캘린더로 교체, "공원 나들이 모드" 삭제
- [ ] **Step 4: Commit & push** — `git add -A README.md 기획안.md web && git commit -m "문서: 주차 비서 방향 반영" && git push`
- [ ] **Step 5: 공개 확인 안내** — 사용자가 저장소를 공개로 바꾸고 Settings → Pages → Source를 "GitHub Actions"로 설정하면, Actions 실행 뒤 `https://tak7257-dot.github.io/kspo-report/`에서 실시간 줄이 실제 값으로 뜨는지 확인한다.
