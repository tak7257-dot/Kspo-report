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
  const ctx = await browser.newContext({ timezoneId: 'Asia/Seoul', ...opts });
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
      check(`${name}: 표 번호는 날짜·시각`, (await text(page, '#ticket-no')).includes('1128-1800'));
      await page.click('button[data-start="16"]');
      check(`${name}: 주말 16시 → 차`, (await text(page, '#answer-title')).includes('차'));
      check(`${name}: 가로 스크롤 없음`, await noSideScroll(page));
      check(`${name}: 차 답이면 지도 링크 숨김`, await page.locator('#maplinks').isHidden());
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
    // (다음 작업의 확인은 이 줄 위에 이어 붙인다)
  } finally {
    await browser.close();
    server.kill();
  }
  console.log(fails.length ? `\n${fails.length}개 실패` : '\nOK');
  process.exit(fails.length ? 1 : 0);
})();
