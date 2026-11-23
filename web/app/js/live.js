/* 실시간 주차현황 API를 일정 간격으로 불러오는 작은 도우미 (브라우저 전용).
   한국체육산업개발 「올림픽공원 실시간 주차현황」(공공데이터포털 15168686), 인증키는 기관이 공개한 값.
   실패(점검 중, 시간 초과, 미리보기 화면의 외부 호출 차단)하면 onUpdate(null)로 알려 화면이 그 줄만 숨긴다. */
(function (root) {
  'use strict';
  var URL = 'https://www.ksponco.or.kr/online/main/parkingorsApi.do?apiKey=PARKING21803504';
  var KEEP_MS = 30 * 60e3;     // 표본은 최근 30분만 기억
  var samples = [], timer = null, listener = null, every = 90e3;

  function once() {
    var ctl = typeof AbortController === 'function' ? new AbortController() : null;
    var stop = ctl ? setTimeout(function () { ctl.abort(); }, 8000) : null;
    return fetch(URL, { cache: 'no-store', signal: ctl ? ctl.signal : undefined })
      .then(function (r) { return r.ok ? r.text() : ''; })
      .catch(function () { return ''; })
      .then(function (text) {
        if (stop) clearTimeout(stop);
        var n = root.Logic.parseLive(text);
        var now = Date.now();
        if (n !== null) samples.push({ t: now, n: n });
        samples = samples.filter(function (s) { return now - s.t <= KEEP_MS; });
        if (listener) listener(n, samples.slice());
      });
  }

  function start(onUpdate, everyMs) {
    listener = onUpdate; every = everyMs || 90e3;
    if (timer) return;
    once();
    timer = setInterval(once, every);
  }
  function stop() { if (timer) clearInterval(timer); timer = null; listener = null; }

  // 화면이 숨겨지면 멈추고, 다시 보이면 이어서 (배터리·데이터 아끼기)
  document.addEventListener('visibilitychange', function () {
    if (!listener) return;
    if (document.hidden) { if (timer) clearInterval(timer); timer = null; }
    else if (!timer) { once(); timer = setInterval(once, every); }
  });

  root.Live = { start: start, stop: stop, samples: function () { return samples.slice(); } };
})(this);
