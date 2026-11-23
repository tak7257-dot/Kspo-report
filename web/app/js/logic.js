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

  var pad2 = function (n) { return (n < 10 ? '0' : '') + n; };
  var WAIT_MINUTES = 20;     // 끝나고 기다렸다 나가기를 권하는 시간
  var EVENING_MIN = 20 * 60; // 출차 몰림 모양은 20:30 이후 저녁 기록 → 20시 이후 끝나는 공연에만 비율을 보여 준다

  // 공연이 언제 끝나고, 20분 기다리면 출차가 얼마로 줄어드는지
  function exitPlan(o) {
    var end = o.startHour * 60 + o.startMinute + o.showMinutes;
    var nextDay = end >= 24 * 60;
    var m = end % (24 * 60);
    var i = o.decay.offsets_min.indexOf(WAIT_MINUTES);
    return {
      endHour: Math.floor(m / 60), endMinute: m % 60, nextDay: nextDay,
      endLabel: pad2(Math.floor(m / 60)) + ':' + pad2(m % 60) + (nextDay ? ' (다음 날)' : ''),
      showRatios: end >= EVENING_MIN,
      wait: { minutes: WAIT_MINUTES, ratio: o.decay.ratio[i] }
    };
  }

  // 나가기 모드를 띄울 때인가: 예상 종료 15분 전부터 종료 90분 뒤까지
  function exitModeActive(o) {
    var day0 = new Date(o.showDateISO + 'T00:00:00').getTime();
    var end = day0 + (o.startHour * 60 + o.startMinute + o.showMinutes) * 60e3;
    var t = o.now.getTime();
    return t >= end - 15 * 60e3 && t <= end + 90 * 60e3;
  }

  // 실시간 주차 API 응답 '[{"parking_sum":1961}]' → 1961. 점검(9999)·빈 응답·이상한 값은 null
  function parseLive(text) {
    try {
      var j = JSON.parse(text);
      var n = Array.isArray(j) && j[0] ? j[0].parking_sum : null;
      return (typeof n === 'number' && isFinite(n) && n >= 0) ? n : null;
    } catch (e) { return null; }
  }

  // 최근 10분 동안 줄어든 대수: 가장 최근 표본과 8~12분 앞선 표본의 차이. 맞는 표본이 없으면 null
  function outflow10(samples) {
    if (!samples || samples.length < 2) return null;
    var last = samples[samples.length - 1], best = null;
    for (var i = 0; i < samples.length - 1; i++) {
      var gap = last.t - samples[i].t;
      if (gap >= 8 * 60e3 && gap <= 12 * 60e3 && (best === null || Math.abs(gap - 6e5) < Math.abs(last.t - best.t - 6e5))) best = samples[i];
    }
    return best === null ? null : Math.max(0, best.n - last.n);
  }

  // 실시간 비교 기준값(2025년 공연 날 같은 달·요일유형·시각 중앙값). 없으면 null
  function baseline(table, month, dayKind, hour) {
    var m = table && table.show_day && table.show_day[String(month)];
    var v = m && m[dayKind] ? m[dayKind][hour] : null;
    return typeof v === 'number' ? v : null;
  }

  return {
    baseline: baseline,
    HOLIDAYS: HOLIDAYS, dayType: dayType, levelOf: levelOf, arrivalAdvice: arrivalAdvice,
    exitPlan: exitPlan, exitModeActive: exitModeActive, parseLive: parseLive, outflow10: outflow10
  };
});
