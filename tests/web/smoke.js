// 덜붐빌때 화면 스모크 테스트 — 실행: node tests/web/smoke.js
// web/app 을 임시 폴더에 펼쳐(문자셋 머리말 추가) 로컬 서버로 띄우고, 컴퓨터·휴대폰·다크·저장소 차단 환경에서 확인한다.
// 실시간 주차 API는 가짜 응답으로 바꿔 끼운다(실제 기관 서버를 부르지 않음).
const { chromium, devices } = require('playwright');
const fs = require('fs'), os = require('os'), path = require('path'), { spawn } = require('child_process');

const PORT = 8790;
const NOW = new Date('2026-11-23T10:00:00+09:00');   // 테스트 기준 "오늘"
const fails = [];
const check = (name, ok, extra = '') => { if (!ok) fails.push(name + (extra ? ' — ' + extra : '')); console.log((ok ? 'ok   ' : 'FAIL ') + name); };

function serveDir() {   // GitHub Pages에 올라갈 결과물 그대로 (tools/build_site.sh)
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'dbt-'));
  require('child_process').execFileSync('sh', [path.resolve(__dirname, '../../tools/build_site.sh'), dir]);
  return dir;
}

async function open(browser, opts, live = 'abort', hash = '#home', blockStorage = false, now = NOW) {
  // 서비스 워커는 기본으로 막는다(가짜 실시간 응답이 워커를 거치지 않게). 앱 설치 확인만 serviceWorkers: 'allow'.
  const ctx = await browser.newContext({ timezoneId: 'Asia/Seoul', serviceWorkers: 'block', ...opts });
  if (blockStorage) await ctx.addInitScript(() => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } }); });
  const page = await ctx.newPage();
  await page.clock.setFixedTime(now);
  page.errors = [];
  page.on('pageerror', e => page.errors.push(e.message));
  await page.route('**/parkingorsApi.do*', r => live === 'abort' ? r.abort() : r.fulfill({ status: 200, contentType: 'text/html', body: live }));
  await page.goto(`http://localhost:${PORT}/index.html${hash}`);
  await page.waitForSelector('#answer-title:not(:empty)', { timeout: 20000 });
  return page;
}
const text = (page, sel) => page.locator(sel).innerText();
const noSideScroll = page => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

(async () => {
  const dir = serveDir();
  const server = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1'], { cwd: dir, stdio: 'ignore' });
  await new Promise(r => setTimeout(r, 800));
  const browser = await chromium.launch({ proxy: { server: process.env.HTTPS_PROXY, bypass: 'localhost,127.0.0.1' } });
  try {
    // ── Task 5: 첫 화면 답 카드 ──
    for (const [name, opts] of [['컴퓨터', { viewport: { width: 1280, height: 860 } }], ['휴대폰', devices['iPhone 13']], ['휴대폰 다크', { ...devices['iPhone 13'], colorScheme: 'dark' }]]) {
      const page = await open(browser, opts);
      check(`${name}: 처음 오면 바꾸기 펼침`, await page.evaluate(() => document.getElementById('change').open));
      await page.click('button[data-date="2026-11-28"]');
      await page.click('button[data-start="18"]');
      check(`${name}: 주말 18시 → 지하철`, (await text(page, '#answer-title')).includes('지하철'));
      check(`${name}: 차라면 15:00`, (await text(page, '#answer-sub')).includes('15:00'));
      check(`${name}: 꼬리표에 도착 15:00`, (await text(page, '#stub')).includes('15:00'));
      check(`${name}: 차라면 주차비 19,200원 (15:00~20:20)`, (await text(page, '#fee')).includes('19,200원'));
      check(`${name}: 예상임을 밝힘 (실제 공연 정보 아님)`, (await text(page, '#ticket-kind')).includes('예상'));
      await page.click('button[data-start="16"]');
      check(`${name}: 주말 16시 → 차`, (await text(page, '#answer-title')).includes('차'));
      check(`${name}: 16시 공연 주차비 10,800원 (15:00~18:00)`, (await text(page, '#fee')).includes('10,800원'));
      check(`${name}: 가로 스크롤 없음`, await noSideScroll(page));
      check(`${name}: 차 답이면 주차장 길찾기`, (await text(page, '#maplinks').catch(() => '')).includes('주차장'));
      check(`${name}: 공연 날이 아니면 나가기 띠 숨김`, await page.locator('#exit-band').isHidden());
      await page.click('button[data-venue="handball"]');
      check(`${name}: 다른 공연장이면 내 자리 링크 숨김`, await page.locator('#to-seat').isHidden());
      await page.click('button[data-venue="kspo-dome"]');
      if (name !== '컴퓨터') check(`${name}: 휴대폰 폭으로 그려짐`, (await page.evaluate(() => innerWidth)) === 390);
      check(`${name}: 실시간 실패 시 줄 숨김`, await page.locator('#live-line').isHidden());
      check(`${name}: 페이지 오류 없음`, page.errors.length === 0, page.errors.join(' | '));
      await page.context().close();
    }
    {
      const page = await open(browser, devices['iPhone 13'], 'abort', '#home', true);
      check('저장소 차단: 답 카드 표시', (await text(page, '#answer-title')).length > 0);
      check('저장소 차단: 페이지 오류 없음', page.errors.length === 0, page.errors.join(' | '));
      await page.context().close();
    }
    {
      // 선택은 다시 열어도 기억된다
      const page = await open(browser, devices['iPhone 13']);
      await page.click('button[data-date="2026-11-30"]');
      await page.click('button[data-start="19"]');
      await page.reload();
      await page.waitForSelector('#answer-title:not(:empty)');
      check('다시 열면 바꾸기 접힘(답부터 보임)', await page.evaluate(() => !document.getElementById('change').open));
      check('다시 열면 고른 날짜·시각 기억', (await text(page, '#answer-sub')).includes('18:00') || (await text(page, '#answer-title')).includes('18:00'));
      await page.context().close();
    }
    // ── Task 6: 실시간 줄과 나가기 모드 ──
    {
      const page = await open(browser, devices['iPhone 13'], '[{"parking_sum":1961}]');
      await page.click('button[data-date="2026-11-23"]');
      await page.waitForSelector('#live-line:not([hidden])', { timeout: 10000 }).catch(() => {});
      check('실시간: 오늘 고르면 지금 대수 표시', (await page.locator('#live-line').isVisible()) && (await text(page, '#live-line')).includes('1,961'));
      await page.click('button[data-date="2026-11-28"]');
      check('실시간: 다른 날 고르면 줄 숨김', await page.locator('#live-line').isHidden());
      await page.context().close();
    }
    {
      const page = await open(browser, devices['iPhone 13'], '9999');
      await page.click('button[data-date="2026-11-23"]');
      await page.waitForTimeout(1500);
      check('실시간: 점검 응답(9999)이면 줄 숨김', await page.locator('#live-line').isHidden());
      check('실시간: 점검 응답에도 페이지 오류 없음', page.errors.length === 0, page.errors.join(' | '));
      await page.context().close();
    }
    {
      const page = await open(browser, devices['iPhone 13'], '[{"parking_sum":1961}]', '#home', false, new Date('2026-11-23T19:50:00+09:00'));
      await page.click('button[data-date="2026-11-23"]');
      await page.click('button[data-start="18"]');
      check('나가기: 끝날 무렵 첫 화면에 안내 띠', await page.locator('#exit-band').isVisible());
      await page.click('#exit-band');
      await page.waitForSelector('#s-exit:not([hidden])');
      check('나가기: 18시 공연은 20분 뒤 42%', (await text(page, '#exit-wait')).includes('42%'));
      check('나가기: 실시간 대수', (await text(page, '#exit-live')).includes('1,961'));
      await page.click('#timer-btn');
      check('나가기: 타이머 남은 시간 표시', (await text(page, '#timer-left')).includes('20:00'));
      check('나가기: 가로 스크롤 없음', await noSideScroll(page));
      check('나가기: 페이지 오류 없음', page.errors.length === 0, page.errors.join(' | '));
      await page.goto(page.url().replace('#exit', '#home'));
      await page.waitForSelector('#answer-title:not(:empty)');
      await page.click('button[data-start="14"]').catch(async () => { await page.click('#change summary'); await page.click('button[data-start="14"]'); });
      await page.goto(page.url().replace('#home', '#exit'));
      await page.waitForSelector('#s-exit:not([hidden])');
      check('나가기: 14시 공연은 비율 숨김', !(await text(page, '#exit-wait')).includes('42%'));
      await page.context().close();
    }
    // ── Task 7: 하루 미리 보기·내 자리·일정표 ──
    {
      const page = await open(browser, { viewport: { width: 1280, height: 860 } });
      await page.click('button[data-date="2026-11-28"]');
      await page.click('button[data-start="18"]');
      await page.click('#to-day');
      await page.waitForSelector('#s-day:not([hidden])');
      check('하루: 단계 버튼 4개', (await page.locator('#day-stops button').count()) === 4);
      const cam0 = await page.evaluate(() => document.getElementById('mv').dataset.cam);
      await page.locator('#day-stops button').nth(2).click();
      const cam2 = await page.evaluate(() => document.getElementById('mv').dataset.cam);
      check('하루: 끝 단계에서 3D 시점이 바뀜', cam0 !== cam2 && cam2 === 'end', `${cam0} → ${cam2}`);
      check('하루: 끝 단계 안내에 20분', (await text(page, '#day-card')).includes('20분'));
      check('하루: 가로 스크롤 없음', await noSideScroll(page));
      await page.goto(page.url().replace('#day', '#seat'));
      await page.waitForSelector('#seat-pick:not([hidden])');
      check('내 자리: 구역 버튼 8개', (await page.locator('.seat-btn').count()) === 8);
      await page.click('.seat-btn[data-id="l2-center"]');
      check('내 자리: 2층 정면 무대까지 72m', (await text(page, '#seat-now')).includes('72m'));
      check('내 자리: 시점이 자리로', await page.evaluate(() => document.getElementById('mv').dataset.cam === 'seat:l2-center'));
      check('하루·내 자리: 페이지 오류 없음', page.errors.length === 0, page.errors.join(' | '));
      await page.context().close();
    }
    {
      const page = await open(browser, devices['iPhone 13']);
      await page.click('button[data-date="2026-11-28"]');
      await page.click('button[data-start="18"]');
      await page.goto(page.url().replace('#home', '#plan'));
      await page.waitForSelector('#s-plan:not([hidden])');
      check('일정표: 시작·끝 일정 표시', (await text(page, '#s-plan')).includes('18:00') && (await text(page, '#s-plan')).includes('20:00'));
      await page.click('#ics-btn');
      const ics = await page.evaluate(async () => { const a = document.getElementById('ics-link'); return a && a.download.endsWith('.ics') ? (await fetch(a.href)).text() : ''; });
      check('일정표: 캘린더 파일 만들기', ics.includes('BEGIN:VCALENDAR') && ics.includes('20261128T170000'));
      await page.click('#share-btn');
      check('일정표: 공유 문구 보임', (await page.locator('#share-text').isVisible()) && (await text(page, '#share-text')).includes('덜붐빌때'));
      check('일정표: 가로 스크롤 없음', await noSideScroll(page));
      check('일정표: 페이지 오류 없음', page.errors.length === 0, page.errors.join(' | '));
      await page.context().close();
    }
    // ── 최종 검토에서 나온 것 ──
    {
      // I1: 자정 넘긴 공연은 다음 날 새벽에 열어도 그 공연 그대로, 나가기 띠 표시
      const page = await open(browser, devices['iPhone 13'], 'abort', '#home', false, new Date('2026-11-28T18:00:00+09:00'));
      await page.click('button[data-date="2026-11-28"]');
      await page.click('button[data-start="22"]');
      await page.clock.setFixedTime(new Date('2026-11-29T00:10:00+09:00'));
      await page.reload(); await page.waitForSelector('#answer-title:not(:empty)');
      check('자정 넘김: 다음 날 00:10에도 11월 28일 공연', (await text(page, '#what')).includes('11. 28'));
      check('자정 넘김: 나가기 띠 표시', await page.locator('#exit-band').isVisible());
      await page.context().close();
    }
    {
      // I2: 열어 둔 화면으로 돌아오면 나가기 띠가 저절로 뜸, 띠는 표 위에
      const page = await open(browser, devices['iPhone 13'], 'abort', '#home', false, new Date('2026-11-23T19:30:00+09:00'));
      await page.click('button[data-date="2026-11-23"]');
      await page.click('button[data-start="18"]');
      check('열어 둔 화면: 19:30엔 띠 없음', await page.locator('#exit-band').isHidden());
      await page.clock.setFixedTime(new Date('2026-11-23T19:50:00+09:00'));
      await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
      check('열어 둔 화면: 19:50에 돌아오면 띠 표시', await page.locator('#exit-band').isVisible());
      const [band, ticket] = await Promise.all([page.locator('#exit-band').boundingBox(), page.locator('.ticket').boundingBox()]);
      check('나가기 띠는 표 위에', band && ticket && band.y < ticket.y);
      check('터치 영역: 공연장 칩 44px 이상', (await page.locator('.chip').first().boundingBox()).height >= 44);
      check('터치 영역: 비 체크 44px 이상', (await page.locator('label.check').boundingBox()).height >= 44);
      await page.context().close();
    }
    {
      const page = await open(browser, devices['iPhone 13'], '[{"parking_sum":1961}]', '#home', false, new Date('2026-11-23T19:50:00+09:00'));
      await page.goto(page.url().replace('#home', '#exit'));
      await page.waitForSelector('#s-exit:not([hidden])');
      await page.waitForSelector('#exit-live:not([hidden])', { timeout: 10000 }).catch(() => {});
      check('타이머: 화면이 꺼지면 소리가 안 날 수 있다고 안내', (await text(page, '#s-exit')).includes('화면이 꺼지면'));
      check('실시간: 출처와 장기 주차 유의사항', (await text(page, '#s-exit')).includes('장기 주차'));
      await page.context().close();
    }
    // ── 오늘 예보 (실시간 보정) ──
    {
      // 토 14:10, 지금 1,800대 → 2025년 공연 날 이 시각(약 2,160대)보다 적음 → 18시 공연이어도 17:00 전 도착이면 차 가능
      const page = await open(browser, devices['iPhone 13'], '[{"parking_sum":1800}]', '#home', false, new Date('2026-11-28T14:10:00+09:00'));
      await page.click('button[data-date="2026-11-28"]');
      await page.click('button[data-start="18"]');
      await page.waitForSelector('#today:not([hidden])', { timeout: 10000 }).catch(() => {});
      const t = await page.locator('#today').innerText().catch(() => '');
      check('오늘 예보: 줄 표시', await page.locator('#today').isVisible(), t);
      check('오늘 예보: 평소보다 적다는 % 표시', /\d+% 적어요/.test(t), t);
      check('오늘 예보: 오늘 기준 권장 도착 17:00', t.includes('17:00'), t);
      check('오늘 예보: 페이지 오류 없음', page.errors.length === 0, page.errors.join(' | '));
      await page.context().close();
    }
    {
      // 오전에는 예보를 내지 않음 (13시 전)
      const page = await open(browser, devices['iPhone 13'], '[{"parking_sum":1800}]', '#home', false, new Date('2026-11-28T11:00:00+09:00'));
      await page.click('button[data-date="2026-11-28"]');
      await page.waitForTimeout(1500);
      check('오늘 예보: 13시 전엔 숨김', await page.locator('#today').isHidden());
      await page.context().close();
    }
    // ── 막대 눌러 그 시각에 도착하면? ──
    {
      const page = await open(browser, devices['iPhone 13']);
      await page.click('button[data-date="2026-11-28"]');
      await page.click('button[data-start="18"]');
      check('막대: 시각마다 누를 수 있는 버튼', (await page.locator('#bar-hits button').count()) === 14);
      await page.click('#bar-hits button[data-hour="16"]');
      const t = await text(page, '#bar-detail');
      check('막대: 16시 도착 → 2.0배·매우 붐빔', t.includes('16:00') && t.includes('2.0배') && t.includes('매우 붐빔'), t);
      check('막대: 권장보다 1시간 늦음', t.includes('1시간 늦'), t);
      check('막대: 주차비 15,600원', t.includes('15,600원'), t);
      check('막대: 고른 막대 표시', (await page.locator('#bar-hits button[data-hour="16"]').getAttribute('aria-pressed')) === 'true');
      const mark = (m) => page.evaluate(m => { const e = document.querySelector('#bars [data-mark="' + m + '"]'); return e ? e.getAttribute('data-hour') : null; }, m);
      check('그래프: 도착 표시가 16시로 옮겨 감', (await mark('arrive')) === '16', await mark('arrive'));
      check('그래프: 원래 추천(15시)은 따로 표시', (await mark('recommend')) === '15', await mark('recommend'));
      check('그래프: 시작 표시는 18시 그대로', (await mark('start')) === '18');
      check('안내표: 꼬리표가 고른 도착 16:00', (await text(page, '#stub')).includes('16:00'));
      check('안내표: 답이 고른 시각 기준(매우 붐벼요)', (await text(page, '#answer-title')).includes('매우 붐벼요'));
      check('안내표: 주차비 15,600원', (await text(page, '#fee')).includes('15,600원'));
      check('안내표: 추천으로 돌아가기 버튼', await page.locator('#ticket-reset').isVisible());
      await page.click('#ticket-reset');
      check('안내표: 돌아가면 다시 지하철 권장', (await text(page, '#answer-title')).includes('지하철') && await page.locator('#ticket-reset').isHidden());
      check('그래프: 돌아가면 도착 표시가 15시로, 추천 표시 없음', (await mark('arrive')) === '15' && (await mark('recommend')) === null);
      check('안내표: 돌아가면 막대 선택도 해제', (await page.locator('#bar-hits button[data-hour="16"]').getAttribute('aria-pressed')) === 'false');
      check('막대: 가로 스크롤 없음', await noSideScroll(page));
      check('막대: 페이지 오류 없음', page.errors.length === 0, page.errors.join(' | '));
      await page.context().close();
    }
    // ── 평가 보완 ──
    {
      const page = await open(browser, devices['iPhone 13']);
      await page.click('button[data-date="2026-11-28"]');
      await page.click('button[data-start="18"]');
      const basis = await page.evaluate(() => document.getElementById('basis').textContent);
      check('근거: 판단 기준(2배·2시간)과 표본(공연 날 일수)', basis.includes('2배') && basis.includes('2시간') && basis.includes('120일'), basis.slice(0, 120));
      check('근거: 비 보정 표본(비 온 168시간)', basis.includes('168시간'), basis.slice(0, 200));
      check('지하철 답이면 역 길찾기', (await text(page, '#maplinks')).includes('역'));
      await page.click('#rain');
      const sub = await text(page, '#answer-sub');
      check('비 체크로 답이 바뀌면 경계선이라고 알림', sub.includes('맑은 날') && sub.includes('15:00'), sub);
      await page.click('#rain');
      await page.click('button[data-start="16"]');
      check('차 답이면 주차장 길찾기와 주차 안내', (await page.locator('#maplinks').isVisible()) && (await text(page, '#maplinks')).includes('주차장'));
      check('구역별 시야 이름', (await text(page, '#to-seat')).includes('구역별 시야'));
      await page.goto(page.url().replace('#home', '#exit'));
      await page.waitForSelector('#s-exit:not([hidden])');
      check('나가기: 출차 흐름이지 대기시간이 아님을 밝힘', (await text(page, '#s-exit')).includes('빠져나오는 데 걸리는 시간'));
      check('평가 보완: 페이지 오류 없음', page.errors.length === 0, page.errors.join(' | '));
      await page.context().close();
    }
    // ── 앱처럼 설치 (PWA): 설치 정보·아이콘, 한 번 연 뒤 인터넷 없이 열기, 설치 안내 ──
    {
      const page = await open(browser, { ...devices['iPhone 13'], serviceWorkers: 'allow' });
      const base = `http://localhost:${PORT}/`;
      const mHref = await page.locator('link[rel="manifest"]').getAttribute('href', { timeout: 2000 }).catch(() => null);
      const man = mHref ? await (await page.request.get(base + mHref)).json() : {};
      check('설치: 이름·홈 화면 시작·단독 화면', man.short_name === '덜붐빌때' && man.display === 'standalone' && /#home/.test(man.start_url || ''), JSON.stringify(man).slice(0, 160));
      const sizes = (man.icons || []).map(i => i.sizes + (i.purpose ? ':' + i.purpose : ''));
      check('설치: 아이콘 192·512·마스크', sizes.includes('192x192') && sizes.includes('512x512') && sizes.some(x => x.includes('maskable')), sizes.join(','));
      let iconsOk = true;
      for (const i of man.icons || []) { const r = await page.request.get(base + i.src); iconsOk = iconsOk && r.ok() && r.headers()['content-type'].includes('png'); }
      const apple = await page.locator('link[rel="apple-touch-icon"]').getAttribute('href', { timeout: 2000 }).catch(() => null);
      iconsOk = iconsOk && !!apple && (await page.request.get(base + apple)).ok();
      check('설치: 아이콘 파일이 모두 열림 (아이폰 아이콘 포함)', iconsOk);
      check('설치: 테마 색', !!(await page.locator('meta[name="theme-color"]').first().getAttribute('content', { timeout: 2000 }).catch(() => null)));
      await page.evaluate(() => navigator.serviceWorker.ready);
      await page.reload(); await page.waitForSelector('#answer-title:not(:empty)');
      check('설치: 서비스 워커가 화면을 맡음', await page.evaluate(() => !!navigator.serviceWorker.controller));
      check('설치: 연결돼 있으면 오프라인 알림 숨김', await page.locator('#offline').isHidden());
      await page.context().setOffline(true);
      await page.reload(); await page.waitForSelector('#answer-title:not(:empty)', { timeout: 15000 });
      check('설치: 인터넷 없이도 답이 나옴', (await text(page, '#answer-title')).length > 2);
      check('설치: 인터넷 없음 알림', (await page.locator('#offline').isVisible()) && (await text(page, '#offline')).includes('인터넷'));
      await page.context().setOffline(false);
      await page.evaluate(() => dispatchEvent(new Event('online')));
      check('설치: 다시 연결되면 알림 숨김', await page.locator('#offline').isHidden());
      check('설치: 더 보기에 홈 화면에 두기', await page.locator('#to-install').isVisible());
      await page.click('#to-install');
      check('설치: 누르면 홈 화면 추가 방법 안내', (await page.locator('#help').evaluate(d => d.open)) && (await text(page, '#install-sec')).includes('홈 화면에 추가'));
      check('설치: 페이지 오류 없음', page.errors.length === 0, page.errors.join(' | '));
      await page.context().close();
    }
    // (다음 작업의 확인은 이 줄 위에 이어 붙인다)
  } finally {
    await browser.close();
    server.kill();
  }
  console.log(fails.length ? `\n${fails.length}개 실패` : '\nOK');
  process.exit(fails.length ? 1 : 0);
})();
