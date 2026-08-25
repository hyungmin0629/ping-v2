"""
위키 링크 그래프를 그림으로 뽑는다 — `docs/img/wiki-graph.svg`.

    python db/wiki_graph.py
    python db/wiki_graph.py --min-degree 1   # 외톨이 노드까지

옵시디언 그래프 뷰와 **같은 데이터**를 본다(`[[위키링크]]`). 다른 점은 하나 —
이건 **재현 가능하다.** 스크린샷은 찍은 순간의 것이고 배치가 매번 달라지지만,
이 스크립트는 씨앗이 고정돼 있어 같은 그림을 다시 만든다. 보고서에 싣는 그림은
이쪽이어야 한다.

배치는 Fruchterman-Reingold(스프링) 방식을 직접 구현했다. 노드가 150개
남짓이라 라이브러리를 하나 더 들일 이유가 없다.

색은 갈래를 뜻한다 — 결정 · 운영 · 표 · 색인/규약. 크기는 연결 수다.
"""

from __future__ import annotations

import argparse
import math
import random
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "img" / "wiki-graph.svg"

LINK = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]")

# 갈래별 색. 옵시디언 볼트의 색 설정과 같은 뜻으로 맞춰 뒀다.
GROUPS = {
    "결정":   ("#3b6fd4", "docs/decisions"),
    "운영":   ("#2f9e5f", "docs/ops"),
    "표":     ("#2f6f6f", "docs/tables"),
    "원본":   ("#a2762f", "raw"),
    "색인":   ("#4a4a4a", None),      # CLAUDE.md · index · DECISIONS · README 등
}


def collect() -> tuple[dict[str, str], list[tuple[str, str]]]:
    """노드 이름 → 갈래, 그리고 링크 쌍."""
    files: list[Path] = []
    for pat in ("docs/**/*.md", "raw/**/*.md"):
        files += sorted(ROOT.glob(pat))
    files += [ROOT / "CLAUDE.md", ROOT / "DECISIONS.md", ROOT / "README.md"]

    group_of: dict[str, str] = {}
    edges: list[tuple[str, str]] = []

    for f in files:
        if not f.exists():
            continue
        rel = f.relative_to(ROOT).as_posix()
        name = f.stem
        g = "색인"
        for label, (_, prefix) in GROUPS.items():
            if prefix and rel.startswith(prefix):
                g = label
                break
        group_of[name] = g
        for target in LINK.findall(f.read_text(encoding="utf-8")):
            target = target.strip()
            if target and target != name:
                edges.append((name, target))

    # 링크만 되고 파일이 없는 대상도 노드로 둔다(옵시디언과 같은 동작).
    for _, dst in edges:
        group_of.setdefault(dst, "색인")
    return group_of, edges


def layout(nodes: list[str], edges: list[tuple[str, str]], *,
           w: float = 1000, h: float = 640, iters: int = 600, seed: int = 7):
    """스프링 배치. 씨앗을 고정해 **같은 그림이 다시 나오게** 한다."""
    rnd = random.Random(seed)
    idx = {n: i for i, n in enumerate(nodes)}
    pos = [[rnd.uniform(0, w), rnd.uniform(0, h)] for _ in nodes]
    k = math.sqrt(w * h / max(len(nodes), 1)) * 0.55
    pairs = [(idx[a], idx[b]) for a, b in edges if a in idx and b in idx]

    for step in range(iters):
        temp = (1 - step / iters) * w * 0.08 + 0.5
        disp = [[0.0, 0.0] for _ in nodes]
        # 밀어내기 — 모든 쌍
        for i in range(len(nodes)):
            xi, yi = pos[i]
            for j in range(i + 1, len(nodes)):
                dx, dy = xi - pos[j][0], yi - pos[j][1]
                d2 = dx * dx + dy * dy or 0.01
                f = (k * k) / d2
                disp[i][0] += dx * f; disp[i][1] += dy * f
                disp[j][0] -= dx * f; disp[j][1] -= dy * f
        # 당기기 — 링크된 쌍
        for a, b in pairs:
            dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
            d = math.hypot(dx, dy) or 0.01
            f = d / k
            disp[a][0] -= dx / d * f * k * 0.5; disp[a][1] -= dy / d * f * k * 0.5
            disp[b][0] += dx / d * f * k * 0.5; disp[b][1] += dy / d * f * k * 0.5
        for i in range(len(nodes)):
            dx, dy = disp[i]
            d = math.hypot(dx, dy) or 0.01
            # ⚠️ 경계로 자르지 않는다. 자르면 밀려난 노드가 테두리에 일렬로
            #    붙어서 **없는 구조가 그림에 생긴다.** 자유롭게 두고 마지막에
            #    전체를 화면에 맞춰 줄인다.
            pos[i][0] += dx / d * min(d, temp)
            pos[i][1] += dy / d * min(d, temp)
    return pos


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-degree", type=int, default=1,
                    help="이 수보다 연결이 적은 노드는 그리지 않는다")
    ap.add_argument("--label-top", type=int, default=14,
                    help="이름을 적을 상위 노드 수 (연결 많은 순)")
    ap.add_argument("--exclude", default="index",
                    help="뺄 노드(쉼표). 기본값 index — **생성 색인은 모든 노드를 "
                         "가리켜서** 그리면 그래프가 통째로 별 모양이 된다. "
                         "빼야 결정끼리의 구조가 보인다")
    args = ap.parse_args()

    group_of, edges = collect()
    drop = {x.strip() for x in args.exclude.split(",") if x.strip()}
    group_of = {n: g for n, g in group_of.items() if n not in drop}
    edges = [(a, b) for a, b in edges if a not in drop and b not in drop]
    deg: dict[str, int] = {n: 0 for n in group_of}
    for a, b in edges:
        deg[a] = deg.get(a, 0) + 1
        deg[b] = deg.get(b, 0) + 1

    nodes = [n for n in group_of if deg.get(n, 0) >= args.min_degree]
    keep = set(nodes)
    edges = [(a, b) for a, b in edges if a in keep and b in keep]
    edges = sorted({tuple(sorted(e)) for e in edges})  # 중복·방향 제거

    print(f"노드 {len(nodes)}개 · 링크 {len(edges)}개")
    counts: dict[str, int] = {}
    for n in nodes:
        counts[group_of[n]] = counts.get(group_of[n], 0) + 1
    for g, c in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {g:<4} {c:>4}")

    w, h = 1000.0, 640.0
    pos = layout(nodes, edges, w=w, h=h)

    # 배치 결과를 화면에 맞춘다. 스프링 배치는 경계를 모르므로 그냥 그리면
    # 가장자리 노드가 잘리고 가운데가 빈다.
    #    ⚠️ 최소~최대가 아니라 **백분위**로 맞춘다. 링크가 하나뿐인 노드 몇 개가
    #       멀리 튕겨 나가는데, 그것까지 담으려 하면 가운데 뭉치가 눌려 안 보인다.
    pad = 34.0

    def span(vals: list[float]) -> tuple[float, float]:
        v = sorted(vals)
        lo = v[int(len(v) * 0.03)]
        hi = v[min(len(v) - 1, int(len(v) * 0.97))]
        return lo, (hi - lo) or 1e-6

    xlo, xspan = span([p[0] for p in pos])
    ylo, yspan = span([p[1] for p in pos])
    sc = min((w - 2 * pad) / xspan, (h - 2 * pad) / yspan)
    cx = pad + ((w - 2 * pad) - xspan * sc) / 2
    cy = pad + ((h - 2 * pad) - yspan * sc) / 2
    pos = [[min(w - 8, max(8, cx + (x - xlo) * sc)),
            min(h - 8, max(8, cy + (y - ylo) * sc))] for x, y in pos]
    idx = {n: i for i, n in enumerate(nodes)}
    dmax = max(deg.values()) or 1

    top = sorted(nodes, key=lambda n: -deg[n])[:args.label_top]

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" '
             f'font-family="Malgun Gothic, sans-serif">',
             f'<rect width="{w:.0f}" height="{h:.0f}" fill="#ffffff"/>']
    for a, b in edges:
        x1, y1 = pos[idx[a]]; x2, y2 = pos[idx[b]]
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                     f'stroke="#c9d2dc" stroke-width="0.6" opacity="0.75"/>')
    for n in nodes:
        x, y = pos[idx[n]]
        r = 2.4 + 7.5 * math.sqrt(deg[n] / dmax)
        color = GROUPS[group_of[n]][0]
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{color}" '
                     f'stroke="#fff" stroke-width="0.7"/>')
    # 라벨은 겹치면 못 읽는다. 이미 적은 라벨과 가까우면 건너뛴다.
    placed: list[tuple[float, float]] = []
    for n in top:
        x, y = pos[idx[n]]
        if any(abs(x - px) < 96 and abs(y - py) < 15 for px, py in placed):
            continue
        placed.append((x, y))
        # 흰 테두리를 깔아 선 위에서도 읽히게 한다(paint-order)
        parts.append(f'<text x="{x:.1f}" y="{y - 10:.1f}" text-anchor="middle" '
                     f'font-size="11.5" font-weight="700" fill="#16324f" '
                     f'stroke="#ffffff" stroke-width="3.2" paint-order="stroke">{n}</text>')
    # 범례
    lx, ly = 14, 18
    for g, (color, _) in GROUPS.items():
        if g not in counts:
            continue
        parts.append(f'<circle cx="{lx+6}" cy="{ly-4}" r="5" fill="{color}"/>')
        parts.append(f'<text x="{lx+17}" y="{ly}" font-size="11.5" fill="#333">'
                     f'{g} {counts[g]}</text>')
        ly += 18
    parts.append("</svg>")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(parts), encoding="utf-8")
    print(f"✅ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
