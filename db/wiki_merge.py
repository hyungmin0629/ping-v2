"""
위키를 되돌린다 — 결정 노드를 DECISIONS.md 한 파일로 합친다.

언제 쓰나:
    노드로 쪼갠 뒤 **오히려 토큰을 더 쓰거나** 답이 나빠지면 되돌린다.
    실측으로는 골라 읽기가 이기지만(1,263 대 1,928), 매칭된 노드를 전부
    읽는 습관이 붙으면 6,907 로 오히려 나빠진다. 그 상태가 계속되면
    구조를 유지할 이유가 없다.

왜 `git revert` 로 하면 안 되나:
    되돌리는 커밋 이후에 쓴 결정이 **함께 사라진다.** 위키로 바꾼 뒤
    새로 적은 결정은 노드 파일로만 존재하기 때문이다.
    이 스크립트는 **지금 있는 노드 전부**를 읽어 합치므로 그런 손실이 없다.

무엇을 되돌리고 무엇을 남기나:
    되돌린다   docs/decisions/ 56개 → DECISIONS.md 한 파일
    남긴다     raw/ (원본이라 되돌릴 성격이 아니다)
               db/doc_lint.py (한 파일이어도 쓸모가 있다)
               docs/tables/ (지우려면 폴더째 지우면 된다. 생성물이다)

사용법:
    python db/wiki_merge.py --dry-run     # 무엇이 합쳐지는지만 본다
    python db/wiki_merge.py               # DECISIONS.md 를 덮어쓴다
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DEC = ROOT / "docs" / "decisions"
OUT = ROOT / "DECISIONS.md"

HEAD = """# 결정 이력

설계 결정과 **그 이유**를 남긴다. 무엇을 했는지가 아니라 **왜 그렇게 했는지**,
그리고 **무엇을 버렸는지**. 스키마 구조나 코드 설명은 여기 적지 않는다 —
DDL과 스크립트가 진실이다.

형식: `## YYYY-MM-DD · 제목` → 결정 / 이유 / 대안 / 영향
"""


def parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    fm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    meta, body = ({}, text)
    if fm:
        for line in fm.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
        body = text[fm.end():]

    body = re.sub(r"^#\s+.+$", "", body, count=1, flags=re.M)          # 제목 줄
    body = re.sub(r"^>\s*⛔.*$", "", body, flags=re.M)                  # 대체 배너
    body = re.split(r"^## 이어지는 결정$", body, flags=re.M)[0]          # 교차 참조
    body = re.sub(r"\n---\n\s*`[^`]+`\s*·.*$", "", body, flags=re.S)    # 꼬리말
    return {
        "slug": path.stem,
        "title": meta.get("title", path.stem),
        "date": meta.get("date", ""),
        "status": meta.get("status", "active"),
        "superseded_by": meta.get("superseded_by", ""),
        "body": body.strip(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = sorted(DEC.glob("*.md"))
    if not files:
        print(f"★ {DEC} 에 결정 노드가 없습니다")
        return 1

    items = sorted((parse(p) for p in files), key=lambda d: (d["date"], d["slug"]))
    parts = [HEAD]
    for it in items:
        head = f"## {it['date']} · {it['title']}"
        if it["status"] == "superseded":
            # 한 파일로 돌아가도 뒤집힌 결정이 살아 있는 것처럼 보이면 안 된다
            head = f"## ~~{it['date']} · {it['title']}~~ *(대체됨)*"
        parts.append(head)
        if it["superseded_by"]:
            parts.append(f"→ 대체한 결정: **{it['superseded_by']}**")
        parts.append(it["body"])
    merged = "\n\n---\n\n".join(parts) + "\n"

    total = len(merged)
    print(f"결정 {len(items)}개 → 한 파일 {total:,}자")
    print(f"  대체된 것 {sum(1 for i in items if i['status'] == 'superseded')}개")
    if args.dry_run:
        print("\n--dry-run 이라 쓰지 않았습니다.")
        print("되돌리려면 이 명령을 --dry-run 없이 다시 돌리세요.")
        return 0

    backup = ROOT / f"DECISIONS.before-merge-{date.today():%Y%m%d}.md"
    if OUT.exists():
        shutil.copy2(OUT, backup)
        print(f"  색인을 {backup.name} 로 백업")
    OUT.write_text(merged, encoding="utf-8")
    print(f"\n{OUT.name} 을 덮어썼습니다.")
    print("남은 일 —")
    print("  1. docs/decisions/ 를 지운다 (합쳐졌으므로 두면 두 벌이 된다)")
    print("  2. CLAUDE.md 의 '위키 구조'·'세 가지 연산' 절을 정리한다")
    print("  3. python db/wiki_index.py 로 색인을 다시 만든다")
    print("  4. python db/doc_lint.py 로 끊어진 링크를 찾는다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
