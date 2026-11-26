// 기획서(docx) 만들기 — 공식 양식(붙임1) 항목 순서 그대로. 숫자는 facts.json(분석 결과 파일에서 뽑은 값)에서만 가져온다.
// 실행: python tools/proposal_facts.py && node docs/기획서/build_docx.js
// 출력: docs/기획서/덜붐빌때_기획서.docx
const fs = require('fs'), path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  AlignmentType, HeadingLevel, ImageRun, PageBreak, LevelFormat, Footer, PageNumber, ExternalHyperlink, VerticalAlign,
} = require('docx');

const DIR = __dirname;
const F = JSON.parse(fs.readFileSync(path.join(DIR, 'facts.json'), 'utf8'));
const v = k => { if (!(k in F)) throw new Error('facts.json 에 없음: ' + k); return F[k].value; };
const n = x => Number(x).toLocaleString('ko-KR');
const pct = x => Math.round(x * 100) + '%';
const URL_SITE = 'https://tak7257-dot.github.io/Kspo-report/';
const URL_REPO = 'https://github.com/tak7257-dot/Kspo-report';
const ZONE = F['전체구역'] ? F['전체구역'].value : null;   // 입출차정보(전체구역) 분석 결과 (받는 중이면 없음)

// ── 모양 ──
const FONT = '맑은 고딕';
const BRAND = '00A86B', INK = '191F28', SUB = '4E5968', LINE = 'D9DEE3', FILL = 'EEF7F2', TODO = 'FFF1A8';
const PAGE_W = 11906, MARGIN = 1134, CONTENT_W = PAGE_W - MARGIN * 2;   // A4, 여백 2cm

// 글 조각: 문자열, 또는 {t, b(굵게), c(색), todo(채울 칸)}
const run = s => typeof s === 'string' ? new TextRun({ text: s, font: FONT })
  : s.todo ? new TextRun({ text: `[채움: ${s.todo}]`, font: FONT, bold: true, shading: { type: ShadingType.CLEAR, fill: TODO, color: 'auto' } })
  : s.link ? new ExternalHyperlink({ link: s.link, children: [new TextRun({ text: s.t, font: FONT, color: '00764B', underline: {} })] })
  : new TextRun({ text: s.t, font: FONT, bold: !!s.b, color: s.c, size: s.size });
const P = (parts, o = {}) => new Paragraph({ children: [].concat(parts).map(run), spacing: { after: 80, line: 300 }, ...o });
const B = (parts, level = 0) => new Paragraph({ children: [].concat(parts).map(run), numbering: { reference: 'dot', level }, spacing: { after: 40, line: 290 } });
const H1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t, font: FONT })] });
const H2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t, font: FONT })] });
const note = t => P([{ t, c: SUB, size: 18 }], { spacing: { after: 120 } });

const border = { style: BorderStyle.SINGLE, size: 4, color: LINE };
const borders = { top: border, bottom: border, left: border, right: border };
function table(widths, rows, { head = true, size = 19 } = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: rows.map((r, i) => new TableRow({
      tableHeader: head && i === 0,
      children: r.map((cell, ci) => new TableCell({
        width: { size: widths[ci], type: WidthType.DXA }, borders,
        shading: head && i === 0 ? { type: ShadingType.CLEAR, fill: FILL, color: 'auto' } : undefined,
        margins: { top: 50, bottom: 50, left: 90, right: 90 }, verticalAlign: VerticalAlign.CENTER,
        children: [].concat(cell).map(c => new Paragraph({
          children: [].concat(c).map(x => typeof x === 'string'
            ? new TextRun({ text: x, font: FONT, size, bold: head && i === 0 })
            : x.todo ? run(x) : new TextRun({ text: x.t, font: FONT, size, bold: x.b || (head && i === 0), color: x.c })),
          spacing: { after: 0, line: 260 },
        })),
      })),
    })),
  });
}
const img = (file, w, h) => new ImageRun({ type: 'png', data: fs.readFileSync(path.join(DIR, 'img', file)), transformation: { width: w, height: h } });
function imageRow(items) {   // [파일, 설명] 여러 개를 테두리 없는 표로 나란히
  const w = Math.floor(CONTENT_W / items.length), none = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
  return new Table({
    width: { size: w * items.length, type: WidthType.DXA }, columnWidths: items.map(() => w),
    rows: [new TableRow({ children: items.map(([file, cap, pw, ph]) => new TableCell({
      width: { size: w, type: WidthType.DXA }, borders: { top: none, bottom: none, left: none, right: none },
      children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [img(file, pw, ph)] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 40 }, children: [new TextRun({ text: cap, font: FONT, size: 17, color: SUB })] })],
    })) })],
  });
}

// ── 숫자 ──
const nc = v('예보검증');
const row = (k, now, target) => nc[k].find(r => r.now === now && r.target === target);
const wk15 = row('weekend', 15, 18), wd17 = row('weekday', 17, 20), wk12 = row('weekend', 12, 18);
const showMin = v('공연시간_중앙값');

// ── 기획 요약서 (1장) ──
const summary = [
  P([{ t: '2026년도 공공데이터 활용 경진대회 기획서', c: SUB, size: 20 }], { spacing: { after: 40 } }),
  new Paragraph({ children: [new TextRun({ text: '덜붐빌때', font: FONT, bold: true, size: 44, color: BRAND })], spacing: { after: 20 } }),
  P([{ t: '"차를 가져갈까?"부터 답하는 올림픽공원 공연 날 주차 비서', b: true, size: 24 }], { spacing: { after: 60 } }),
  P([{ t: '참가자: ' }, { todo: '개인/팀명 (11/28 결정 후)' }], { spacing: { after: 160 } }),
  H1('기획 요약서'),
  H2('1. 활용사례명'),
  P('덜붐빌때 — 공연 날 올림픽공원에 차를 가져갈지, 몇 시까지 들어와야 하는지, 끝나고 언제 나가면 덜 막히는지를 알려 주는 휴대폰 웹 서비스'),
  H2('2. 사용한 공공데이터명 (모두 한국체육산업개발주식회사, 공공데이터포털)'),
  table([3700, 5938], [
    ['데이터', '쓰임'],
    ['올림픽공원 차량입출차, 공연, 날씨정보 등 연계 데이터 (2025)', '공연 날 시간대별 주차장 혼잡 — 답의 핵심'],
    ['올림픽공원 실시간 주차현황 (2026-09 개방)', '"지금 주차장 N대"와 공연 당일 오늘 예보 보정'],
    ['올림픽공원 입출차 정보 (2024-07)', '공연이 끝난 뒤 출차가 줄어드는 모양'],
    [[ZONE ? '올림픽공원 입출차정보(전체구역) (2025)' : '올림픽공원 입출차정보(전체구역) (2025)'], [ZONE ? '문별 흐름·만차 추정' : { todo: '전체구역 분석 결과(문별 흐름·만차 추정)' }]],
    ['올림픽공원 공연정보 (공연행사정보 API)', '공연 길이(끝나는 시각 추정)'],
    ['올림픽공원 공연장 실감형 콘텐츠', '공연장 3D, KSPO DOME 구역별 시야'],
    ['자주 묻는 질문정보', '주차 면수·요금·매표소·입차 가능 시간'],
  ], { size: 18 }),
  H2('3. 요약'),
  P(`공연을 고르면 2025년 공연 날 ${v('화면_공연일수')}일의 주차 기록으로 "차로 와도 된다 / 지하철이 낫다"와 권장 도착 시각을 답한다. 공연 당일에는 실시간 주차현황으로 남은 시간을 다시 예보하고, 공연이 끝날 무렵에는 "20분 쉬었다 나가면 같이 나가는 차가 ${v('출차_20분')}%로 준다"는 나가기 안내와 타이머를 띄운다. 처음 오는 사람은 공연장 3D로 하루를 미리 본다. 모든 답에 근거(자료·기준·표본)와 모르는 것을 함께 밝힌다.`),
  H2('4. 기대효과'),
  B([{ t: '관람객: ', b: true }, '도착·출차 시각을 스스로 나눠 공연 날 저녁 주차장 정체와 대기 시간이 준다. 붐비는 날은 대중교통으로 바꾸도록 돕는다.']),
  B([{ t: '기관: ', b: true }, '공연 날 시간대별 혼잡과 출차 몰림을 숫자로 보여 주어 안내 인력·주차 운영 계획의 근거가 된다. 정적 웹이라 운영비가 들지 않는다.']),
  B([{ t: '공공데이터: ', b: true }, '새로 열린 실시간 주차현황 API를 과거 연계 데이터와 묶어 "오늘 예보"로 쓰는 활용 사례. 부족한 데이터는 추가 개방 요청으로 정리했다.']),
  new Paragraph({ children: [new PageBreak()] }),
];

// ── 상세 기획서 ──
const detail = [
  H1('상세 기획서'),
  H2('1. 활용사례 개요'),
  P([{ t: '1-1. 활용사례 명  ', b: true }, '덜붐빌때 — "차를 가져갈까?"부터 답하는 올림픽공원 공연 날 주차 비서']),
  P([{ t: '1-2. 활용사례 기능, 특징 등 세부내용', b: true }]),
  table([2300, 4300, 3038], [
    ['기능', '관람객이 얻는 것', '쓰는 공공데이터'],
    ['답 카드 (첫 화면)', '공연장·날짜·시작 시각을 고르면 차/지하철 추천, 권장 도착 시각, 예상 주차비, 길찾기', '연계 데이터, 자주 묻는 질문정보'],
    ['시간대 막대', '공연 날 시간대별 혼잡(평소 대비 배수). 막대를 누르면 "그 시각에 도착하면?"으로 답이 바뀜', '연계 데이터'],
    ['오늘 예보', '공연 당일 13시부터 실시간 주차 대수로 남은 4시간을 다시 예보', '실시간 주차현황 + 연계 데이터'],
    ['나가기 안내', '공연 끝날 무렵 첫 화면에 뜸. 10·20·30분 뒤 출차 비율, 20분 타이머(화면 켜짐 유지·진동·소리)', '입출차 정보, 공연정보'],
    ['공연 날 하루 미리 보기', '도착 → 공연 → 끝 → 출차 단계별 공연장 3D. KSPO DOME은 구역별 시야 8곳', '실감형 콘텐츠'],
    ['일정표·캘린더·공유', '하루 일정을 캘린더(.ics, 30분 전 알림)로 저장, 같이 갈 사람에게 보낼 문구', '—'],
    ['이 답의 근거', '판단 기준·자료·표본·가정·모르는 것을 펼쳐 볼 수 있음. 비 체크로 답이 바뀌면 "경계선"이라고 알림', '—'],
    ['홈 화면에 두기', '앱처럼 설치. 한 번 연 화면은 공연장 안처럼 전파가 약해도 열림(실시간 숫자는 제외)', '—'],
  ], { size: 18 }),
  P('', { spacing: { after: 60 } }),
  imageRow([['1_답카드.png', '답 카드', 118, 256], ['2_시간대.png', '시간대 막대', 150, 137], ['3_나가기.png', '나가기 안내', 118, 256], ['4_시야.png', '구역별 시야(3D)', 118, 256]]),
  P([{ t: '1-3. 활용사례 서비스 확인 방법', b: true }], { spacing: { before: 160, after: 80 } }),
  new Paragraph({ spacing: { after: 60 }, children: [img('qr_서비스.png', 84, 84), new TextRun({ text: '   휴대폰 카메라로 찍으면 바로 열려요', font: FONT, size: 18, color: SUB })] }),
  B([{ t: '웹 주소: ', b: true }, { t: URL_SITE, link: URL_SITE }, ' — 휴대폰·컴퓨터 브라우저에서 바로 열림(설치·로그인 없음). 휴대폰에서는 공유 → "홈 화면에 추가"로 앱처럼 쓸 수 있음.']),
  B([{ t: '소스 코드: ', b: true }, { t: URL_REPO, link: URL_REPO }, ' — 분석 파이프라인(python run_all.py), 화면, 테스트, 자동 배포 설정이 모두 공개되어 있어 그대로 재현할 수 있음.']),

  H2('2. 활용사례의 독창성'),
  P([{ t: '2-1. 활용 공공데이터', b: true }]),
  table([3000, 1000, 1700, 2238, 1700], [
    ['데이터 (공공데이터포털 번호)', '형태', '규모', '가공', '이용허락범위'],
    ['차량입출차, 공연, 날씨정보 등 연계 데이터 (15164822)', 'API', `${n(v('m25_시간대수'))}개 시간대 (${v('m25_기간')})`, `결함일 ${v('결함일수')}일 제외, 같은 달 비교`, '제한 없음'],
    ['실시간 주차현황 (15168686)', 'API', `웹이 직접 호출, ${v('실시간기록_시작')}부터 기록 누적`, '공연 날 같은 시각 대비 편차', '제한 없음'],
    ['입출차 정보 (15138735)', 'CSV', `${n(v('입출차2024_건수'))}건 (2024-07)`, '10분 단위 출차 대수', '제한 없음'],
    ['입출차정보(전체구역) (15159093)', 'API', ZONE ? `${n(ZONE.대수)}건 (2025)` : '2,411,225건 (2025)', ZONE ? '문별 입출차·동시 주차' : { todo: '분석 후' }, '제한 없음'],
    ['공연정보 (3037877)', 'API', `${n(v('공연정보_건수'))}건`, `공연 시간 ${n(v('공연시간_표본'))}건 → 중앙값`, '공공누리 제1유형'],
    ['공연장 실감형 콘텐츠 (15127487)', 'GLB/DAE', `공연장 ${v('3D_공연장수')}곳`, '웹용 경량화(Draco)', '제한 없음'],
    ['자주 묻는 질문정보 (15089962)', 'CSV', '주차·이용 문답', '면수·요금 등 사실만 추출', '제한 없음'],
  ], { size: 17 }),
  note('출처: 한국체육산업개발주식회사, 공공데이터포털(www.data.go.kr). 홈페이지 공연 일정처럼 공공누리 표시가 없는 자료는 쓰지 않고 링크로만 연결했다.'),

  P([{ t: '2-2. 사례를 활용하게 된 배경 및 활용 우수성', b: true }]),
  P([{ t: '배경. ', b: true }, `올림픽공원은 KSPO DOME을 비롯한 여러 공연장이 주차장(약 ${n(v('FAQ_capacity'))}대 규모)을 함께 쓴다. 관람객은 "차를 가져가도 될까?", "몇 시까지 가야 하나?", "끝나고 언제 빼야 덜 막히나?"를 매번 감으로 정한다. 기관 데이터를 분석해 보니 공연의 영향은 하루 전체가 아니라 저녁 몇 시간에 몰린다.`]),
  table([4800, 4838], [
    ['2025년 연계 데이터에서 찾은 사실', '서비스에 쓴 방식'],
    [`주말·휴일 공연 날 ${v('주말_저녁최고시')}시 주차장이 평소의 ${v('주말_저녁최고배')}배, 평일 공연 날 ${v('평일_저녁최고시')}시 ${v('평일_저녁최고배')}배`, '평소의 2배를 "매우 붐빔"으로 보고 권장 도착 시각을 정함'],
    [`하루 최대 주차대수는 주말·휴일 공연 날 +${v('피크증가_주말')}%, 평일 공연 날 +${v('피크증가_평일')}%`, '하루 총량이 아닌 시간대별 비교로 안내'],
    [`관객 수와 혼잡의 상관 ${v('관객_피크_상관')}(약함)`, '관객 수 대신 요일 유형·시작 시각으로 판단'],
    [`비 온 ${v('비_시간수')}시간은 평균 ${v('비_보정률')}% 적음`, '비 체크 시 보정, 답이 바뀌면 경계선 알림'],
    [`공연이 끝나고 출차가 가장 몰린 10분 대비 20분 뒤 ${v('출차_20분')}% (2024-07, 저녁 ${v('출차_저녁수')}일)`, '"20분 쉬었다 나가기" 안내와 타이머'],
  ], { size: 18 }),
  P([{ t: '활용 우수성. ', b: true }, `데이터의 결함을 먼저 찾아 고쳤다. 기록이 20시간 미만이거나 낮에도 새벽 수준인 ${v('결함일수')}일을 제외했고, 7→8월 사이 하루 피크가 ${v('8월_급변')}로 급변한 구간은 집계 범위가 바뀐 것으로 보고 모든 비교를 "같은 달·같은 요일 유형·같은 시각의 공연 없는 날"과 했다.`], { spacing: { before: 100, after: 80 } }),
  P([{ t: '다른 서비스와의 차별점', b: true }]),
  B([{ t: '질문으로 시작한다. ', b: true }, '혼잡 지도를 보여 주고 해석을 맡기는 대신 "차를 가져갈까?"에 먼저 답하고, 이유는 펼쳐 보게 했다.']),
  B([{ t: '과거 + 실시간을 묶은 오늘 예보. ', b: true }, `새로 열린 실시간 주차현황을 2025년 공연 날 같은 시각과 견줘 남은 시간을 다시 예보한다. 2025년 공연 날로 되짚어 보니 주말 15시에 18시를 예보할 때 오차가 ${pct(wk15.err_past)}에서 ${pct(wk15.err_corrected)}로, 평일 17시에 20시를 예보할 때 ${pct(wd17.err_past)}에서 ${pct(wd17.err_corrected)}로 줄었다.`]),
  B([{ t: '끝나고 나가는 순간까지. ', b: true }, '대부분의 안내는 도착에서 끝나지만, 이 서비스는 공연 종료 무렵 첫 화면을 나가기 안내로 바꾼다.']),
  B([{ t: '실감형 콘텐츠의 생활 활용. ', b: true }, `공연장 3D를 "공연 날 하루"의 단계별 장면과 KSPO DOME 구역별 시야(${v('시야_시점수')}곳)로 써서 처음 오는 관람객의 불안을 줄인다.`]),
  B([{ t: '정직한 답. ', b: true }, '모든 답에 자료·표본·가정과 "모르는 것"을 함께 적는다. 홈페이지 자료 없이 공공데이터만 쓴다.']),

  H2('3. 활용사례의 구체성'),
  P([{ t: '답을 정하는 방법', b: true }]),
  B(`시간대별 혼잡 = 2025년 공연 날의 주차대수 ÷ 같은 달·같은 요일 유형·같은 시각의 공연 없는 날 (평소 = 1). ${v('붐빔_기준')}배 이상 "붐빔", ${v('매우붐빔_기준')}배 이상 "매우 붐빔".`),
  B(`권장 도착 = 시작 1시간 전(자주 묻는 질문정보의 권장 여유 ${v('FAQ_spare_minutes')}분)부터 거꾸로 보며 평소의 2배 아래인 가장 늦은 시각. 그 시각이 시작보다 2시간 넘게 이르면 지하철을 권하고 지도 앱 길찾기로 연결한다.`),
  B(`예상 주차비 = 권장 도착부터 공연 종료 후 출차까지, 10분당 ${n(v('FAQ_fee_per_10min'))}원(경차·장애인 등 ${v('FAQ_discount_pct')}% 할인 안내). 공연 길이는 공연정보 ${n(v('공연시간_표본'))}건의 중앙값 ${showMin.join('·')}분.`),
  B(`오늘 예보 = 지금 주차 대수 ÷ 2025년 공연 날 같은 시각 중앙값으로 편차를 구해 최대 4시간 뒤까지 곱한다. 12시에 적용하면 오차가 오히려 커져(주말 ${pct(wk12.err_past)} → ${pct(wk12.err_corrected)}) 13시부터만 쓴다.`),
  B(`나가기 = 출차가 가장 몰린 10분을 100%로 10분 뒤 ${v('출차_10분')}%, 20분 뒤 ${v('출차_20분')}%, 30분 뒤 ${v('출차_30분')}%. 출차 기록 범위에 맞춰 20~23시에 끝나는 공연에만 비율을 보여 준다.`),
  P([{ t: '되짚어 본 예보 정확도 (2025년 공연 날, 오차 중앙값)', b: true }], { spacing: { before: 100, after: 60 } }),
  table([2400, 1800, 1800, 1800, 1838], [
    ['예보 (지금 → 맞힐 시각)', '표본', '과거 평균만', '실시간 보정', '변화'],
    ...[['weekend', 13, 17], ['weekend', 15, 18], ['weekend', 17, 20], ['weekday', 13, 17], ['weekday', 15, 18], ['weekday', 17, 20]].map(([k, a, t]) => {
      const r = row(k, a, t);
      return [`${k === 'weekend' ? '주말·휴일' : '평일'} ${a}시 → ${t}시`, `${r.days}일`, pct(r.err_past), pct(r.err_corrected), `${Math.round((r.err_corrected - r.err_past) * 100)}%p`];
    }),
  ], { size: 18 }),
  P([{ t: '빈틈을 막은 부분', b: true }], { spacing: { before: 100, after: 60 } }),
  B('자정을 넘겨 끝나는 공연은 나가기 안내가 끝날 때까지 날짜를 유지, 공휴일은 2028년까지 반영(요일 유형 판단).'),
  B('비 체크 하나로 답이 바뀌면 "맑은 날 기준으로는 …, 경계선을 넘은 것"이라고 함께 알림.'),
  B('출차 비율은 "10분 동안 빠져나간 차의 수"이지 출구 대기 시간이 아님을 화면에 명시.'),
  B('실시간 숫자는 저장본을 쓰지 않음(지난 숫자를 지금처럼 보여 주지 않음). 실패하면 줄을 숨김.'),
  B(`품질: 판단 로직 테스트 ${v('계산테스트_수')}개, 분석 파이프라인 테스트, 휴대폰·컴퓨터·다크 모드·저장소 차단·오프라인 화면 점검을 자동으로 돌린다. 터치 영역 44px 이상.`),
  ...(ZONE ? [] : [P([{ todo: '입출차정보(전체구역) 분석: 공연 날 시각별 동시 주차 대수(전체 면수 대비), 문별 입차·출차 비중, 머문 시간 → 위 표와 나가기 비율 갱신' }], { spacing: { before: 80 } })]),

  H2('4. 사례의 활용 적절성 (사회적 가치)'),
  B([{ t: '혼잡 분산: ', b: true }, `공연 날 저녁 주차장이 평소의 ${v('주말_저녁최고배')}배까지 오르는 시간에 도착이 몰린다. 권장 도착 시각과 "20분 쉬었다 나가기"는 같은 수의 차를 시간에 나눠 진입·출차 정체를 줄인다.`]),
  B([{ t: '대중교통 전환: ', b: true }, '시작 2시간 전보다 일찍 와야 하는 날은 지하철을 먼저 권해 공원 주변 교통과 탄소 배출을 줄인다.']),
  B([{ t: '처음 오는 관람객의 불안 해소: ', b: true }, '공연장 3D와 하루 단계별 안내로 길·주차·시야를 미리 본다.']),
  B([{ t: '기관 운영 근거: ', b: true }, '같은 분석으로 운영자용 리포트(공개 저장소 output/report.html)도 만들어, 공연 날 시간대별 혼잡과 출차 몰림을 안내 인력 배치와 주차 운영에 쓸 수 있다.']),
  B([{ t: '공공데이터 신뢰: ', b: true }, '근거와 한계를 함께 보여 주는 방식으로, 공공데이터 기반 안내가 "왜 이런 답인지" 설명할 수 있음을 보인다.']),
  ...(ZONE ? [] : [P([{ todo: '전체구역 분석으로 "끝나고 20분 늦게 나가는 차가 늘면 출차 최대치가 얼마나 줄어드는지" 계산해 넣기' }])]),

  H2('5. 실현가능성 및 기타'),
  P([{ t: '추진 일정 및 개발·운영 계획', b: true }]),
  table([1700, 7938], [
    ['시기', '내용'],
    ['11/17', '공공데이터 수집·정리·분석 파이프라인, 운영자 리포트'],
    ['11/18~20', '공연장 3D 변환(실감형 콘텐츠 → 웹용), 서비스명 확정'],
    ['11/23', '"차를 가져갈까?" 답 카드 중심으로 개편, 공공데이터만 쓰도록 정리'],
    ['11/25', '실시간 주차·오늘 예보, 주차비, 근거 공개, 평가 보완'],
    ['11/26', '홈 화면에 두기(오프라인), 입출차정보(전체구역) 수집'],
    ['11/27~', '기능 동결, 기획서·점검 → 12/1 제출'],
  ], { size: 18 }),
  B('정적 웹(GitHub Pages) + 자동화(GitHub Actions): main에 올리면 자동 배포되고, 실시간 주차현황은 예약 실행으로 기록을 쌓는다(예약 간격은 GitHub 사정에 따라 불규칙). 서버·DB가 없어 운영비 0원.'),
  B('인증키는 코드와 웹에 넣지 않는다(실시간 주차현황은 기관이 공개한 웹용 키만 사용). 추가 API는 GitHub 비밀값으로만 쓴다.'),
  P([{ t: '서비스 유지 계획 (2028년까지)', b: true }], { spacing: { before: 100, after: 60 } }),
  B('공휴일은 2028년까지 넣어 두었고, 쌓이는 실시간 기록으로 해마다 공연 날 패턴과 오늘 예보 기준을 다시 계산한다(python run_all.py 한 번).'),
  B('수상 시 원천 소스(공개 저장소) 제공과 2028년까지 운영 협조에 동의한다. 기관 서버로 옮길 때도 정적 파일 복사로 끝난다.'),
  P([{ t: '한계 (정직하게 밝힘)', b: true }], { spacing: { before: 100, after: 60 } }),
  B('공연장마다 다른 답을 주지 못한다: 2025년 연계 데이터의 공연과 공연장을 이을 날짜 있는 자료가 없다(대관정보 717건은 날짜 칸이 비어 있고 2022년까지).'),
  B('지하철·버스 혼잡 데이터가 없어 지도 앱 길찾기로 넘긴다.'),
  B(ZONE ? '만차 여부: 입출차정보(전체구역)로 추정(위 3장).' : ['만차 여부: ', { todo: '전체구역 분석 결과 반영' }]),
  P([{ t: '추가 개방이 필요한 공공데이터 (의견)', b: true }], { spacing: { before: 100, after: 60 } }),
  B([{ t: '대관정보에 행사 일자·시작 시각: ', b: true }, '있으면 공연장별 안내와 공연이 겹치는 날 구분이 가능하다.']),
  B([{ t: '주차장 구역별 면수와 구역별 실시간 대수: ', b: true }, '"어느 주차장이 먼저 찬다"를 정확히 안내할 수 있다.']),
  B([{ t: '주차장 혼잡도 정보의 P구역 위치(어느 문 쪽인지): ', b: true }, '지금은 위치를 몰라 문별 안내에 쓰지 못했다.']),
  B([{ t: '출구별 대기 시간(차단기 통과 기록): ', b: true }, '출차 "흐름"이 아니라 "기다리는 시간"을 알려 줄 수 있다.']),
  P([{ t: '도구와 라이선스', b: true }], { spacing: { before: 100, after: 60 } }),
  B('기획·분석·개발 과정에서 AI 코딩 도구(Claude Code)를 보조로 사용했다. 모든 수치는 공개 저장소의 코드로 공공데이터에서 다시 계산할 수 있고, 기획서의 숫자는 분석 결과 파일에서 자동으로 옮겼다(docs/기획서/숫자_출처.md).'),
  B('글꼴: DBT Sans(Pretendard 기반, SIL OFL 1.1), 아이콘 글씨 Jua(SIL OFL 1.1). 라이브러리: model-viewer·Draco(Apache-2.0), pandas 등 자유 라이선스.'),
];

const doc = new Document({
  creator: '덜붐빌때', title: '덜붐빌때 기획서', description: '2026년도 공공데이터 활용 경진대회 기획서',
  styles: {
    default: { document: { run: { font: FONT, size: 21, color: INK } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: 30, bold: true, color: INK }, paragraph: { spacing: { before: 120, after: 120 }, keepNext: true, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: BRAND, space: 4 } } } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: 24, bold: true, color: '00764B' }, paragraph: { spacing: { before: 200, after: 80 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: 'dot', levels: [
    { level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 240 } } } },
    { level: 1, format: LevelFormat.BULLET, text: '–', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 240 } } } },
  ] }] },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: 16838 }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: ['덜붐빌때 · ', PageNumber.CURRENT], font: FONT, size: 16, color: SUB })] })] }) },
    children: [...summary, ...detail],
  }],
});

Packer.toBuffer(doc).then(buf => {
  const out = path.join(DIR, '덜붐빌때_기획서.docx');
  fs.writeFileSync(out, buf);
  console.log('→', out, Math.round(buf.length / 1024) + 'KB', ZONE ? '(전체구역 반영)' : '(전체구역 칸 비워 둠)');
});
