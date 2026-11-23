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
