// 덜붐빌때 화면 스모크 테스트 — 실행: node tests/web/smoke.js
// web/app 을 임시 폴더에 펼쳐(문자셋 머리말 추가) 로컬 서버로 띄우고, 컴퓨터·휴대폰·다크·저장소 차단 환경에서 확인한다.
// 실시간 주차 API는 가짜 응답으로 바꿔 끼운다(실제 기관 서버를 부르지 않음).
const { chromium, devices } = require('playwright');
const fs = require('fs'), os = require('os'), path = require('path'), { spawn } = require('child_process');

const APP = path.resolve(__dirname, '../../web/app');
const PORT = 8790;
const NOW = new Date('2026-11-23T10:00:00+09:00');   // 테스트 기준 "오늘"
const fails = [];
const check = (name, ok, extra = '') => { if (!ok) fails.push(name + (extra ? ' — ' + extra : '')); console.log((ok ? 'ok   ' : 'FAIL ') + name); };

function serveDir() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'dbt-'));
  for (const d of ['data', 'js', 'models', 'img', 'draco']) if (fs.existsSync(path.join(APP, d))) fs.symlinkSync(path.join(APP, d), path.join(dir, d));
  fs.writeFileSync(path.join(dir, 'index.html'),
    '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">' +
    '<style>[hidden]{display:none!important}body{margin:0}</style></head><body>' + fs.readFileSync(path.join(APP, 'index.html'), 'utf8'));
  return dir;
}

async function open(browser, opts, live = 'abort', hash = '#home', blockStorage = false) {
  const ctx = await browser.newContext({ timezoneId: 'Asia/Seoul', ...opts });
  if (blockStorage) await ctx.addInitScript(() => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } }); });
  const page = await ctx.newPage();
  await page.clock.setFixedTime(NOW);
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
      await page.click('button[data-start="16"]');
      check(`${name}: 주말 16시 → 차`, (await text(page, '#answer-title')).includes('차'));
      check(`${name}: 가로 스크롤 없음`, await noSideScroll(page));
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
    // (다음 작업의 확인은 이 줄 위에 이어 붙인다)
  } finally {
    await browser.close();
    server.kill();
  }
  console.log(fails.length ? `\n${fails.length}개 실패` : '\nOK');
  process.exit(fails.length ? 1 : 0);
})();
