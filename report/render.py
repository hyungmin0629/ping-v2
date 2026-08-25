"""
주간 보고서 · ② 렌더 층 — JSON 을 3쪽 PDF 로.

    python report/render.py                              # 가장 최근 JSON
    python report/render.py --json report/out/weekly-2026-08-17.json
    python report/render.py --html-only                  # PDF 없이 HTML 만

`collect.py` 가 만든 JSON 만 읽는다. **BigQuery 를 다시 부르지 않는다** —
그림을 고치려고 매번 스캔하면 돈이 나가고, 숫자가 바뀌어 비교도 안 된다.

──────────────────────────────────────────────────────────────────────
⚠️ 이 파일의 핵심은 그림이 아니라 **억제 규칙**이다.

실유저는 20~50명 규모라 분모가 한 자릿수인 칸이 흔하다. 2명 중 1명이
투표한 것을 "50.0%"로 적으면 그 숫자는 거짓말이 된다 — 한 명이 마음을
바꾸면 0% 나 100% 가 되는 값이기 때문이다.

    분모 0        "관측 없음"
    분모 < 10     "1/2" 처럼 **실수로** 적는다 (비율을 만들지 않는다)
    분모 >= 10    "32.4%"

유저가 늘면 같은 코드가 저절로 비율을 쓰기 시작한다. 임계값은 MIN_DEN.
──────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from charts import BLUE, ORANGE, empty_note, grouped_bars, hbars, line_chart  # noqa: E402

TEMPLATE = HERE / "template" / "weekly.html"
OUT = HERE / "out"

MIN_DEN = 10          # 이보다 분모가 작으면 비율을 만들지 않는다
GOAL_PARTICIPATION = 30.0   # 주간 유효 투표 참여율 목표(%)
DASHBOARD_URL = "https://lookerstudio.google.com/"

SOURCE_LABEL = {
    "supabase": "실유저 데이터",
    "local": "합성 데이터 시뮬레이션",
}


# ---------------------------------------------------------------------
# 숫자와 억제
# ---------------------------------------------------------------------
class Ratio:
    """비율 하나. **분모가 작으면 비율을 만들지 않는다.**"""

    def __init__(self, num: float, den: float, min_den: int = MIN_DEN):
        self.num, self.den = num or 0, den or 0
        self.ok = self.den >= min_den
        self.pct = (100.0 * self.num / self.den) if self.den else None

    @property
    def text(self) -> str:
        if not self.den:
            return "관측 없음"
        if not self.ok:
            return f"{self.num:,.0f}/{self.den:,.0f}"
        return f"{self.pct:.1f}%"

    @property
    def note(self) -> str:
        if not self.den:
            return "대상자 없음"
        if not self.ok:
            return f"분모 {self.den:,.0f}명 — 비율 판단 불가"
        return f"분모 {self.den:,.0f}명"

    def delta_to(self, other: "Ratio") -> str:
        """전주 대비 %p. 어느 한쪽이라도 억제됐으면 비교하지 않는다."""
        if not (self.ok and other and other.ok):
            return ""
        return fmt_delta(self.pct - other.pct, unit="%p", digits=1)


def fmt_delta(diff: float, unit: str = "", digits: int = 0, invert: bool = False) -> str:
    """▲/▼ 배지. `invert` 는 '늘어나면 나쁜' 지표(신고 적체)에 쓴다."""
    if abs(diff) < (0.05 if digits else 0.5):
        return '<span class="flat">전주와 같음</span>'
    up = diff > 0
    cls = ("down" if up else "up") if invert else ("up" if up else "down")
    arrow = "▲" if up else "▼"
    val = f"{abs(diff):,.{digits}f}"
    return f'<span class="{cls}">{arrow} {val}{unit}</span>'


def won(v: float) -> str:
    v = v or 0
    if v >= 1_000_000:
        return f"₩{v/1_000_000:.2f}M"
    return f"₩{v:,.0f}"


def esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def mmdd(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.month}/{d.day}"


# ---------------------------------------------------------------------
# 조각들
# ---------------------------------------------------------------------
def kpi(title: str, value: str, delta: str = "", note: str = "",
        attn: bool = False, small: bool = False) -> str:
    return (
        f'<div class="kpi{" attn" if attn else ""}">'
        f'<div class="k">{esc(title)}</div>'
        f'<div class="v{" sm" if small else ""}">{value}</div>'
        f'<div class="foot"><span class="note">{esc(note)}</span>{delta}</div>'
        f"</div>"
    )


def fit_rows(n: int, box_h: int) -> int:
    """행 높이를 상자에 맞춘다. 항목이 적다고 막대가 상자 위쪽에 몰리지 않게."""
    if n <= 0:
        return 34
    return max(24, min(56, (box_h - 14) // n))


def funnel_bars(rows: list[dict], empty_msg: str, box_h: int = 230) -> str:
    if not rows or not rows[0].get("base"):
        return empty_note(empty_msg, box_h)
    base = rows[0]["base"] or 1
    items = []
    for r in rows:
        v = r["value"] or 0
        rt = Ratio(v, base)
        right = f'{v:,.0f} · {rt.text}' if rt.ok else f'{v:,.0f} / {base:,.0f}'
        items.append((r["step_label"], v, right))
    return hbars(items, width=500, label_w=104, row_h=fit_rows(len(items), box_h))


def cohort_table(rows: list[dict], week_end: date) -> str:
    if not rows:
        return '<div class="cap" style="text-align:center;padding:18px 0">첫 투표 코호트가 아직 없습니다</div>'
    cohorts: dict[str, dict] = {}
    for r in rows:
        c = cohorts.setdefault(r["cohort_week"], {"size": r["cohort_size"], "w": {}})
        if r.get("week_no") is not None:
            c["w"][int(r["week_no"])] = r["voters"] or 0

    head = "".join(f"<th>W{i}</th>" for i in range(5))
    body = []
    for cw in sorted(cohorts):
        c = cohorts[cw]
        cells = [f'<td class="rowhead">{mmdd(cw)} 주<br><span style="font-weight:400">'
                 f'{c["size"]:,}명</span></td>']
        for i in range(5):
            # 그 주차가 실제로 지나갔는가. 안 지났으면 '아직 모른다'로 둔다.
            observed_end = date.fromisoformat(cw) + timedelta(days=7 * i + 6)
            if observed_end > week_end:
                cells.append('<td class="none">-</td>')
                continue
            rt = Ratio(c["w"].get(i, 0), c["size"])
            cells.append(f'<td class="c{min(i,4)}">{rt.text}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (f'<table class="cohort"><tr><th></th>{head}</tr>' + "".join(body) + "</table>")


def segment_bars(rows: list[dict]) -> tuple[str, str]:
    """차원 값이 하나뿐인 축은 그리지 않는다 — 정보가 0이다."""
    by_dim: dict[str, list[dict]] = {}
    for r in rows:
        by_dim.setdefault(r["dim"], []).append(r)
    items, notes = [], []
    for dim in ("school_type", "grade"):
        group = by_dim.get(dim, [])
        if len(group) < 2:
            if group:
                notes.append(f'{group[0]["label"]} 한 갈래뿐이라 축에서 뺐습니다')
            continue
        for r in sorted(group, key=lambda x: x["label"]):
            rt = Ratio(r["voters"], r["eligible"])
            items.append((r["label"], rt.pct or 0, rt.text))
    if not items:
        return (empty_note("나눌 세그먼트가 없습니다", 200), " · ".join(notes))
    return (hbars(items, width=500, label_w=72, row_h=fit_rows(len(items), 210)),
            " · ".join(notes))


def heart_bars(rows: list[dict], box_h: int = 250) -> str:
    if not rows:
        return empty_note("이번 주 하트 이동이 없습니다", box_h)
    items = []
    for r in sorted(rows, key=lambda x: (not x["is_credit"], -max(x["hearts_earned"], x["hearts_spent"]))):
        v = r["hearts_earned"] if r["is_credit"] else r["hearts_spent"]
        items.append((r["flow_label"], v, f"{v:,.0f}"))
    return hbars(items, width=500, label_w=92, row_h=fit_rows(len(items), box_h))


# ---------------------------------------------------------------------
def build(data: dict) -> str:
    meta = data["meta"]
    week_start = date.fromisoformat(meta["week_start"])
    week_end = date.fromisoformat(meta["week_end"])
    weeks = data["weeks"]
    cur = weeks[-1] if weeks else {}
    prev = weeks[-2] if len(weeks) > 1 else {}
    g = lambda row, k: (row or {}).get(k, 0) or 0  # noqa: E731

    # ── 신선도 배지 ────────────────────────────────────────────────
    fr = data.get("freshness") or {}
    last_data = fr.get("last_data_date")
    badges = [f'<span class="badge">{esc(SOURCE_LABEL.get(meta["source"], meta["source"]))}</span>']
    if last_data and date.fromisoformat(last_data) >= week_end:
        badges.insert(0, '<span class="badge ok">파이프라인 정상</span>')
    else:
        badges.insert(0, f'<span class="badge warn">⚠ 데이터 {esc(last_data or "없음")} 까지</span>')
    if fr.get("mart_built_on"):
        badges.append(f'<span class="badge">Mart 갱신 {esc(fr["mart_built_on"])}</span>')

    # ── 1쪽 KPI ───────────────────────────────────────────────────
    part = Ratio(g(cur, "eligible_voters"), g(cur, "eligible"))
    part_prev = Ratio(g(prev, "eligible_voters"), g(prev, "eligible"))

    # W2 리텐션 — 관찰이 끝난 가장 최근 코호트
    coh: dict[str, dict] = {}
    for r in data.get("cohort", []):
        c = coh.setdefault(r["cohort_week"], {"size": r["cohort_size"], "w": {}})
        if r.get("week_no") is not None:
            c["w"][int(r["week_no"])] = r["voters"] or 0
    observable = [cw for cw in sorted(coh)
                  if date.fromisoformat(cw) + timedelta(days=20) <= week_end]
    w2 = Ratio(coh[observable[-1]]["w"].get(2, 0), coh[observable[-1]]["size"]) if observable else Ratio(0, 0)
    w2_prev = (Ratio(coh[observable[-2]]["w"].get(2, 0), coh[observable[-2]]["size"])
               if len(observable) > 1 else None)

    backlog = data.get("backlog", [])
    bl_cur = backlog[-1] if backlog else {}
    bl_prev = backlog[-2] if len(backlog) > 1 else {}

    kpi_cards = "".join([
        kpi("주간 접속 사용자 WAU", f'{g(cur,"wau"):,}명',
            fmt_delta(g(cur, "wau") - g(prev, "wau"), unit="명"),
            f'전주 {g(prev,"wau"):,}명'),
        kpi("주간 유효 투표 참여율", part.text, part.delta_to(part_prev), part.note,
            small=not part.ok),
        kpi("W2 투표 리텐션", w2.text, w2.delta_to(w2_prev),
            f'{mmdd(observable[-1])} 주 코호트' if observable else "관찰 가능 코호트 없음",
            small=not w2.ok),
        kpi("신규 가입자", f'{g(cur,"signups"):,}명',
            fmt_delta(g(cur, "signups") - g(prev, "signups"), unit="명"),
            f'전주 {g(prev,"signups"):,}명'),
        kpi("주간 실제 매출", won(g(cur, "revenue_krw")),
            fmt_delta(g(cur, "revenue_krw") - g(prev, "revenue_krw"), unit="원"),
            f'스텁 {g(cur,"stub_purchases"):,}건 제외' if g(cur, "stub_purchases")
            else "성공 결제만 포함"),
        kpi("미처리 신고", f'{g(bl_cur,"pending_count"):,}건',
            fmt_delta(g(bl_cur, "pending_count") - g(bl_prev, "pending_count"),
                      unit="건", invert=True),
            f'7일+ 미처리 {g(bl_cur,"pending_gt7d"):,}건', attn=True),
    ])

    # ── 1쪽 차트 ──────────────────────────────────────────────────
    labels = [f"W-{len(weeks)-1-i}" if i < len(weeks) - 1 else "금주" for i in range(len(weeks))]
    part_series = [Ratio(g(w, "eligible_voters"), g(w, "eligible")) for w in weeks]
    chart_part = line_chart(
        labels, [(r.pct if r.den else None) for r in part_series],
        fmt=lambda v: f"{v:.0f}%", point_fmt=lambda v: f"{v:.1f}%",
        goal=GOAL_PARTICIPATION, goal_label="목표 30%", width=500, height=365)

    stage = {r["week_start"]: r for r in data.get("stage", [])}
    s_cur = stage.get(meta["week_start"], {})
    s_prev = stage.get((week_start - timedelta(days=7)).isoformat(), {})
    chart_stage = grouped_bars([
        ("신규", g(prev, "signups"), g(cur, "signups")),
        ("접속", g(prev, "wau"), g(cur, "wau")),
        ("투표", g(prev, "voters"), g(cur, "voters")),
        ("10문항(건)", g(s_prev, "sessions_10q"), g(s_cur, "sessions_10q")),
        ("결제", g(prev, "payers"), g(cur, "payers")),
    ], width=500, height=365)

    # ── 1쪽 요약 — 데이터가 문장을 정한다 ─────────────────────────
    lines = []
    if part.ok:
        diff = part.pct - GOAL_PARTICIPATION
        lines.append(("good", f"주간 유효 투표 참여율 {part.text}로 목표 {GOAL_PARTICIPATION:.0f}%를 "
                              f"{abs(diff):.1f}%p {'초과' if diff >= 0 else '밑돌았습니다'}.")
                     if diff >= 0 else
                     ("warn", f"주간 유효 투표 참여율 {part.text}로 목표 {GOAL_PARTICIPATION:.0f}%에 "
                              f"{abs(diff):.1f}%p 못 미쳤습니다."))
    else:
        lines.append(("info", f"유효 사용자 {g(cur,'eligible'):,}명 중 {g(cur,'eligible_voters'):,}명이 "
                              f"투표했습니다. 표본이 작아 비율 대신 실수로 적었습니다."))
    if g(cur, "signups"):
        lines.append(("info", f"신규 가입 {g(cur,'signups'):,}명. "
                              f"활동 사용자는 {g(cur,'wau'):,}명(전주 {g(prev,'wau'):,}명)입니다."))
    else:
        lines.append(("warn", f"이번 주 신규 가입이 없습니다. 활동 사용자 {g(cur,'wau'):,}명은 "
                              f"기존 가입자입니다."))
    if g(bl_cur, "pending_gt7d"):
        lines.append(("ops", f"7일 이상 미처리 신고가 {g(bl_cur,'pending_gt7d'):,}건입니다. "
                             f"처리 화면이 없어 신고가 PENDING 으로 쌓이고 있습니다."))
    elif g(bl_cur, "pending_count"):
        lines.append(("ops", f"미처리 신고 {g(bl_cur,'pending_count'):,}건이 남아 있습니다."))
    else:
        lines.append(("good", "미처리 신고가 없습니다."))
    if not g(cur, "revenue_krw") and g(cur, "stub_purchases"):
        lines.append(("info", f"충전 {g(cur,'stub_purchases'):,}건은 전부 MVP 스텁이라 "
                              f"매출로 세지 않았습니다."))
    tagname = {"good": "성과", "warn": "주의", "ops": "운영", "info": "관측"}
    summary = "".join(
        f'<div class="sline"><span class="tag {t}">{tagname[t]}</span><span>{esc(msg)}</span></div>'
        for t, msg in lines[:4])

    # ── 2쪽 ───────────────────────────────────────────────────────
    fu = data.get("funnel_user", [])
    funnel_user = funnel_bars(fu, "이번 주 신규 가입이 없어 표시할 코호트가 없습니다", 215)
    act_cap = (f'금주 가입자 {fu[0]["base"]:,}명을 동일 분모로 추적' if fu
               else "같은 주에 가입한 사용자 기준")
    act_note = ("가입 직후라 관찰 기간이 짧습니다 — 뒷단계는 늘 낮게 나옵니다. "
                "힌트 단계는 받은 투표에서 사는 것이라 이 퍼널에 넣지 않았습니다.")
    funnel_recv = funnel_bars(data.get("funnel_received", []),
                              "이번 주에 오간 투표가 없습니다", 215)
    recv_note = "광고로 연 무료 힌트와 하트로 산 힌트를 합쳐 셌습니다."
    cohort_html = cohort_table(data.get("cohort", []), week_end)
    cohort_note = (f"분모가 {MIN_DEN}명 미만인 코호트는 비율 대신 실수로 적습니다.")
    seg_html, seg_note = segment_bars(data.get("segments", []))
    seg_cap = f"전체 {part.text} 대비 차이가 큰 집단"

    # ── 3쪽 ───────────────────────────────────────────────────────
    arppu = (g(cur, "revenue_krw") / g(cur, "payers")) if g(cur, "payers") else None
    rev_cards = "".join([
        kpi("주간 실제 매출", won(g(cur, "revenue_krw")),
            fmt_delta(g(cur, "revenue_krw") - g(prev, "revenue_krw"), unit="원"),
            "성공 결제 기준 · 스텁 제외"),
        kpi("결제 사용자", f'{g(cur,"payers"):,}명',
            fmt_delta(g(cur, "payers") - g(prev, "payers"), unit="명"), "중복 제외"),
        kpi("ARPPU", won(arppu) if arppu else "관측 없음", "",
            "매출 ÷ 결제자", small=arppu is None),
        kpi("첫 결제 사용자", f'{g(cur,"first_payers"):,}명', "",
            f'재결제 {max(g(cur,"payers")-g(cur,"first_payers"),0):,}명'),
    ])
    chart_rev = line_chart(labels, [g(w, "revenue_krw") for w in weeks],
                           fmt=lambda v: won(v), width=500, height=140,
                           zero_note="이 8주 동안 실제 매출이 없습니다 — 충전은 전부 MVP 스텁입니다")
    heart_html = heart_bars(data.get("heart_flow", []))
    heart_note = (f'광고로 연 무료 힌트 {g(cur,"hints_by_ad"):,}건은 하트가 움직이지 않아 '
                  f'이 막대에 없습니다. 유료 힌트는 {g(cur,"hints_paid"):,}건입니다.')
    chart_backlog = line_chart(labels[-len(backlog):] if backlog else labels,
                               [g(b, "pending_count") for b in backlog] or [0],
                               fmt=lambda v: f"{v:,.0f}", color=ORANGE, unit="건",
                               width=500, height=270)

    alert_rows = [
        ("신규 신고", f'{g(bl_cur,"reported_in_week"):,}건', BLUE),
        ("처리 완료", f'{g(bl_cur,"closed_in_week"):,}건', "#16a34a"),
        ("미처리 증감",
         f'{g(bl_cur,"pending_count")-g(bl_prev,"pending_count"):+,}건', ORANGE),
        ("7일 이상 미처리", f'{g(bl_cur,"pending_gt7d"):,}건', "#dc2626"),
    ]
    alerts = "".join(
        f'<div class="alert"><span><span class="dot" style="background:{c}"></span>'
        f'{esc(k)}</span><b>{esc(v)}</b></div>' for k, v, c in alert_rows)
    if g(bl_cur, "pending_gt7d"):
        alerts += ('<div class="callout">확인 필요: 7일 이상 미처리 신고 — '
                   '처리 화면(sanction)이 아직 없습니다</div>')
    else:
        alerts += '<div class="callout quiet">장기 미처리 신고 없음</div>'

    # ── 채우기 ────────────────────────────────────────────────────
    period = f'{week_start:%Y.%m.%d}-{week_end:%m.%d}'
    stamp = (f'데이터 기간 {period} · 생성 '
             f'{datetime.fromisoformat(meta["generated_at"]):%Y.%m.%d %H:%M}')
    values = {
        "TITLE": f"PING 주간 보고서 {period}",
        "PERIOD": period,
        "SOURCE_LABEL": SOURCE_LABEL.get(meta["source"], meta["source"]),
        "BADGES": "".join(badges),
        "KPI_CARDS": kpi_cards,
        "CHART_PARTICIPATION": chart_part,
        "CHART_STAGES": chart_stage,
        "STAGE_UNIT_NOTE": " · 10문항만 세션 건수",
        "SUMMARY": summary,
        "DASHBOARD_URL": DASHBOARD_URL,
        "ACT_CAP": act_cap,
        "ACT_NOTE": act_note,
        "FUNNEL_USER": funnel_user,
        "FUNNEL_RECV": funnel_recv,
        "RECV_NOTE": recv_note,
        "COHORT": cohort_html,
        "COHORT_NOTE": cohort_note,
        "SEG_CAP": seg_cap,
        "SEGMENTS": seg_html,
        "SEG_NOTE": seg_note or "학교급·학년별 분모는 그 주 끝 기준 유효 사용자입니다.",
        "REV_CARDS": rev_cards,
        "CHART_REVENUE": chart_rev,
        "HEART_FLOW": heart_html,
        "HEART_NOTE": heart_note,
        "CHART_BACKLOG": chart_backlog,
        "REPORT_ALERTS": alerts,
        "FOOTNOTE": ("본 보고서는 BigQuery mart 에서 자동 생성됩니다. "
                     "분모가 작은 지표는 비율 대신 실수로 표기합니다."),
        "STAMP": stamp,
    }
    html = TEMPLATE.read_text(encoding="utf-8")
    for k, v in values.items():
        html = html.replace("{{" + k + "}}", str(v))
    return html


def to_pdf(html_path: Path, pdf_path: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright 가 없습니다. .venv 에서:\n"
                 "  python -m pip install -r requirements.txt\n"
                 "  python -m playwright install chromium")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.resolve().as_uri(), wait_until="load")
        page.pdf(path=str(pdf_path), print_background=True,
                 prefer_css_page_size=True, margin={"top": "0", "bottom": "0",
                                                    "left": "0", "right": "0"})
        browser.close()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="collect.py 산출물. 없으면 가장 최근 것")
    ap.add_argument("--html-only", action="store_true")
    args = ap.parse_args()

    if args.json:
        src = Path(args.json)
    else:
        found = sorted(OUT.glob("weekly-*.json"))
        if not found:
            sys.exit("report/out 에 JSON 이 없습니다. 먼저 collect.py 를 돌리세요.")
        src = found[-1]

    data = json.loads(src.read_text(encoding="utf-8"))
    html = build(data)
    stem = f'PING-weekly-{data["meta"]["week_start"]}'
    html_path = OUT / f"{stem}.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"HTML {html_path}")
    if args.html_only:
        return 0
    pdf_path = OUT / f"{stem}.pdf"
    to_pdf(html_path, pdf_path)
    print(f"✅ PDF  {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
