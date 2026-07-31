"""
표 하나당 한 장 — docs/tables/<표>.md 를 만든다. (위키 2계층 · 엔티티 페이지)

왜 필요한가:
    표 하나를 이해하려면 지금 네 군데를 따로 열어야 한다.
      db/ddl/*.sql          이 표가 뭔지, 왜 이렇게 생겼는지 (주석)
      docs/decisions/*.md   이 표에 얽힌 결정들
      qa/checks/integrity.sql  이 표를 지키는 검사
      db/rls/*.sql          이 표를 건드리는 정책과 RPC
    예를 들어 heart_transaction 은 결정 6개 · 검사 5종에 걸쳐 있다.

    합성 데이터를 만들 때 표 40개를 하나씩 놓고 "이 컬럼에 무슨 값이
    들어가야 하고 왜 그런가"를 봐야 하는데, 매번 네 군데를 찾는 것은
    40번 반복된다.

⚠️ **새로 쓰는 내용은 없다.** 전부 기존 파일에서 긁어모은다.
   원본이 바뀌면 다시 돌린다 — erd.py 가 ERD 를 뽑는 것과 같다.
   그러므로 **이 폴더의 파일은 손으로 고치지 않는다.**

사용법:
    python db/wiki_tables.py
    python db/wiki_tables.py --check     # 갱신이 필요한지만 (lint 용)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply import dsn  # noqa: E402
from erd import (DOMAINS, EMPTY_REASON, MASTER, REFERENCE,  # noqa: E402
                 fetch, row_counts, table_notes)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "tables"

KIND_LABEL = {
    "master": "마스터 — 선택지·코드표. 시드 SQL 이 채운다",
    "reference": "참조 — 외부(NEIS)에서 받아 채운다",
    "activity": "활동 — 사람이 쓰면 쌓인다",
}


def mentions(text: str, table: str) -> bool:
    """본문이 이 표를 가리키는가.

    이름에 밑줄이 있으면 그 자체로 식별자라 단어 경계만으로 안전하다.
    `post`·`report` 처럼 흔한 낱말은 백틱이나 코드 안에 있을 때만 인정한다 —
    안 그러면 "리포트를 보면" 같은 문장이 전부 걸린다.
    """
    if "_" in table:
        return re.search(rf"\b{re.escape(table)}\b", text) is not None
    return re.search(rf"[`.\s(]{re.escape(table)}[`.\s,)]", text) is not None


def decisions_for(tables: list[str]) -> dict[str, list[tuple[str, str]]]:
    """각 표를 실제로 다루는 결정을 찾는다.

    ⚠️ "이어지는 결정" 블록은 빼고 본다. 거기 실린 것은 **다른 결정의 제목**이고,
       그 제목에 표 이름이 들어 있으면(예: drop-admin-user 의 "app_user.is_admin")
       그 표를 다루지도 않는 결정이 딸려온다.
    """
    out: dict[str, list[tuple[str, str]]] = {t: [] for t in tables}
    for path in sorted((ROOT / "docs" / "decisions").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        text = re.split(r"^## 이어지는 결정$", text, flags=re.M)[0]
        title = m.group(1).strip() if (m := re.search(r"^title:\s*(.+)$", text, re.M)) else path.stem
        for t in tables:
            if mentions(text, t):
                out[t].append((path.stem, title))
    return out


def checks_for(tables: list[str]) -> dict[str, list[str]]:
    """integrity.sql 을 검사 단위로 쪼개, 각 검사가 건드리는 표를 찾는다."""
    out: dict[str, list[str]] = {t: [] for t in tables}
    sql = (ROOT / "qa" / "checks" / "integrity.sql").read_text(encoding="utf-8")
    for block in re.split(r"\bUNION ALL\b", sql):
        name = m.group(1) if (m := re.search(r"SELECT\s+'([^']+)'", block)) else None
        if not name:
            continue
        # 주석은 빼고 실제 SQL 이 부르는 표만 본다
        body = re.sub(r"--[^\n]*", "", block)
        used = set(re.findall(r"\b(?:FROM|JOIN)\s+(\w+)", body, re.I))
        for t in tables:
            if t in used:
                out[t].append(name)
    return out


def rls_for(tables: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {t: [] for t in tables}
    for path in sorted((ROOT / "db" / "rls").glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        for t in tables:
            if re.search(rf"\b{re.escape(t)}\b", text):
                out[t].append(path.name)
    return out


def generator_tables() -> set[str]:
    src = (ROOT / "generator" / "generate.py").read_text(encoding="utf-8")
    made = set(re.findall(r'w\.write\("(\w+)"', src))
    # session_rows 로 모아 한 번에 쓰는 것들은 정적으로 안 잡힌다
    made |= {"vote_item", "vote_candidate", "vote_shuffle", "ad_impression"}
    seed = set(re.findall(r"INSERT INTO (\w+)",
                          (ROOT / "db" / "ddl" / "90_seed_master.sql").read_text(encoding="utf-8")))
    return made | seed


def build_page(t: str, ctx: dict) -> str:
    cols, pks, fks, order, uniques = (ctx["cols"], ctx["pks"], ctx["fks"],
                                      ctx["order"], ctx["uniques"])
    note = ctx["notes"].get(t, {})
    domain = ctx["domain"].get(t, "기타")
    kind = "master" if t in MASTER else "reference" if t in REFERENCE else "activity"
    n = ctx["counts"].get(t, 0)
    fk_of = {(c, col): p for c, col, p in fks}

    L = [
        "---",
        f"title: {t}",
        f"domain: {domain}",
        f"kind: {kind}",
        f"rows: {n}",
        f"tags: [테이블, {domain}]",
        "---",
        "",
        f"# {t}" + (f" · {note.get('title', '')}" if note.get("title") else ""),
        "",
        "> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.",
        "> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.",
        "",
        f"**{domain}** · {KIND_LABEL[kind]} · 실데이터 **{n:,}행**",
        "",
    ]

    if t in EMPTY_REASON:
        why = EMPTY_REASON[t]
        tag = {"live": "기능은 살아 있는데 아직 아무도 안 했다",
               "no-screen": "화면이나 실행 코드가 없다",
               "no-writer": "계획에는 있는데 쓰는 코드가 없다"}.get(why[0], why[0])
        L += [f"> **비어 있다 — {tag}.** {why[1]}", ""]

    if note.get("note"):
        L += ["## 왜 이렇게 생겼나", "", note["note"], ""]

    L += ["## 컬럼", "",
          "| 이름 | 타입 | NULL | 키 |", "|---|---|---|---|"]
    for c in order.get(t, []):
        nullable, typ = cols.get((t, c), (True, "?"))
        typ = (typ.replace("character varying", "varchar")
                  .replace("timestamp with time zone", "timestamptz"))
        key = []
        if (t, c) in pks:
            key.append("**PK**")
        if (t, c) in fk_of:
            parent = fk_of[(t, c)]
            # 스키마 밖 부모(auth.users)는 노드가 없으므로 링크하지 않는다
            key.append(f"→ [[{parent}]]" if "." not in parent else f"→ {parent}")
        L.append(f"| `{c}` | {typ} | {'' if nullable else 'NOT NULL'} | {' '.join(key)} |")
    L.append("")

    if uniques.get(t):
        L += ["**UNIQUE** — " + " · ".join(f"`{u}`" for u in uniques[t]), ""]

    incoming = sorted({c for c, _, p in fks if p == t})
    if incoming:
        L += ["**이 표를 참조하는 표** — " + " · ".join(f"[[{c}]]" for c in incoming), ""]

    if ds := ctx["decisions"].get(t):
        L += [f"## 얽힌 결정 {len(ds)}개", ""]
        L += [f"- [[{slug}|{title}]]" for slug, title in ds]
        L.append("")

    if cs := ctx["checks"].get(t):
        L += [f"## 이 표를 지키는 정합성 검사 {len(cs)}종", "",
              "`qa/checks/integrity.sql` · 위반 0이어야 한다.", ""]
        L += [f"- {c}" for c in cs]
        L.append("")

    if rs := ctx["rls"].get(t):
        L += ["## 이 표를 다루는 정책·RPC", "",
              " · ".join(f"`db/rls/{r}`" for r in rs), ""]

    made = t in ctx["generator"]
    L += ["## 합성 데이터", "",
          ("생성기가 만든다." if made else
           "⚠️ **생성기가 아직 만들지 않는다.** 합성 데이터를 채우려면 새로 써야 한다."),
          ""]

    # 꼬리말에 [[erd]] 를 걸면 40장이 전부 걸어 가짜 허브가 된다.
    # 관계는 위의 FK 링크가 이미 그린다.
    L += ["---", "", "정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]"]
    return "\n".join(L) + "\n"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["local", "supabase"], default="supabase")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    with psycopg.connect(dsn(args.target), connect_timeout=30) as conn, conn.cursor() as cur:
        tables, cols, pks, fks, order, uniques = fetch(cur)
        counts = row_counts(cur, tables)

    ctx = {
        "cols": cols, "pks": pks, "fks": fks, "order": order, "uniques": uniques,
        "notes": table_notes(), "counts": counts,
        "domain": {t: title for title, _, members in DOMAINS for t in members},
        "decisions": decisions_for(tables),
        "checks": checks_for(tables),
        "rls": rls_for(tables),
        "generator": generator_tables(),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    stale = []
    for t in tables:
        page = build_page(t, ctx)
        path = OUT / f"{t}.md"
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != page:
                stale.append(t)
        else:
            path.write_text(page, encoding="utf-8")

    # 사라진 표의 페이지는 지운다 — 남으면 없는 표를 설명하게 된다
    orphans = [p for p in OUT.glob("*.md") if p.stem not in tables]
    if args.check:
        if stale or orphans:
            print(f"★ docs/tables/ 가 낡았습니다 ({len(stale)}개 갱신, {len(orphans)}개 잔재)"
                  " — python db/wiki_tables.py")
            return 1
        print("  docs/tables/ 최신")
        return 0
    for p in orphans:
        p.unlink()
        print(f"  잔재 삭제 {p.name}")

    with_dec = sum(1 for t in tables if ctx["decisions"][t])
    with_chk = sum(1 for t in tables if ctx["checks"][t])
    no_gen = [t for t in tables if t not in ctx["generator"]]
    print(f"생성 완료 — docs/tables/ · 표 {len(tables)}개")
    print(f"  결정이 얽힌 표      {with_dec:>3}")
    print(f"  정합성 검사가 있는 표 {with_chk:>3}")
    print(f"  생성기가 안 만드는 표 {len(no_gen):>3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
