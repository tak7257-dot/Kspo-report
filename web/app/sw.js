/* 덜붐빌때 서비스 워커: 한 번 연 화면은 공연장 안처럼 전파가 약해도 열리게 한다.
   - 화면·데이터(JSON): 인터넷 먼저, 안 되면 저장본 (새 분석이 올라가면 바로 반영)
   - 글꼴·그림·3D·스크립트: 저장본 먼저 (크고 잘 안 바뀜). 3D는 처음 볼 때 저장
   - 실시간 주차 API 같은 다른 사이트 요청은 건드리지 않는다 (지난 숫자를 '지금'처럼 보여 주면 안 됨)
   VERSION 은 tools/build_site.sh 가 배포할 때 커밋 번호로 바꾼다 → 새로 올리면 옛 저장본을 지운다. */
const VERSION = '__BUILD__';
const CACHE = 'dbt-' + VERSION;
const SHELL = [
  './', 'index.html', 'manifest.webmanifest', 'js/logic.js', 'js/live.js', 'fonts/DBTSans-Variable.woff2',
  'data/show_profile.json', 'data/exit_profile.json', 'data/live_baseline.json', 'data/seat_views.json',
  'data/park_facts.json', 'data/nowcast_check.json',
  'icons/icon-192.png', 'icons/apple-touch-icon.png', 'icons/favicon-32.png'
];
const CDN = 'https://cdn.jsdelivr.net/npm/@google/model-viewer@';

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k.startsWith('dbt-') && k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

function networkFirst(req) {
  return fetch(req).then(res => {
    if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
    return res;
  }).catch(() => caches.match(req, { ignoreSearch: true }).then(hit => hit || caches.match('index.html')));
}

function cacheFirst(req) {
  return caches.match(req).then(hit => hit || fetch(req).then(res => {
    if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
    return res;
  }));
}

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.href.startsWith(CDN)) { e.respondWith(cacheFirst(req)); return; }   // 3D 보기 도구 (버전 고정)
  if (url.origin !== self.location.origin) return;                         // 실시간 주차 API 등: 손대지 않음
  if (req.mode === 'navigate' || url.pathname.endsWith('.html') || url.pathname.includes('/data/')) {
    e.respondWith(networkFirst(req));
  } else {
    e.respondWith(cacheFirst(req));
  }
});
