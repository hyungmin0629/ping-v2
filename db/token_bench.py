"""
위키 구조의 토큰 실측 — 2026-07-31 의 측정을 재현하고 다시 잰다.

    python db/token_bench.py                 # 두 시점 비교
    python db/token_bench.py --window 15,25,40   # 읽기 창 민감도까지

──────────────────────────────────────────────────────────────────────
**무엇을 재나.** 같은 질문에 답하기 위해 읽어야 하는 토큰이다.
2026-07-31 에 다섯 경로를 쟀고(A~E), 공정한 비교는 **B 대 D** 였다.

    A 통째로 읽기        쪼개기 전에 실제로 하던 것
    B grep + 구간 읽기   **쪼개기 전에도 가능했던 것** ← 기준선
    D grep + 정확한 노드 **쪼갠 뒤 하게 되는 것**     ← 비교 대상
    E grep + 매칭 전부   규율이 무너졌을 때 (참고용)

그때 결과는 B 1,928 · D 1,263 → **34% 절감**이었다.

**왜 다시 재나.** 결정이 56개에서 91개로 늘었다. 노드가 늘면 grep 에
걸리는 파일도 늘어서(D 의 파일 목록이 길어지고, B 의 한 파일은 더 두꺼워진다)
절감률이 어느 쪽으로든 움직인다. 구조를 유지할 이유가 아직 있는지 확인한다.

──────────────────────────────────────────────────────────────────────
⚠️ **두 시점을 같은 자로 잰다.** 옛 숫자(1,263·1,928)가 어떤 토크나이저로
   나왔는지 기록이 없다. 그래서 옛 상태를 git 에서 꺼내 **오늘의 토크나이저로
   다시 잰다.** 절대값을 옛 기록과 직접 비교하지 않고, 두 시점을 서로 비교한다.

⚠️ **B 의 '구간'은 창 크기가 정한다.** 한 파일에서는 결정의 경계를 모르므로
   읽을 범위를 찍어야 한다. 한 값에 기대지 않도록 여러 창을 함께 잰다.
   (경계를 모른다는 것 자체가 B 의 비용이라는 게 원래 관찰이었다.)
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DEC = ROOT / "docs" / "decisions"

# 2026-07-31 측정에 쓴 질문 다섯. 같은 것을 쓴다.
#   grep_term  : 에이전트가 실제로 칠 낱말 (한글)
#   slug_hint  : 파일명만 보고 고를 때의 단서 (슬러그는 ASCII 다)
QUERIES = [
    ("하트 경제",   "하트",   ("heart",)),
    ("친구 끊기",   "친구",   ("friend",)),
    ("합성 데이터", "합성",   ("synthetic",)),
    ("증분 함정",   "증분",   ("incremental", "bigquery", "watermark", "backfill")),
    ("힌트 요금",   "힌트",   ("hint",)),
]

# 그때 상태(위키 전환 직후 56 노드) vs 지금
STATES = [
    ("2026-07-31 · 56 노드", "9a10db0"),
    ("2026-08-25 · 91 노드", None),        # None 이면 작업 트리
]


# ---------------------------------------------------------------------
def encoder():
    """tiktoken 이 있으면 그것, 없으면 글자 기반 근사.

    ⚠️ 어느 쪽이든 **두 시점에 같은 자를 대는 것**이 목적이다. 절대값을
       다른 도구의 숫자와 견주지 않는다.
    """
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return (lambda s: len(enc.encode(s))), "tiktoken/cl100k_base"
    except ImportError:
        # 한글은 대략 1.5자/토큰, ASCII 는 4자/토큰. 거친 근사다.
        def approx(s: str) -> int:
            ko = sum(1 for c in s if "가" <= c <= "힣")
            return int(ko / 1.5 + (len(s) - ko) / 4)
        return approx, "근사(글자수)"


def materialize(ref: str | None) -> tuple[Path, Path | None]:
    """그 시점의 docs/decisions 를 꺼낸다. 작업 트리면 그대로 쓴다."""
    if ref is None:
        return DEC, None
    tmp = Path(tempfile.mkdtemp(prefix="token_bench_"))
    out = subprocess.run(
        ["git", "archive", ref, "docs/decisions"],
        cwd=ROOT, capture_output=True,
    )
    if out.returncode != 0:
        sys.exit(f"git archive 실패: {out.stderr.decode('utf-8', 'replace')[:200]}")
    (tmp / "archive.tar").write_bytes(out.stdout)
    shutil.unpack_archive(tmp / "archive.tar", tmp, format="tar")
    return tmp / "docs" / "decisions", tmp


def strip_frontmatter(text: str) -> str:
    return re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)


def single_file(nodes: list[Path]) -> str:
    """쪼개지 않았다면 있었을 한 파일. 노드 본문을 이어 붙인다."""
    return "\n\n".join(strip_frontmatter(p.read_text(encoding="utf-8")) for p in sorted(nodes))


# ---------------------------------------------------------------------
def measure(nodes_dir: Path, term: str, hints: tuple[str, ...], tok, window: int) -> dict:
    nodes = sorted(nodes_dir.glob("*.md"))
    merged = single_file(nodes)
    lines = merged.split("\n")

    # ── A · 한 파일을 통째로 ────────────────────────────────────────
    a = tok(merged)

    # ── D · 파일명만 받고 정확한 노드 하나 ──────────────────────────
    #    B 가 어느 구간을 읽을지 정하려면 목표 결정을 먼저 골라야 하므로 D 가 앞에 온다.
    matched = [p for p in nodes if term in p.read_text(encoding="utf-8")]
    list_out = "\n".join(f"docs/decisions/{p.name}" for p in matched)
    picked = next((p for p in matched if any(h in p.stem for h in hints)), None)
    if picked is None:
        picked = matched[0] if matched else None
    d = tok(list_out) + (tok(picked.read_text(encoding="utf-8")) if picked else 0)

    # ── B · 한 파일에서 grep 하고 **그 구간 하나만** ────────────────
    #    에이전트가 보는 것: grep 출력(줄번호+본문) 전체 + 찍은 창 하나.
    #
    #    ⚠️ **D 와 같은 결정을 목표로 삼는다.** 같은 답을 얻는 비용을 견주는
    #       것이므로, D 가 노드 하나를 읽으면 B 도 구간 하나를 읽어야 한다.
    #       매칭을 전부 읽는 경우는 E 다 — 그것을 B 에 섞으면 B 가 부풀려져
    #       절감률이 실제보다 좋게 나온다(2026-08-25 에 실제로 그렇게 짰다가 고쳤다).
    hits = [i for i, ln in enumerate(lines) if term in ln]
    grep_out = "\n".join(f"DECISIONS.md:{i+1}:{lines[i]}" for i in hits)
    target = hits[0] if hits else 0
    if picked is not None:
        body = strip_frontmatter(picked.read_text(encoding="utf-8")).split("\n")
        anchor = next((ln for ln in body if term in ln), None)
        if anchor is not None:
            target = next((i for i in hits if lines[i] == anchor), target)
    lo, hi = max(0, target - window), min(len(lines), target + window + 1)
    b = tok(grep_out) + tok("\n".join(lines[lo:hi]))

    # ── E · 매칭된 노드를 전부 (규율이 무너진 경우) ─────────────────
    e = tok(list_out) + sum(tok(p.read_text(encoding="utf-8")) for p in matched)

    return {"A": a, "B": b, "D": d, "E": e,
            # D 를 둘로 쪼개 둔다. 노드가 더 늘면 **파일 목록 쪽이 먼저 커진다** —
            # 흔한 낱말 하나가 위키 절반에 걸리기 시작하면 그때가 한계다.
            "D_list": tok(list_out),
            "D_node": d - tok(list_out),
            "hits": len(hits), "files": len(matched),
            "picked": picked.name if picked else "—"}


# 세 단계. 개편 전은 노드가 아예 없어서 위의 A~E 경로를 잴 수 없다 —
# 읽을 것이 `DECISIONS.md` 한 파일뿐이었다.
STAGES = [
    ("개편 전",   "pre-wiki", "2026-07-30"),
    ("개편 직후", "9a10db0",  "2026-07-31"),
    ("현재",      None,       "2026-08-25"),
]


def git_show(ref: str | None, path: str) -> str | None:
    """그 시점의 파일 하나. ref 가 None 이면 작업 트리."""
    if ref is None:
        f = ROOT / path
        return f.read_text(encoding="utf-8") if f.exists() else None
    out = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True)
    return out.stdout.decode("utf-8", "replace") if out.returncode == 0 else None


def stages(tok, window: int) -> None:
    """세 단계 비교 — **매 세션 고정비**와 **결정 하나를 찾는 비용**.

    ⚠️ 개편 전에는 D(골라 읽기) 경로가 존재하지 않았다. 노드가 없었기 때문이다.
       그래서 '그때 실제로 하던 것'과 '같은 방법으로 맞춘 비교'를 나눠 싣는다.
    """
    print("=" * 74)
    print("■ 세 단계 — 매 세션 고정비 (CLAUDE.md · 모든 세션이 무조건 지불한다)")
    print("=" * 74)
    base = None
    for label, ref, when in STAGES:
        n = tok(git_show(ref, "CLAUDE.md") or "")
        base = base if base is not None else n
        print(f"  {label:<10} {when}   {n:>8,} 토큰   ({100*(n-base)/base:+.0f}%)")

    print()
    print("=" * 74)
    print("■ 세 단계 — 결정 하나를 알기 위해 읽는 토큰")
    print("=" * 74)
    for label, ref, when in STAGES:
        if ref == "pre-wiki":
            whole = tok(git_show(ref, "DECISIONS.md") or "")
            print(f"  {label:<10} {when}   실제로 하던 것(통째로 읽기) {whole:>8,}")
            continue
        nodes_dir, tmp = materialize(ref)
        vals = [measure(nodes_dir, term, hints, tok, window)
                for _, term, hints in QUERIES]
        d = sum(v["D"] for v in vals) / len(vals)
        b = sum(v["B"] for v in vals) / len(vals)
        print(f"  {label:<10} {when}   골라 읽기 {d:>8,.0f}   "
              f"(한 파일이었다면 grep {b:,.0f})")
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", default="25",
                    help="B 경로의 읽기 창(줄). 쉼표로 여러 개")
    ap.add_argument("--stages", action="store_true",
                    help="개편 전 · 직후 · 현재 세 단계만 본다")
    args = ap.parse_args()
    windows = [int(w) for w in args.window.split(",")]

    tok, tok_name = encoder()
    print(f"토크나이저: {tok_name}\n")

    if args.stages:
        stages(tok, windows[0])
        return 0

    for window in windows:
        print("=" * 74)
        print(f"■ B 경로 읽기 창 ±{window}줄")
        print("=" * 74)
        summary = []
        for label, ref in STATES:
            nodes_dir, tmp = materialize(ref)
            rows = []
            for name, term, hints in QUERIES:
                r = measure(nodes_dir, term, hints, tok, window)
                rows.append((name, r))
            n_nodes = len(list(nodes_dir.glob("*.md")))

            print(f"\n{label}  (노드 {n_nodes}개)")
            print(f"  {'질문':<12} {'매칭':>6} {'A 통째':>9} {'B 구간':>9} "
                  f"{'D 노드':>9} {'E 전부':>9}   고른 노드")
            for name, r in rows:
                print(f"  {name:<12} {r['files']:>4}개 {r['A']:>9,} {r['B']:>9,} "
                      f"{r['D']:>9,} {r['E']:>9,}   {r['picked']}")
            keys = ["A", "B", "D", "E", "D_list", "D_node"]
            avg = {k: sum(r[k] for _, r in rows) / len(rows) for k in keys}
            avg["files"] = sum(r["files"] for _, r in rows) / len(rows)
            print(f"  {'평균':<12} {avg['files']:>4.0f}개 {avg['A']:>9,.0f} {avg['B']:>9,.0f} "
                  f"{avg['D']:>9,.0f} {avg['E']:>9,.0f}")
            cut = 100 * (avg["B"] - avg["D"]) / avg["B"]
            print(f"  → B 대비 D 절감 {cut:.1f}%   "
                  f"(E 는 B 의 {avg['E']/avg['B']:.1f}배)")
            print(f"    D 의 구성: 파일 목록 {avg['D_list']:,.0f} "
                  f"({100*avg['D_list']/avg['D']:.0f}%) + 노드 본문 {avg['D_node']:,.0f}")
            summary.append((label, avg, cut))
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)

        print("\n" + "-" * 74)
        (l0, a0, c0), (l1, a1, c1) = summary
        print(f"  {l0}: B {a0['B']:,.0f} → D {a0['D']:,.0f}  ({c0:.1f}% 절감)")
        print(f"  {l1}: B {a1['B']:,.0f} → D {a1['D']:,.0f}  ({c1:.1f}% 절감)")
        print(f"  절감률 변화: {c0:.1f}% → {c1:.1f}%  ({c1-c0:+.1f}%p)")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
