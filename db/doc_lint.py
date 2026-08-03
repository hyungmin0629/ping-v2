"""
문서가 하는 주장을 살아 있는 실제와 대조한다. (위키의 lint 연산)

왜 필요한가:
    이 저장소의 "진실"은 DDL·스크립트·살아 있는 DB 이고, 문서는 그것을 가리킨다.
    그런데 코드는 매 커밋 바뀌고 **문서는 조용히 낡는다.** 오류가 안 난다.

    2026-07-31 에 손으로 점검했더니 낡은 주장이 9곳 나왔다 —
    테이블 수, 시험 항목 수, 단계 표의 순서, 비어 있는 표 목록.
    다음에도 손으로 하면 또 놓치므로 스크립트로 옮긴다.

무엇을 보나:
    1  숫자   테이블·컬럼·FK·마이그레이션 수를 DB·파일시스템과 대조
    2  이름   사라진 표 이름이 현재형으로 남아 있는가
    3  링크   [[링크]] 가 실제 파일을 가리키는가
    4  파일   문서가 언급하는 스크립트가 실제로 있는가
    5  색인   docs/index.md 가 최신인가
    6  원본   raw/ 에 반영 안 된 회의록이 있는가

사용법:
    python db/doc_lint.py              # 전부
    python db/doc_lint.py --offline    # DB 없이 (숫자 검사 일부 생략)
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 이 문서들만 본다. raw/ 는 원본이라 낡아도 고치지 않는다.
DOCS = ["CLAUDE.md", "README.md", "DECISIONS.md",
        "docs/design-spec.md", "docs/ONBOARDING.md", "docs/TEAM-PLAN.md"]

# 사라진 이름. 이력을 말하는 자리(→, 없앴다, 삭제, 지운, 당시)는 봐준다.
GONE = ["admin_user", "external_sync_log", "sync_resource", "sync_status"]
HISTORY_HINT = re.compile(
    r"→|없앴|삭제|지운|지웠|폐기|당시|한때|이제 없|더 이상|지금은|나머지|W0 조정|W1[789]|~~|\[\[")


def md_files() -> list[Path]:
    return [p for p in ROOT.rglob("*.md")
            if ".venv" not in str(p) and "node_modules" not in str(p)]


def live_counts() -> dict[str, int] | None:
    """살아 있는 DB 에서 진짜 값을 읽는다. 못 붙으면 None."""
    try:
        from dotenv import load_dotenv
        import psycopg
    except ImportError:
        return None
    load_dotenv(ROOT / ".env")
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        return None
    try:
        with psycopg.connect(url, connect_timeout=15) as conn, conn.cursor() as cur:
            cur.execute("""SELECT count(*) FROM information_schema.tables
                            WHERE table_schema='public' AND table_type='BASE TABLE'""")
            tables = cur.fetchone()[0]
            cur.execute("""SELECT count(*) FROM information_schema.columns c
                             JOIN information_schema.tables t USING(table_schema,table_name)
                            WHERE c.table_schema='public' AND t.table_type='BASE TABLE'""")
            cols = cur.fetchone()[0]
            cur.execute("""SELECT count(*) FROM pg_constraint
                            WHERE contype='f' AND connamespace='public'::regnamespace""")
            fks = cur.fetchone()[0]
        return {"테이블": tables, "컬럼": cols, "FK": fks}
    except Exception:
        return None


def verify_item_count() -> int | None:
    """verify.py 가 실제로 몇 항목을 찍는지 센다. 느려서 기본은 건너뛴다."""
    try:
        r = subprocess.run([sys.executable, str(ROOT / "db" / "rls" / "verify.py")],
                           capture_output=True, text=True, encoding="utf-8", timeout=600)
        return len(re.findall(r"^  (동작함|막힘|깨끗함) ", r.stdout, re.M)) or None
    except Exception:
        return None


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--with-verify", action="store_true",
                    help="verify.py 를 실제로 돌려 항목 수까지 대조 (느리다)")
    args = ap.parse_args()

    problems: list[str] = []      # 반드시 고쳐야 하는 것 (반환 1)
    notes: list[str] = []         # 사람이 판단할 것 (반환 0)

    def bad(msg: str) -> None:
        problems.append(msg)
        print(f"  ★ {msg}")

    def note(msg: str) -> None:
        # 숫자와 이름은 이력 서술과 구별이 어렵다. 알리되 막지는 않는다.
        notes.append(msg)
        print(f"  · {msg}")

    # ── 1. 숫자 ────────────────────────────────────────────────
    print("1. 숫자 주장")
    truth = None if args.offline else live_counts()
    if truth is None:
        print("  건너뜀 — DB 에 붙지 못했습니다")
    else:
        pats = [(r"(\d+)\s*개?\s*테이블", "테이블"), (r"(\d+)\s*컬럼", "컬럼"), (r"FK\s*(\d+)", "FK")]
        for d in DOCS:
            p = ROOT / d
            if not p.exists():
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if HISTORY_HINT.search(line):
                    continue
                for pat, kind in pats:
                    for m in re.finditer(pat, line):
                        v = int(m.group(1))
                        if v > 3 and v != truth[kind] and abs(v - truth[kind]) < 25:
                            note(f"{d}:{i} {kind}={v} (실제 {truth[kind]}) — {line.strip()[:60]}")
        if args.with_verify:
            n = verify_item_count()
            if n:
                for d in DOCS:
                    p = ROOT / d
                    if not p.exists():
                        continue
                    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                        if HISTORY_HINT.search(line):
                            continue
                        for m in re.finditer(r"(\d+)\s*항목", line):
                            if int(m.group(1)) != n:
                                note(f"{d}:{i} 시험={m.group(1)} (실제 {n})")
        if not notes:
            print("  깨끗함")

    # ── 2. 사라진 이름 ─────────────────────────────────────────
    print("2. 사라진 이름이 현재형으로 남아 있는가")
    before = len(notes)
    for d in DOCS:
        p = ROOT / d
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if HISTORY_HINT.search(line):
                continue
            for g in GONE:
                if g in line:
                    note(f"{d}:{i} `{g}` — {line.strip()[:60]}")
    if len(notes) == before:
        print("  깨끗함")

    # ── 3. 링크 ────────────────────────────────────────────────
    print("3. [[링크]] 가 실제 파일을 가리키는가")
    before = len(problems)
    # 옵시디언은 [[이름]](파일명)과 [[폴더/이름]](볼트 상대경로) 둘 다 받는다.
    # 이름이 겹칠 때는 경로를 붙여야 하므로 두 형태를 모두 인정한다.
    names = {p.stem for p in md_files()}
    names |= {p.relative_to(ROOT).with_suffix("").as_posix() for p in md_files()}
    for p in md_files():
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for m in re.finditer(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", line):
                if m.group(1) not in names:
                    bad(f"{p.relative_to(ROOT)}:{i} [[{m.group(1)}]] 대상 없음")
    if len(problems) == before:
        print("  깨끗함")

    # ── 4. 언급된 스크립트가 실재하는가 ────────────────────────
    print("4. 문서가 부르는 스크립트가 실재하는가")
    before = len(problems)
    for p in md_files():
        if "raw" in p.parts:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for m in re.finditer(r"python\s+((?:db|pipeline|generator|qa)/[\w/]+\.py)", line):
                if not (ROOT / m.group(1)).exists():
                    bad(f"{p.relative_to(ROOT)}:{i} {m.group(1)} 없음")
    if len(problems) == before:
        print("  깨끗함")

    # ── 5. 색인 ────────────────────────────────────────────────
    print("5. 생성물이 최신인가 (색인 · 테이블 페이지)")
    for script, what in (("wiki_index.py", "docs/index.md"),
                         ("wiki_tables.py", "docs/tables/")):
        r = subprocess.run([sys.executable, str(ROOT / "db" / script), "--check"],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            bad(f"{what} 가 낡음 — python db/{script}")
    if not any(w in p for p in problems for w in ("index.md", "tables/")):
        print("  깨끗함")

    # ── 6. 반영 안 된 원본 ─────────────────────────────────────
    print("6. raw/ 에 반영 안 된 회의록이 있는가")
    before = len(problems)
    for p in sorted((ROOT / "raw" / "meetings").glob("*.md")):
        if p.name.startswith("_"):
            continue
        if re.search(r"^ingested:\s*false\s*$", p.read_text(encoding="utf-8"), re.M | re.I):
            bad(f"{p.relative_to(ROOT)} 아직 반영 안 됨 — 읽고 위키에 옮길 것")
    if len(problems) == before:
        print("  깨끗함")

    # ── 7. 없는 질문 번호를 가리키는가 ─────────────────────────
    # 질문 번호(Q12 같은)는 **위치 기반 식별자**라 문서에서 질문을 지우면
    # 그걸 인용한 곳이 전부 조용히 깨진다. 오류가 안 나서 더 위험하다.
    # 실제로 Q31~Q47 을 지운 뒤 다른 문서 4개가 그 번호를 계속 가리키고 있었다.
    print("7. 없는 질문 번호를 가리키는가")
    before = len(problems)
    qdoc = ROOT / "docs" / "synthetic-v2-decisions.md"
    if qdoc.exists():
        live = {int(m) for m in re.findall(r"^### (?:⚠️ )?(?:추가질문 )?Q(\d+)\.",
                                           qdoc.read_text(encoding="utf-8"), re.M)}
        if live:
            for p in md_files() + sorted((ROOT / "docs").glob("*.html")):
                if p.name == qdoc.name:
                    text = qdoc.read_text(encoding="utf-8")
                    # 자기 문서에서는 제목 줄을 빼고 본다
                    text = re.sub(r"^### .*$", "", text, flags=re.M)
                else:
                    text = p.read_text(encoding="utf-8")
                dead = {int(n) for n in re.findall(r"\bQ(\d+)\b", text)} - live
                if dead:
                    bad(f"{p.relative_to(ROOT)} 가 없는 질문 "
                        f"{', '.join('Q'+str(n) for n in sorted(dead))} 를 가리킴")
    if len(problems) == before:
        print("  깨끗함")

    # ── 8. 결정 없이 코드만 쌓이지 않았는가 ─────────────────────
    # 규약은 "설계 결정이 내려지면 docs/decisions/ 에 노드를 만든다"인데,
    # 지키는지 보는 장치가 없었다. 실제로 2026-08-03 합성 데이터 작업에서
    # **아홉 번 연속으로 건너뛰었다** — 근거가 커밋 메시지와 설정 주석에만
    # 흩어져 DECISIONS 색인으로는 찾을 수 없었다. query 연산이 그 폴더를
    # grep 하므로 사실상 없는 것과 같다.
    #
    # ⚠️ 실패(★)로 두지 않는다. "결정이 정말 없었다"와 "적기를 잊었다"는
    #    기계가 구별하지 못한다. 실패로 두면 늘 빨간불이 되고, 그러면 검사
    #    자체를 안 보게 된다. 숫자·이름 검사와 같은 이유다.
    print("8. 결정 없이 코드만 쌓이지 않았는가")
    LIMIT = 8
    WATCH = ["db/", "generator/", "pipeline/", "web/"]
    try:
        last = subprocess.run(
            ["git", "log", "-1", "--diff-filter=A", "--format=%H", "--", "docs/decisions/"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.strip()
        rng = f"{last}..HEAD" if last else "HEAD"
        out = subprocess.run(
            ["git", "log", rng, "--format=%h %s", "--"] + WATCH,
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.strip()
        commits = [l for l in out.splitlines() if l.strip()]
        if len(commits) > LIMIT:
            note(f"마지막 결정 노드 이후 코드 커밋 {len(commits)}개 "
                 f"(기준 {LIMIT}) — 적어야 할 결정이 있었는지 본다")
            for c in commits[:5]:
                print(f"      {c}")
            if len(commits) > 5:
                print(f"      … 외 {len(commits) - 5}개")
        else:
            print(f"  깨끗함 (마지막 결정 이후 코드 커밋 {len(commits)}개)")
    except Exception as e:                      # git 이 없거나 저장소가 아닐 때
        print(f"  건너뜀 — git 을 읽지 못함 ({e})")

    # ── 9. 결정 노드가 색인에서 빠지지 않았는가 ──────────────────
    # 노드 파일이 있어도 DECISIONS.md 에 줄이 없으면 **사실상 없는 노드**다.
    # query 연산이 색인을 거쳐 찾기 때문이다. 실제로 `group: 웹앱` 인 노드 3개가
    # **색인에 그 절 자체가 없어서** 통째로 빠져 있었다(2026-08-03 에 발견).
    print("9. 결정 노드가 색인에서 빠지지 않았는가")
    before = len(problems)
    idx_path = ROOT / "DECISIONS.md"
    dec_dir = ROOT / "docs" / "decisions"
    if idx_path.exists() and dec_dir.exists():
        idx = idx_path.read_text(encoding="utf-8")
        sections = set(re.findall(r"^## (.+)$", idx, re.M))
        missing, groups = [], set()
        for f in sorted(dec_dir.glob("*.md")):
            body = f.read_text(encoding="utf-8")
            if f"[[{f.stem}" not in idx:
                missing.append(f.stem)
            m = re.search(r"^group:\s*(.+?)\s*$", body, re.M)
            if m:
                groups.add(m.group(1))
        for name in missing:
            bad(f"{name} 이 DECISIONS.md 색인에 없음 — 노드가 있어도 못 찾는다")
        # 절이 없는 그룹은 노드가 통째로 빠지는 원인이 된다
        for g in sorted(groups - sections):
            if not any(g in s for s in sections):
                bad(f"group '{g}' 에 해당하는 절이 DECISIONS.md 에 없음")
    if len(problems) == before:
        print("  깨끗함")

    print()
    print("=" * 60)
    if notes:
        print(f"살펴볼 것 {len(notes)}건 — 이력 서술이면 그대로 두면 된다")
    if problems:
        print(f"고쳐야 할 것 {len(problems)}건")
        return 1
    print("문서가 실제와 맞습니다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
