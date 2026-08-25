"""
주간 보고서 · 인라인 SVG 차트.

**외부 라이브러리도 자바스크립트도 쓰지 않는다.** PDF 로 뽑을 때 헤드리스
브라우저가 스크립트 실행을 기다리게 만들면 "가끔 빈 그래프가 나오는" 버그가
생긴다. 문자열로 만든 SVG 는 로드되는 순간 이미 그려져 있다.

색은 본문 CSS 변수와 같은 값을 쓴다(`template/weekly.html`).
"""

from __future__ import annotations

BLUE = "#2563eb"
BLUE_LIGHT = "#93b4f7"
GRAY = "#cbd5e1"
ORANGE = "#f59e0b"
INK = "#0f172a"
DIM = "#64748b"


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _nice_max(v: float) -> float:
    """축 상한을 사람이 읽기 좋은 값으로. 0 이면 1 로 둔다(선이 사라지지 않게)."""
    if v <= 0:
        return 1.0
    # ⚠️ 지수가 바깥이다. 배수를 바깥으로 돌면 12 를 재는데 100 이 나온다
    #    (1×10⁰ → 1×10¹ → 1×10² 순으로 먼저 커지기 때문). 2026-08-25 실제로 겪었다.
    for exp in range(-2, 13):
        for mult in (1, 2, 2.5, 5, 10):
            cand = mult * (10 ** exp)
            if cand >= v:
                return float(cand)
    return float(v)


def empty_note(msg: str, height: int = 120) -> str:
    """그릴 것이 없을 때. **빈 상자를 두지 않는다** — 고장인지 0인지 구별이 안 된다."""
    return (f'<div class="cap" style="text-align:center;padding:{height//3}px 0">'
            f'{_esc(msg)}</div>')


def line_chart(labels, values, *, fmt=None, color=BLUE, goal=None, goal_label=None,
               width=760, height=210, unit="", zero_note=None, point_fmt=None) -> str:
    """8주 추이. 값이 전부 0 이어도 축과 선을 그린다 — 빈 칸은 오해를 낳는다."""
    fmt = fmt or (lambda v: f"{v:,.0f}")
    point_fmt = point_fmt or fmt   # 축 눈금과 끝점 라벨의 자릿수를 따로 둘 수 있다
    if zero_note and not any(values):
        return empty_note(zero_note, height)
    pad_l, pad_r, pad_t, pad_b = 46, 34, 18, 26
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    # None 은 **0 이 아니라 '모른다'** 다. 분모가 없던 주(가입자가 아직 없던 주)를
    # 0% 로 그리면 "참여율이 0이었다"는 없던 사실이 생긴다. 선을 끊는다.
    known = [v for v in values if v is not None]
    vmax = _nice_max(max(known + ([goal] if goal else []) + [0]) * 1.15)
    n = max(len(values), 1)
    xs = [pad_l + (w * i / (n - 1) if n > 1 else w / 2) for i in range(n)]
    ys = [None if v is None else pad_t + h - (h * (v / vmax)) for v in values]

    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">']
    # 가로 눈금 3줄
    for frac in (0, 0.5, 1):
        y = pad_t + h - h * frac
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+w}" y2="{y:.1f}" '
                     f'stroke="#eef2f7" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l-8}" y="{y+4:.1f}" text-anchor="end" '
                     f'class="axis">{_esc(fmt(vmax*frac))}</text>')
    if goal is not None and vmax > 0:
        gy = pad_t + h - h * (goal / vmax)
        parts.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l+w}" y2="{gy:.1f}" '
                     f'stroke="{ORANGE}" stroke-width="1.2" stroke-dasharray="5 4"/>')
        if goal_label:
            parts.append(f'<text x="{pad_l+w}" y="{gy-6:.1f}" text-anchor="end" '
                         f'class="axis" fill="{ORANGE}">{_esc(goal_label)}</text>')
    if n > 1:
        d, pen_down = [], False
        for x, y in zip(xs, ys):
            if y is None:
                pen_down = False
                continue
            d.append(f"{'L' if pen_down else 'M'}{x:.1f},{y:.1f}")
            pen_down = True
        if d:
            parts.append(f'<path d="{" ".join(d)}" fill="none" stroke="{color}" '
                         f'stroke-width="2.2" stroke-linejoin="round"/>')
    for i, (x, y) in enumerate(zip(xs, ys)):
        last = i == n - 1
        if y is not None:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{4 if last else 3}" '
                         f'fill="{color if last else "#fff"}" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{x:.1f}" y="{height-8}" text-anchor="middle" class="axis">'
                     f'{_esc(labels[i])}</text>')
    if n and ys[-1] is not None:
        parts.append(f'<text x="{xs[-1]:.1f}" y="{ys[-1]-12:.1f}" text-anchor="end" '
                     f'class="pointlabel">{_esc(point_fmt(values[-1]))}{_esc(unit)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def grouped_bars(items, *, width=760, height=210) -> str:
    """전주(회색) 대비 금주(파랑). items = [(라벨, 전주, 금주), ...]"""
    pad_l, pad_r, pad_t, pad_b = 46, 14, 22, 30
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    vmax = _nice_max(max([max(p, c) for _, p, c in items] + [0]) * 1.2)
    slot = w / max(len(items), 1)
    bw = min(26, slot / 3.2)

    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">']
    for frac in (0, 0.5, 1):
        y = pad_t + h - h * frac
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+w}" y2="{y:.1f}" '
                     f'stroke="#eef2f7"/>')
        parts.append(f'<text x="{pad_l-8}" y="{y+4:.1f}" text-anchor="end" class="axis">'
                     f'{vmax*frac:,.0f}</text>')
    for i, (label, prev, cur) in enumerate(items):
        cx = pad_l + slot * (i + 0.5)
        for j, (v, color) in enumerate(((prev, GRAY), (cur, BLUE))):
            bh = h * (v / vmax) if vmax else 0
            x = cx - bw * (1.05 if j == 0 else -0.05)
            parts.append(f'<rect x="{x:.1f}" y="{pad_t+h-bh:.1f}" width="{bw:.1f}" '
                         f'height="{max(bh,0.8):.1f}" fill="{color}" rx="2"/>')
        parts.append(f'<text x="{cx:.1f}" y="{pad_t+h-h*(cur/vmax if vmax else 0)-7:.1f}" '
                     f'text-anchor="middle" class="pointlabel">{cur:,.0f}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{height-9}" text-anchor="middle" class="axis">'
                     f'{_esc(label)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def hbars(items, *, width=560, row_h=34, label_w=104, color=BLUE, alt_color=None,
          value_fmt=None) -> str:
    """가로 막대. items = [(라벨, 값, 오른쪽에 적을 글자), ...]

    막대 뒤에 연한 트랙을 깔아 **0 인 항목도 자리를 차지하게** 한다.
    값이 0 이면 막대가 사라져서 항목 자체가 없는 것처럼 보이기 때문이다.
    """
    value_fmt = value_fmt or (lambda v: f"{v:,.0f}")
    n = len(items)
    height = max(row_h * n + 10, 40)
    track_x = label_w + 8
    track_w = width - track_x - 96
    vmax = max([v for _, v, _ in items] + [0]) or 1

    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">']
    for i, (label, value, right) in enumerate(items):
        y = 6 + row_h * i
        bar = track_w * (value / vmax)
        c = alt_color if (alt_color and i >= n // 2 and False) else color
        parts.append(f'<text x="{label_w}" y="{y+16}" text-anchor="end" class="hlabel">'
                     f'{_esc(label)}</text>')
        parts.append(f'<rect x="{track_x}" y="{y+4}" width="{track_w}" height="16" '
                     f'fill="#f1f5f9" rx="3"/>')
        parts.append(f'<rect x="{track_x}" y="{y+4}" width="{max(bar,1):.1f}" height="16" '
                     f'fill="{c}" rx="3"/>')
        parts.append(f'<text x="{track_x+track_w+8}" y="{y+17}" class="hvalue">'
                     f'{_esc(right if right is not None else value_fmt(value))}</text>')
    parts.append("</svg>")
    return "".join(parts)
