// 아이콘 SVG 원본 → 크기별 PNG (브라우저로 그려 글자 가장자리가 깨끗하다). 먼저 python tools/icon_svg.py
// 실행: node tools/export_icons.js
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const DIR = path.resolve(__dirname, '../web/app/icons');
const JOBS = [   // [원본, 결과, 크기, 투명 바탕 유지]
  ['icon.svg', 'icon-192.png', 192, true],
  ['icon.svg', 'icon-512.png', 512, true],
  ['icon-full.svg', 'icon-maskable-512.png', 512, false],   // 안드로이드가 원·둥근 사각형으로 자른다
  ['icon-full.svg', 'apple-touch-icon.png', 180, false],    // 아이폰이 자기 모서리로 자른다 (투명하면 검게 나옴)
  ['favicon.svg', 'favicon-32.png', 32, true],
];
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ deviceScaleFactor: 1 });
  for (const [src, out, size, transparent] of JOBS) {
    const svg = fs.readFileSync(path.join(DIR, src), 'utf8');
    await p.setViewportSize({ width: size, height: size });
    await p.setContent(`<html><body style="margin:0;background:transparent"><img src="data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}" width="${size}" height="${size}" style="display:block"></body></html>`);
    await p.waitForFunction(() => document.images[0].complete);
    await p.screenshot({ path: path.join(DIR, out), omitBackground: transparent });
    console.log(out, size);
  }
  await b.close();
})();
