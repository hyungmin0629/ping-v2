"""
docs/index.md 를 다시 만든다 — 위키 전체 목록. (2계층)

왜 스크립트인가:
    손으로 관리하는 목록은 반드시 낡는다. 오늘(2026-07-31) 문서 점검에서
    CLAUDE.md 의 "비어 있는 테이블" 목록이 실제와 어긋나 있던 것이 그 예다.
    문서가 5개일 때는 손으로 되지만 60개가 넘으면 안 된다.

무엇을 훑나:
    raw/       원본. 회의록·리포트·외부 자료 (읽기 전용)
    docs/      위키. 결정·운영·생성물

frontmatter 의 title 을 제목으로 쓰고, 없으면 첫 `# 제목` 을 쓴다.

사용법:
    python db/wiki_index.py            # docs/index.md 갱신
    python db/wiki_index.py --check    # 갱신이 필요한지만 알려준다 (lint 용)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "index.md"

# (폴더, 제목, 설명). 순서가 곧 색인 순서다.
SECTIONS = [
    ("raw/meetings",         "회의록",     "팀 회의 원본. 고치지 않는다."),
    ("raw/legacy-analysis",  "구 서비스 분석", "이 프로젝트가 시작된 근거. 2026-07-28 조사."),
    ("raw/external",         "외부 자료",   "API 스펙 등 바깥에서 온 문서."),
    ("docs/decisions",       "결정",       "왜 그렇게 했는지. 하나가 한 노드다."),
    ("docs/ops",             "운영 참조",   "실제로 그 작업을 할 때 필요한 값과 절차."),
]

# 폴더에 안 들어가는 낱장 문서
LOOSE = [
    ("CLAUDE.md",           "프로젝트 규약",  "에이전트가 매번 읽는다. 위키 구조와 워크플로."),
    ("README.md",           "저장소 소개",   "무엇을 만드는 프로젝트인가."),
    ("DECISIONS.md",        "결정 색인",     "결정 노드 56개 목록."),
    ("docs/design-spec.md", "설계 명세",     "통독용. 배경·목표·단계."),
    ("docs/ONBOARDING.md",  "온보딩",       "저장소를 처음 받은 사람용."),
    ("docs/TEAM-PLAN.md",   "팀 작업 절차",  "협업·스키마 변경 영향 범위."),
    ("docs/erd.md",         "ERD (생성물)",  "`db/erd.py` 가 살아 있는 DB 에서 뽑는다."),
    ("docs/log.md",         "작업 이력",     "위키에 무엇을 언제 했나."),
]

SKIP = {"index.md", "_template.md"}


def title_of(path: Path) -> tuple[str, str]:
    """(제목, 한 줄 요약). frontmatter 를 먼저 보고 없으면 본문에서 찾는다."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return path.stem, ""
    title = ""
    if m := re.match(r"^---\n(.*?)\n---\n", text, re.S):
        if t := re.search(r"^title:\s*(.+)$", m.group(1), re.M):
            title = t.group(1).strip()
        body = text[m.end():]
    else:
        body = text
    if not title:
        title = h.group(1).strip() if (h := re.search(r"^#\s+(.+)$", body, re.M)) else path.stem
    # 제목 다음의 첫 산문 줄을 요약으로 쓴다
    summary = ""
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", ">", "|", "-", "*", "`", "---")):
            continue
        summary = re.sub(r"[*`\[\]]|\(\S+\)", "", s)[:78]
        break
    return title, summary


def build() -> str:
    out = [
        "---",
        "title: 위키 색인",
        "group: 위키",
        "tags: [위키, 색인]",
        "---",
        "",
        "# 위키 색인",
        "",
        "이 저장소의 문서 전체 목록이다. **손으로 고치지 않는다** —",
        "`python db/wiki_index.py` 가 다시 만든다.",
        "",
        "문서는 세 층이다. 자세한 것은 [[CLAUDE|CLAUDE.md]] 의 *위키 구조*.",
        "",
        "| 층 | 무엇 | 고치는 주체 |",
        "|---|---|---|",
        "| 1 | `raw/` 원본 — 회의록·분석·외부 자료 | **사람만** |",
        "| 2 | `docs/` 위키 — 원본과 코드에서 뽑아 만든 것 | 에이전트 |",
        "| 3 | `CLAUDE.md` 규약 — 그 일을 어떻게 하는지 | 사람 + 에이전트 |",
        "",
    ]

    out += ["## 낱장 문서", ""]
    for rel, label, note in LOOSE:
        p = ROOT / rel
        if not p.exists():
            continue
        out.append(f"- [[{p.stem}|{label}]] — {note}")
    out.append("")

    total = 0
    for folder, label, note in SECTIONS:
        d = ROOT / folder
        files = sorted(p for p in d.glob("*.md") if p.name not in SKIP) if d.exists() else []
        out += [f"## {label} <sub>`{folder}` · {len(files)}</sub>", "", note, ""]
        if not files:
            out += ["_아직 없다._", ""]
            continue
        total += len(files)
        for p in files:
            title, summary = title_of(p)
            line = f"- [[{p.stem}|{title}]]"
            if summary:
                line += f" — {summary}"
            out.append(line)
        out.append("")

    out += ["---", "",
            f"문서 {total + len([r for r, _, _ in LOOSE if (ROOT / r).exists()])}개 · "
            f"`python db/wiki_index.py` 로 갱신"]
    return "\n".join(out) + "\n"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="갱신이 필요한지만 본다")
    args = ap.parse_args()

    fresh = build()
    old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
    if args.check:
        if fresh != old:
            print("★ docs/index.md 가 낡았습니다 — python db/wiki_index.py")
            return 1
        print("  docs/index.md 최신")
        return 0

    OUT.write_text(fresh, encoding="utf-8")
    print(f"생성 완료 — {OUT.relative_to(ROOT)}")
    for folder, label, _ in SECTIONS:
        d = ROOT / folder
        n = len([p for p in d.glob("*.md") if p.name not in SKIP]) if d.exists() else 0
        print(f"  {label:<14}{n:>3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
