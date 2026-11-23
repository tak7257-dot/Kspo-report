// 덜붐빌때 판단 로직 테스트 — 실행: node --test tests/web/
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const L = require('../../web/app/js/logic.js');
const P = require(path.join(__dirname, '../../web/app/data/show_profile.json')).profile;

const adv = (profile, startHour, rain = false) => L.arrivalAdvice({ profile, startHour, rain, rainFactor: 0.907 });

// ── Task 1: 도착 판단 ──
test('주말 18시 → 지하철, 차라면 15시', () => {
  const r = adv(P.weekend, 18);
  assert.deepEqual([r.mode, r.arriveHour, r.leadHours, r.firstVeryBusyHour], ['subway', 15, 3, 16]);
});
test('주말 17시 → 2시간 차라 차 괜찮음', () => {
  const r = adv(P.weekend, 17);
  assert.deepEqual([r.mode, r.arriveHour], ['car', 15]);
});
test('주말 16시 → 차, 15시', () => assert.equal(adv(P.weekend, 16).mode, 'car'));
test('평일 20시 → 차, 19시, 매우 붐비는 시각 없음', () => {
  const r = adv(P.weekday, 20);
  assert.deepEqual([r.mode, r.arriveHour, r.firstVeryBusyHour], ['car', 19, null]);
});
test('비 오면 지수가 줄어 답이 바뀜: 주말 18시 비 → 16시', () => {
  assert.equal(adv(P.weekend, 18, true).arriveHour, 16);
});
test('도착 가능 시각이 없으면 arriveHour null, 지하철', () => {
  const r = adv(Array(24).fill(250), 18);
  assert.deepEqual([r.mode, r.arriveHour, r.leadHours], ['subway', null, null]);
});
test('dayType: 2026-11-28 토 weekend, 11-30 월 weekday, 12-25 성탄절 weekend', () => {
  assert.equal(L.dayType('2026-11-28'), 'weekend');
  assert.equal(L.dayType('2026-11-30'), 'weekday');
  assert.equal(L.dayType('2026-12-25'), 'weekend');
});
test('levelOf 경계: 129 보통, 130 붐빔, 200 매우 붐빔', () => {
  assert.equal(L.levelOf(129), 'normal');
  assert.equal(L.levelOf(130), 'busy');
  assert.equal(L.levelOf(200), 'very');
});

// ── Task 2: 나가기 판단과 실시간 값 ──
const D = { offsets_min: [0, 10, 20, 30, 40, 50, 60], ratio: [1, 0.68, 0.42, 0.41, 0.44, 0.57, 0.54] };
test('18시+120분 → 20:00, 비율 표시, 20분 뒤 0.42', () => {
  const e = L.exitPlan({ startHour: 18, startMinute: 0, showMinutes: 120, decay: D });
  assert.deepEqual([e.endLabel, e.showRatios, e.wait.minutes, e.wait.ratio], ['20:00', true, 20, 0.42]);
});
test('14시 공연 → 16:00, 비율 숨김', () => {
  assert.equal(L.exitPlan({ startHour: 14, startMinute: 0, showMinutes: 120, decay: D }).showRatios, false);
});
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
test('parseLive: 정상 값만 숫자, 나머지 null', () => {
  assert.equal(L.parseLive('[{"parking_sum":1961}]'), 1961);
  for (const bad of ['', '9999', '{', '[]', '[{"parking_sum":-3}]']) assert.equal(L.parseLive(bad), null);
});
test('outflow10: 10분 전 2000 → 지금 1860 = 140, 표본 부족이면 null', () => {
  const t0 = Date.parse('2026-11-28T20:00:00');
  assert.equal(L.outflow10([{ t: t0, n: 2000 }, { t: t0 + 10 * 60e3, n: 1860 }]), 140);
  assert.equal(L.outflow10([{ t: t0, n: 2000 }, { t: t0 + 3 * 60e3, n: 1990 }]), null);
});

// ── Task 3: 실시간 비교 기준값 ──
test('baseline: 있는 칸은 값, 8월·없는 달은 null', () => {
  const wk = Array(24).fill(null); wk[18] = 4200;
  const t = { show_day: { '11': { weekend: wk, weekday: Array(24).fill(null) } } };
  assert.equal(L.baseline(t, 11, 'weekend', 18), 4200);
  assert.equal(L.baseline(t, 8, 'weekend', 18), null);
  assert.equal(L.baseline(t, 12, 'weekend', 18), null);
  assert.equal(L.baseline(t, 11, 'weekday', 18), null);
});

// ── Task 4: 캘린더 파일과 공유 문구 ──
const ICS_BASE = { dateISO: '2026-11-28', venueName: 'KSPO DOME', startHour: 18, startMinute: 0, showMinutes: 120, now: new Date('2026-11-23T10:00:00Z') };
test('buildIcs: 차면 도착 15시부터 20시까지, CRLF, 30분 전 알림', () => {
  const s = L.buildIcs({ ...ICS_BASE, arriveHour: 15, mode: 'car' });
  assert.match(s, /^BEGIN:VCALENDAR\r\n/);
  assert.ok(s.includes('DTSTART;TZID=Asia/Seoul:20261128T150000\r\n'));
  assert.ok(s.includes('DTEND;TZID=Asia/Seoul:20261128T200000\r\n'));
  assert.ok(s.includes('TRIGGER:-PT30M'));
  assert.ok(s.includes('SUMMARY:KSPO DOME 공연 (덜붐빌때)'));
  assert.match(s, /END:VCALENDAR\r\n$/);
});
test('buildIcs: 지하철이면 시작 1시간 전부터', () => {
  assert.ok(L.buildIcs({ ...ICS_BASE, arriveHour: 15, mode: 'subway' }).includes('DTSTART;TZID=Asia/Seoul:20261128T170000'));
});
test('buildIcs: 22시 공연은 다음 날 00시에 끝남', () => {
  assert.ok(L.buildIcs({ ...ICS_BASE, startHour: 22, arriveHour: 21, mode: 'car' }).includes('DTEND;TZID=Asia/Seoul:20261129T000000'));
});
test('shareText: 지하철 추천 문구', () => {
  const advice = L.arrivalAdvice({ profile: P.weekend, startHour: 18, rain: false, rainFactor: 0.907 });
  const exit = L.exitPlan({ startHour: 18, startMinute: 0, showMinutes: 120, decay: D });
  assert.equal(L.shareText({ dateISO: '2026-11-28', venueName: 'KSPO DOME', startHour: 18, startMinute: 0, advice, exit, url: 'https://x.example/' }),
    '11월 28일(토) KSPO DOME 18:00 · 지하철 추천 (차라면 15:00 전 도착) — 덜붐빌때 https://x.example/');
});
test('shareText: 차 문구와 출차 안내', () => {
  const advice = L.arrivalAdvice({ profile: P.weekday, startHour: 19, rain: false, rainFactor: 0.907 });
  const exit = L.exitPlan({ startHour: 19, startMinute: 0, showMinutes: 120, decay: D });
  assert.equal(L.shareText({ dateISO: '2026-11-30', venueName: 'KSPO DOME', startHour: 19, startMinute: 0, advice, exit, url: 'https://x.example/' }),
    '11월 30일(월) KSPO DOME 19:00 · 차는 18:00 전 도착, 끝나고 20분 뒤 출차 — 덜붐빌때 https://x.example/');
});

// ── 운영 기간(2028년)까지 공휴일 ──
test('dayType: 2028 설날(1/26)·총선(4/12)·추석 대체공휴일(10/5)은 weekend, 2028-10-06 금은 weekday', () => {
  assert.equal(L.dayType('2028-01-26'), 'weekend');
  assert.equal(L.dayType('2028-04-12'), 'weekend');
  assert.equal(L.dayType('2028-10-05'), 'weekend');
  assert.equal(L.dayType('2028-10-06'), 'weekday');
});
