/* 덜붐빌때 판단 로직 — 화면(DOM)과 상관없는 계산만 모아 둔 파일.
   브라우저에서는 window.Logic, Node 테스트에서는 require()로 쓴다. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Logic = factory();
})(this, function () {
  'use strict';

  // 공휴일(대체공휴일 포함). 행정안전부 공휴일 기준, 바뀌면 이 목록만 고치세요.
  var HOLIDAYS = [
    '2026-01-01', '2026-02-16', '2026-02-17', '2026-02-18', '2026-03-01', '2026-03-02', '2026-05-05', '2026-05-24',
    '2026-05-25', '2026-06-03', '2026-06-06', '2026-08-15', '2026-08-17', '2026-09-24', '2026-09-25', '2026-09-26',
    '2026-10-03', '2026-10-05', '2026-10-09', '2026-12-25',
    '2027-01-01', '2027-02-06', '2027-02-07', '2027-02-08', '2027-02-09', '2027-03-01', '2027-05-05', '2027-05-13',
    '2027-06-06', '2027-08-15', '2027-08-16', '2027-09-14', '2027-09-15', '2027-09-16', '2027-10-03', '2027-10-04',
    '2027-10-09', '2027-10-11', '2027-12-25', '2027-12-27'
  ];

  var BUSY = 130, VERY_BUSY = 200;   // 평소의 1.3배 붐빔, 2배 매우 붐빔 (show_profile.json levels와 같은 값)
  var MAX_LEAD_HOURS = 2;            // 권장 도착이 시작보다 2시간 넘게 이르면 지하철을 권한다 (사용자 결정)
  var EARLIEST_HOUR = 10;            // 10시보다 이른 도착은 권하지 않는다

  // 토·일·공휴일이면 'weekend', 아니면 'weekday'
  function dayType(dateISO) {
    var d = new Date(dateISO + 'T00:00:00');
    var w = d.getDay();
    return (w === 0 || w === 6 || HOLIDAYS.indexOf(dateISO) >= 0) ? 'weekend' : 'weekday';
  }

  // 혼잡 지수(평소 = 100) → 3단계
  function levelOf(index) {
    return index >= VERY_BUSY ? 'very' : index >= BUSY ? 'busy' : 'normal';
  }

  // 차를 가져가도 될까? 시작 1시간 전부터 거꾸로 보며, 평소의 2배 아래인 가장 늦은 시각을 권장 도착으로.
  function arrivalAdvice(o) {
    var f = o.rain ? o.rainFactor : 1;
    var idx = o.profile.map(function (v) { return v * f; });
    var arrive = null;
    for (var h = o.startHour - 1; h >= EARLIEST_HOUR; h--) {
      if (idx[h] < VERY_BUSY) { arrive = h; break; }
    }
    var firstVery = null;
    for (var k = EARLIEST_HOUR; k < o.startHour; k++) {
      if (idx[k] >= VERY_BUSY) { firstVery = k; break; }
    }
    var lead = arrive === null ? null : o.startHour - arrive;
    return {
      mode: (arrive === null || lead > MAX_LEAD_HOURS) ? 'subway' : 'car',
      arriveHour: arrive,
      leadHours: lead,
      firstVeryBusyHour: firstVery,
      indexAtArrive: arrive === null ? null : idx[arrive]
    };
  }

  return { HOLIDAYS: HOLIDAYS, dayType: dayType, levelOf: levelOf, arrivalAdvice: arrivalAdvice };
});
