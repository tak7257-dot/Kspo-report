"""4단계: 지표 표를 읽어 차트 + 자동 해설이 들어간 HTML 보고서를 만든다.

입력:  data/clean/m_*.csv, m_kpi.json   (metrics.py 결과)
출력:  output/report.html               (브라우저로 열면 되는 단일 파일)
"""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs_version
from jinja2 import Template

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean"
OUT = ROOT / "output"

# 색: 평일=파랑, 주말=주황 (색약 검사 통과한 조합). 크기 표현(히트맵)은 파랑 한 가지 색의 진하기.
C_WEEKDAY, C_WEEKEND = "#2a78d6", "#eb6834"
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
INK_MUTED, GRID = "#898781", "rgba(137,135,129,0.25)"
FONT = "Pretendard, 'Noto Sans KR', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif"


def base_layout(fig, height=340, **kw):
    fig.update_layout(
        height=height, margin=dict(l=48, r=16, t=16, b=40),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=13, color=INK_MUTED),
        hoverlabel=dict(font=dict(family=FONT)),
        legend=dict(orientation="h", y=1.08, x=0),
        **kw,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, ticks="")
    fig.update_yaxes(gridcolor=GRID, zeroline=False, ticks="")
    return fig


def chart_daily(daily):
    fig = go.Figure()
    for is_weekend, name, color in [(False, "평일", C_WEEKDAY), (True, "주말", C_WEEKEND)]:
        d = daily[daily["주말"] == is_weekend]
        fig.add_bar(x=d["날짜"], y=d["입차대수"], name=name, marker_color=color,
                    customdata=d["요일"],
                    hovertemplate="%{x|%m/%d}(%{customdata}) · %{y:,}대<extra></extra>")
    base_layout(fig, barcornerradius=4, bargap=0.25)
    fig.update_xaxes(tickformat="%m/%d", dtick=7 * 86400000)
    fig.update_yaxes(title_text="입차 대수")
    return fig


def chart_occupancy(occ):
    fig = go.Figure()
    for name, color in [("평일", C_WEEKDAY), ("주말", C_WEEKEND)]:
        d = occ[occ["구분"] == name]
        fig.add_scatter(x=d["시"], y=d["재차대수"], name=name, mode="lines+markers",
                        line=dict(color=color, width=2), marker=dict(size=8, color=color),
                        hovertemplate=name + " %{x}시 · 평균 %{y:,.0f}대<extra></extra>")
        peak = d.loc[d["재차대수"].idxmax()]
        fig.add_annotation(x=peak["시"], y=peak["재차대수"], text=f"{name} 정점 {int(peak['시'])}시",
                           showarrow=False, yshift=16, font=dict(color=INK_MUTED, size=12))
    base_layout(fig, hovermode="x unified")
    fig.update_xaxes(title_text="시각", dtick=2, range=[-0.5, 23.5])
    fig.update_yaxes(title_text="주차장 안 차량 수(평균)")
    return fig


def chart_heatmap(heat):
    fig = go.Figure(go.Heatmap(
        z=heat.values, x=[int(c) for c in heat.columns], y=heat.index,
        colorscale=[[i / (len(BLUE_RAMP) - 1), c] for i, c in enumerate(BLUE_RAMP)],
        xgap=2, ygap=2, colorbar=dict(title="대/일", thickness=10, outlinewidth=0),
        hovertemplate="%{y}요일 %{x}시 · 하루 평균 %{z:.0f}대 입차<extra></extra>",
    ))
    base_layout(fig, height=300)
    fig.update_xaxes(title_text="입차 시각", dtick=2)
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    return fig


# ---------------- 2025 공연·날씨 섹션 ----------------
C_SHOW, C_BASE = "#6250d6", "#898781"   # 공연일=보라, 공연 없는 날=회색 점선(비교 기준)


def chart_show_profile(prof):
    """공연일의 시간대별 지수(같은 달·요일유형·시각의 공연 없는 날 = 100). 평일/주말 두 선."""
    fig = go.Figure()
    fig.add_hline(y=100, line=dict(color=C_BASE, width=2, dash="dash"))
    fig.add_annotation(x=12, y=100, text="공연 없는 날 = 100", showarrow=False, yshift=-14,
                       font=dict(color=INK_MUTED, size=12))
    for name, color in [("평일", C_WEEKDAY), ("주말·휴일", C_WEEKEND)]:
        s = prof[prof["요일유형"] == name]
        if s.empty:
            continue
        fig.add_scatter(x=s["시"], y=s["지수"], name=f"{name} 공연일", mode="lines+markers",
                        line=dict(color=color, width=2), marker=dict(size=8, color=color),
                        hovertemplate=name + " 공연일 %{x}시 · 지수 %{y:.0f}<extra></extra>")
        pk = s.loc[s["지수"].idxmax()]
        fig.add_annotation(x=pk["시"], y=pk["지수"], text=f"{name} {int(pk['지수'])}", showarrow=False,
                           yshift=14, font=dict(color=INK_MUTED, size=12))
    base_layout(fig, height=320, hovermode="x unified")
    fig.update_xaxes(title_text="시각", dtick=2, range=[-0.5, 23.5])
    fig.update_yaxes(title_text="주차 지수 (공연 없는 날 = 100)")
    return fig


def chart_show_scatter(shows):
    s = shows.dropna(subset=["증가율"])
    s = s[s["관람객수"] > 0]
    fig = go.Figure(go.Scatter(
        x=s["관람객수"], y=s["증가율"], mode="markers",
        marker=dict(size=10, color=C_SHOW, line=dict(width=2, color="#fcfcfb")),
        customdata=list(zip(s["날짜"].astype(str).str[:10], s["공연명"].str.slice(0, 40), s["피크주차"])),
        hovertemplate="%{customdata[0]} %{customdata[1]}<br>관람객 %{x:,}명 · 피크 %{customdata[2]:,}대 · 기준 대비 %{y:+.0f}%<extra></extra>",
    ))
    fig.add_hline(y=0, line=dict(color=GRID, width=1))
    base_layout(fig, height=320, showlegend=False)
    fig.update_xaxes(title_text="공연 관람객 수(명)", showgrid=True, gridcolor=GRID)
    fig.update_yaxes(title_text="피크 주차 증가율(%)", ticksuffix="%")
    return fig


def pct(x):
    """+3% / -5% / 0% 형식 (반올림 결과가 0이면 부호 없이)"""
    v = int(round(x))
    return "0%" if v == 0 else f"{v:+d}%"


def findings_2025(k, shows, weather):
    out = [
        f"{k['기간']} 중 공연이 있었던 날은 {k['공연일수']}일입니다(분석 대상 {k['일수']}일).",
    ]
    # 하루 최대 주차 비교: 수치 크기에 따라 문장을 고른다 (데이터가 바뀌어도 말이 맞도록)
    we, wd = k["공연일피크증가율_주말"], k["공연일피크증가율_평일"]
    def size_word(x, end):
        stem = "거의 차이가 없었" if abs(x) < 10 else ("높았" if x > 0 else "낮았")
        return stem + ("습니다" if end else "고")
    out.append(f"하루 최대 주차대수는 같은 달·같은 요일유형의 공연 없는 날과 비교해(중앙값) "
               f"주말·휴일 공연일이 {pct(we)}로 {size_word(we, False)}, 평일 공연일은 {pct(wd)}로 {size_word(wd, True)}.")
    out.append(f"시간대로 보면 공연 영향은 저녁에 집중됩니다. 주말·휴일 공연일은 오후부터 늘어 "
               f"{k['저녁최고시_주말']}시에 평소의 {k['저녁최고지수_주말'] / 100:.1f}배, 평일 공연일은 낮에는 평소와 비슷하다가 "
               f"{k['저녁최고시_평일']}시에 {k['저녁최고지수_평일'] / 100:.1f}배가 됩니다(같은 달 공연 없는 날 같은 시각 = 1배).")
    if k["관객_피크_상관"] == k["관객_피크_상관"]:  # NaN 이 아니면
        strength = "뚜렷하지 않습니다" if abs(k["관객_피크_상관"]) < 0.3 else "어느 정도 있습니다"
        out.append(f"공연 관람객 수와 하루 최대 주차대수의 상관계수는 {k['관객_피크_상관']}로 관계가 {strength}. "
                   f"주차 운영 계획은 관객 수보다 공연 시작 시각과 요일을 기준으로 세우는 편이 맞습니다.")
    w = weather.set_index("조건")
    if "비 옴" in w.index:
        out.append(f"비가 온 시간(공연 없는 날 9~20시)은 같은 달·시간대 평균 대비 {pct(w.loc['비 옴', 'mean'])}였습니다"
                   f"(표본 {int(w.loc['비 옴', 'size'])}시간).")
    return out


def findings(k, occ, daily, heat):
    """숫자에서 자동으로 해설 문장을 만든다 (데이터가 바뀌면 문장도 바뀜)."""
    wd = occ[occ["구분"] == "평일"].set_index("시")["재차대수"]
    we = occ[occ["구분"] == "주말"].set_index("시")["재차대수"]
    early = wd.loc[5:7].mean() / we.loc[5:7].mean()
    pm = we.loc[14:17].mean() / wd.loc[14:17].mean()
    top3 = daily.nlargest(3, "입차대수")
    top3_txt = ", ".join(f"{r['날짜']:%m/%d}({r['요일']}) {r['입차대수']:,}대" for _, r in top3.iterrows())
    diff = (k["주말일평균"] - k["평일일평균"]) / k["평일일평균"] * 100
    return [
        f"하루 입차 대수는 평일 {k['평일일평균']:,}대, 주말 {k['주말일평균']:,}대로 차이가 {diff:+.1f}%에 그칩니다. "
        f"총량보다 '몰리는 시간'이 다릅니다.",
        f"평일 정점은 {int(wd.idxmax())}시(평균 {int(wd.max()):,}대), 주말 정점은 {int(we.idxmax())}시"
        f"(평균 {int(we.max()):,}대)입니다.",
        f"평일 새벽 5~7시 재차 대수는 주말 같은 시간의 {early:.1f}배입니다. 출근 전 운동·통근 수요로 추정되며, 이용자 조사로 확인이 필요합니다.",
        f"주말 오후 2~5시 재차 대수는 평일 같은 시간의 {pm:.1f}배입니다. 공연·행사 일정과의 관계는 2025 연계 데이터로 검증할 예정입니다.",
        f"입차가 가장 많았던 날은 {top3_txt}입니다.",
        f"입차 차량의 {k['단시간비율']}%는 5분 안에 출차했습니다(통과·승하차 추정). 일반 체류 차량의 체류시간 중앙값은 {k['체류중앙값분']}분입니다.",
    ]


TEMPLATE = Template("""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>올림픽공원 방문 흐름 리포트</title>
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@{{ plotly_ver }}/plotly.min.js"></script>
<style>
:root{--bg:#f9f9f7;--card:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--line:#e1e0d9;--accent:#2a78d6}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#0d0d0d;--card:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--line:#2c2c2a;--accent:#3987e5}}
:root[data-theme="dark"]{--bg:#0d0d0d;--card:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--line:#2c2c2a;--accent:#3987e5}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font-family:{{ font }};line-height:1.6}
main{max-width:980px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:28px;margin:0 0 4px} h2{font-size:19px;margin:40px 0 12px} .sub{color:var(--ink2);margin:0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-top:24px}
.kpi,.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.kpi b{display:block;font-size:26px;font-variant-numeric:tabular-nums} .kpi span{color:var(--ink2);font-size:14px}
ul.f li{margin:6px 0} .note{color:var(--ink2);font-size:14px}
table{border-collapse:collapse;width:100%;font-size:14px} td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left}
footer{margin-top:48px;color:var(--muted);font-size:13px}
</style></head><body><main>
<h1>올림픽공원 방문 흐름 리포트</h1>
<p class="sub">주차 입출차 기록으로 본 방문객 흐름 · 분석 기간 {{ k['기간'] }} · 자동 생성 {{ generated }}</p>

<div class="kpis">
  <div class="kpi"><span>총 입차</span><b>{{ "{:,}".format(k['총입차']) }}대</b></div>
  <div class="kpi"><span>하루 평균 입차</span><b>{{ "{:,}".format(k['일평균입차']) }}대</b></div>
  <div class="kpi"><span>최대 동시 재차</span><b>{{ "{:,}".format(k['최대재차대수']) }}대</b><span>{{ k['최대재차시각'] }}</span></div>
  <div class="kpi"><span>체류시간 중앙값</span><b>{{ k['체류중앙값분'] }}분</b><span>5분 미만 체류 제외</span></div>
</div>

<h2>핵심 발견</h2>
<div class="card"><ul class="f">{% for f in findings %}<li>{{ f }}</li>{% endfor %}</ul></div>

<h2>시간대별 주차장 안 차량 수 (평일 vs 주말)</h2>
<div class="card">{{ occ_chart }}<p class="note">매 시간 주차장 안에 있던 차량 수의 최대값을 평일/주말별로 평균 낸 값입니다.</p></div>

<h2>요일 × 시간대 입차 (하루 평균)</h2>
<div class="card">{{ heat_chart }}</div>

<h2>날짜별 입차 대수</h2>
<div class="card">{{ daily_chart }}</div>

{% if y25 %}
<h2 style="margin-top:56px">2025 공연·날씨와 방문 흐름</h2>
<p class="sub">공연·날씨 연계 데이터 · {{ y25.k['기간'] }} · 시간대별 {{ "{:,}".format(y25.k['시간대수']) }}건</p>
<div class="kpis">
  <div class="kpi"><span>공연일</span><b>{{ y25.k['공연일수'] }}일</b><span>전체 {{ y25.k['일수'] }}일 중</span></div>
  <div class="kpi"><span>주말 공연일 저녁 지수</span><b>{{ "%.0f"|format(y25.k['저녁지수_주말']) }}</b><span>18~21시, 공연 없는 날 = 100</span></div>
  <div class="kpi"><span>평일 공연일 저녁 지수</span><b>{{ "%.0f"|format(y25.k['저녁지수_평일']) }}</b><span>18~21시, 공연 없는 날 = 100</span></div>
  <div class="kpi"><span>최대 주차대수</span><b>{{ "{:,}".format(y25.k['최대주차']) }}대</b><span>{{ y25.k['최대주차시각'] }}</span></div>
</div>
<h2>핵심 발견 (2025)</h2>
<div class="card"><ul class="f">{% for f in y25.findings %}<li>{{ f }}</li>{% endfor %}</ul></div>
<h2>공연일의 시간대별 주차 지수</h2>
<div class="card">{{ y25.profile }}<p class="note">같은 달·같은 요일유형·같은 시각의 공연 없는 날 평균을 100으로 둔 값입니다. 달마다 집계 수준이 달라도 공정하게 비교하기 위한 방식입니다.</p></div>
<h2>공연 규모와 주차 증가</h2>
<div class="card">{{ y25.scatter }}<p class="note">점 하나 = 공연일 하루. 세로축은 같은 달·같은 요일유형의 공연 없는 날 평균 피크 대비 증가율입니다.</p></div>
<h2>날씨별 주차 (공연 없는 날 9~20시)</h2>
<div class="card"><table><tr><th>조건</th><th>같은 시간대 평균 대비</th><th>표본(시간)</th></tr>
{% for r in y25.weather if r['size'] > 0 %}<tr><td>{{ r['조건'] }}</td><td>{{ pct(r['mean']) if r['mean'] == r['mean'] else "-" }}</td><td>{{ r['size'] }}</td></tr>{% endfor %}
</table></div>
<h2>공연일 상위 10</h2>
<div class="card"><table><tr><th>날짜</th><th>공연</th><th>관람객</th><th>피크 주차</th><th>기준 대비</th></tr>
{% for r in y25.top %}<tr><td>{{ r['날짜'] }}</td><td>{{ r['공연명'] }}</td><td>{{ "{:,}".format(r['관람객수']|int) }}</td><td>{{ "{:,}".format(r['피크주차']|int) }}</td><td>{{ "%+.0f%%"|format(r['증가율']) if r['증가율'] == r['증가율'] else "-" }}</td></tr>{% endfor %}
</table></div>
{% endif %}

<h2>데이터와 한계</h2>
<div class="card note">
<ul>
<li>출처: 공공데이터포털, 한국체육산업개발주식회사_올림픽공원 입출차 정보 (1행 = 차량 1대, 입차·출차 시각).</li>
<li>원본 {{ "{:,}".format(k['총입차']) }}행 중 완전히 같은 행 {{ "{:,}".format(dup) }}건이 있습니다. 차량 ID가 없어 같은 분에 드나든 다른 차인지 구분할 수 없으므로 제거하지 않았습니다.</li>
<li>분석 기간 첫날 이전에 들어온 차량은 데이터에 없어서, 재차 대수는 둘째 날부터 계산했습니다.</li>
<li>주차 데이터는 차량 방문만 반영합니다. 대중교통·도보 방문객은 포함되지 않습니다.</li>
{% if y25 %}<li>2025 연계 데이터의 '방문객' 값은 주차대수에 일정 배율(평일 3배, 주말·휴일 5배로 확인)을 곱한 추정값이라 분석에 쓰지 않았습니다.</li>
<li>2025 공연 효과의 비교 기준은 '같은 달 + 같은 요일유형(+ 같은 시각)'의 공연 없는 정상일 평균입니다. 같은 달에 그런 날이 없으면 집계 수준이 같은 앞뒤 달 평균으로 보완했습니다. 공연일 {{ y25.k['공연일수'] }}일 중 {{ y25.k['기준있는공연일'] }}일을 비교했고(앞뒤 달 기준 {{ y25.k['앞뒤달기준공연일'] }}일), 나머지는 비교할 기준이 없어 제외했습니다.</li>
{% for n in y25.notes %}<li>{{ n }}</li>{% endfor %}{% endif %}
</ul></div>

<footer>이 보고서는 Python(pandas, Plotly) 파이프라인으로 수집 → 정리 → 지표 → 보고서까지 자동 생성되었습니다.</footer>
</main></body></html>""")


if __name__ == "__main__":
    daily = pd.read_csv(CLEAN / "m_daily.csv", parse_dates=["날짜"])
    heat = pd.read_csv(CLEAN / "m_heatmap.csv", index_col=0)
    occ = pd.read_csv(CLEAN / "m_occupancy.csv")
    k = json.loads((CLEAN / "m_kpi.json").read_text(encoding="utf-8"))
    dup = int(pd.read_csv(CLEAN / "visits.csv", usecols=["입차시각", "출차시각"]).duplicated().sum())

    def html(fig):  # plotly.js 는 페이지 <head> 에서 한 번만 불러오므로 여기선 차트만
        return fig.to_html(full_html=False, include_plotlyjs=False,
                           config={"displayModeBar": False, "responsive": True})

    y25 = None
    if (CLEAN / "m25_kpi.json").exists():   # 2025 연계 데이터 지표가 있으면 섹션 추가
        k25 = json.loads((CLEAN / "m25_kpi.json").read_text(encoding="utf-8"))
        prof = pd.read_csv(CLEAN / "m25_profile.csv")
        shows = pd.read_csv(CLEAN / "m25_shows.csv")
        shows["공연명"] = shows["공연명"].fillna("")
        weather = pd.read_csv(CLEAN / "m25_weather.csv")
        notes_file = CLEAN / "m25_notes.json"
        top = shows.head(10).copy()
        top["날짜"] = top["날짜"].astype(str).str[:10]
        top["공연명"] = top["공연명"].str.slice(0, 45)
        y25 = dict(
            k=k25, findings=findings_2025(k25, shows, weather),
            profile=html(chart_show_profile(prof)),
            scatter=html(chart_show_scatter(shows)),
            weather=weather.to_dict("records"), top=top.to_dict("records"),
            notes=json.loads(notes_file.read_text(encoding="utf-8")) if notes_file.exists() else [],
        )

    OUT.mkdir(exist_ok=True)
    page = TEMPLATE.render(
        y25=y25, plotly_ver=get_plotlyjs_version(), pct=pct,
        k=k, dup=dup, font=FONT, generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        findings=findings(k, occ, daily, heat),
        occ_chart=html(chart_occupancy(occ)),
        heat_chart=html(chart_heatmap(heat)),
        daily_chart=html(chart_daily(daily)),
    )
    (OUT / "report.html").write_text(page, encoding="utf-8")
    print("보고서 생성:", OUT / "report.html")
    for f in findings(k, occ, daily, heat):
        print(" -", f)
