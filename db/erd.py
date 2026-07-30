"""
살아 있는 스키마에서 ERD(mermaid)를 뽑는다.

왜 스크립트인가:
    이 프로젝트는 "스키마 구조는 DDL 이 진실"이고 문서에 테이블 정의를
    베껴 적지 않는다. ERD 를 손으로 그리면 그 규칙을 어기는 두 번째 진실이
    생기고, 마이그레이션이 하나 쌓일 때마다 조용히 낡는다.
    그래서 그리지 않고 **뽑는다.**

    관계는 pg_constraint 에서 읽으므로 실제로 걸려 있는 FK 만 나온다.
    문서에 적어두고 안 건 FK 같은 것은 애초에 나올 수 없다.

사용법:
    python db/erd.py                     # docs/erd.md 를 다시 만든다
    python db/erd.py --target local
    python db/erd.py --stdout            # 파일을 쓰지 않고 출력만
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply import dsn  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "erd.md"
OUT_JSON = ROOT / "docs" / "erd.json"      # 카드형 ERD 가 읽는다

# 42개를 한 장에 그리면 아무도 못 읽는다. 도메인으로 나눈다.
# 여기 없는 테이블은 "기타"로 떨어진다 — 새 테이블이 조용히 사라지지 않게.
DOMAINS: list[tuple[str, str, list[str]]] = [
    ("기준 정보", "지역·학교·학급. 유저를 배치할 곳이 먼저 있어야 한다.",
     ["region", "school", "grade_class", "admin_user"]),
    ("유저", "익명 계정 하나에 프로필 하나. 접속 기록과 탈퇴가 딸린다.",
     ["app_user", "user_session", "user_withdrawal", "withdrawal_reason"]),
    ("친구", "요청(방향 있음) → 수락 → friendship(방향 없음).",
     ["friend_request", "friendship", "friend_recommendation", "block_record"]),
    ("질문과 투표", "세션 하나에 아이템 여럿, 아이템 하나에 후보 넷.",
     ["question_category", "question", "question_request", "vote_session",
      "vote_item", "vote_candidate", "vote_shuffle", "vote_received",
      "hint_purchase", "ad_impression"]),
    ("하트", "모든 증감이 heart_transaction 하나를 거친다. 이 프로젝트의 핵심.",
     ["heart_transaction_type", "heart_product", "heart_purchase", "heart_transaction"]),
    ("신고와 제재", "신고와 제재를 FK 로 연결한다. 구 시스템에는 이 연결이 없었다.",
     ["report_reason", "report", "sanction_policy", "sanction"]),
    ("학교 정보", "NEIS 에서 받아 채운다. 급식은 데이터를 준 학교 아래 저장한다.",
     ["meal_plan", "meal_menu_item", "timetable", "school_notice",
      "school_notice_read", "school_event", "external_sync_log"]),
    ("게시판", "자유게시판(W9). 익명이 아니라 글쓴이가 드러난다.",
     ["board_category", "post", "post_comment", "post_like", "comment_like"]),
]


def fetch(cur):
    cur.execute("""
        SELECT c.relname AS tbl, a.attname AS col, NOT a.attnotnull AS nullable,
               format_type(a.atttypid, a.atttypmod) AS typ
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
          JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
         WHERE n.nspname = 'public' AND c.relkind = 'r'
    """)
    cols = {(t, c): (nul, ty) for t, c, nul, ty in cur.fetchall()}

    cur.execute("""
        SELECT c.relname, a.attname
          FROM pg_constraint con
          JOIN pg_class c ON c.oid = con.conrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
          JOIN LATERAL unnest(con.conkey) k(attnum) ON true
          JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
         WHERE con.contype = 'p' AND n.nspname = 'public'
    """)
    pks = set(cur.fetchall())

    cur.execute("""
        SELECT c.relname AS child, a.attname AS col,
               -- 부모가 public 밖이면 스키마를 붙인다. auth.users(Supabase 인증)가
               -- 그렇다 — 이름만 보면 우리 테이블처럼 읽힌다.
               CASE WHEN fn.nspname = 'public' THEN f.relname
                    ELSE fn.nspname || '.' || f.relname END AS parent
          FROM pg_constraint con
          JOIN pg_class c ON c.oid = con.conrelid
          JOIN pg_class f ON f.oid = con.confrelid
          JOIN pg_namespace n  ON n.oid  = c.relnamespace
          JOIN pg_namespace fn ON fn.oid = f.relnamespace
          JOIN LATERAL unnest(con.conkey) k(attnum) ON true
          JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
         WHERE con.contype = 'f' AND n.nspname = 'public'
         ORDER BY 1, 2
    """)
    fks = cur.fetchall()

    # 컬럼 순서와 UNIQUE 는 카드형 ERD(docs/erd.json)에서 쓴다.
    cur.execute("""
        SELECT c.relname, a.attname, a.attnum
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
          JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
         WHERE n.nspname = 'public' AND c.relkind = 'r'
         ORDER BY c.relname, a.attnum
    """)
    order: dict[str, list[str]] = {}
    for t, col, _ in cur.fetchall():
        order.setdefault(t, []).append(col)

    cur.execute("""
        SELECT c.relname, string_agg(a.attname, ', ' ORDER BY k.ord)
          FROM pg_constraint con
          JOIN pg_class c ON c.oid = con.conrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
          JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord) ON true
          JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
         WHERE con.contype = 'u' AND n.nspname = 'public'
         GROUP BY c.relname, con.oid
    """)
    uniques: dict[str, list[str]] = {}
    for t, cols_txt in cur.fetchall():
        uniques.setdefault(t, []).append(cols_txt)

    cur.execute("""
        SELECT c.relname, count(*) FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public' AND c.relkind = 'r' GROUP BY 1
    """)
    tables = sorted(t for t, _ in cur.fetchall())
    return tables, cols, pks, fks, order, uniques


# 도메인 색. 채도를 낮춘 8색이라 옆에 놓아도 서로 싸우지 않고,
# 전부 밝아서 검은 글씨가 얹힌다.
DOMAIN_FILL = {
    "기준 정보": "#E3E8E6", "유저": "#CFE6DE", "친구": "#DCE7CF",
    "질문과 투표": "#E9E2CB", "하트": "#F0DCCB", "신고와 제재": "#EED6D6",
    "학교 정보": "#D6E0EE", "게시판": "#E2D9EA", "기타": "#EDEDED",
}


def whole(domains, tables, fks) -> str:
    """42개를 한 장에. 컬럼을 버리고 관계만 남긴다.

    상자마다 키를 적으면 42개가 화면을 덮어 정작 선이 안 보인다. 한 장으로 보는
    목적은 "무엇이 무엇에 붙어 있나"이지 "어떤 컬럼인가"가 아니다.
    같은 두 테이블 사이의 FK 가 여럿이면(report→app_user 는 2개) 선 하나로 접고
    ×N 을 붙인다 — 안 접으면 report 주변이 뭉갠다.
    """
    # id 는 **순서**로 짓는다. hash() 는 실행마다 값이 달라져 생성 파일이
    # 매번 다르게 나온다 — git 이 의미 없는 변경으로 채워진다.
    lines = ["flowchart LR"]
    for i, (title, _, members) in enumerate(domains):
        members = [t for t in members if t in tables]
        if not members:
            continue
        lines.append(f'    subgraph g{i}["{title}"]')
        lines.append("        direction TB")
        for t in members:
            lines.append(f"        {t}[{t}]")
        lines.append("    end")

    pairs: dict[tuple[str, str], int] = {}
    for child, _col, parent in fks:
        if parent not in tables or child not in tables:
            continue          # auth.users 처럼 스키마 밖 부모는 그리지 않는다
        pairs[(child, parent)] = pairs.get((child, parent), 0) + 1

    for (child, parent), n in sorted(pairs.items()):
        label = f'|"×{n}"|' if n > 1 else ""
        lines.append(f"    {child} -->{label} {parent}")

    for i, (title, _, members) in enumerate(domains):
        members = [t for t in members if t in tables]
        if members:
            lines.append(f"    classDef c{i} fill:{DOMAIN_FILL.get(title, '#EEE')},"
                         f"stroke:#5C6B6B,color:#14181A")
            lines.append(f"    class {','.join(members)} c{i}")
    return "\n".join(lines)


def diagram(members: list[str], cols, pks, fks) -> str:
    """도메인 하나의 mermaid erDiagram.

    컬럼은 **키만** 싣는다. 전부 실으면 상자가 화면을 넘어가 관계선이 안 보인다.
    나머지는 DDL 을 보면 된다 — 그게 진실이므로.
    """
    inside = set(members)
    lines = ["erDiagram"]

    for t in members:
        keys = sorted(
            {c for (tt, c) in pks if tt == t}
            | {c for (child, c, _) in fks if child == t}
        )
        lines.append(f"    {t} {{")
        for c in keys:
            nullable, typ = cols.get((t, c), (False, "?"))
            mark = "PK" if (t, c) in pks else "FK"
            short = typ.replace("character varying", "varchar").replace(
                "timestamp with time zone", "timestamptz")
            lines.append(f"        {short.split('(')[0].replace(' ', '_')} {c} {mark}")
        if not keys:
            lines.append("        _ 키없음")
        lines.append("    }")

    seen = set()
    for child, col, parent in fks:
        if child not in inside:
            continue
        # 도메인 밖 부모는 상자를 만들지 않고 관계도 생략한다.
        # 대신 아래 "도메인을 넘는 연결" 표에 모아서 보여준다.
        if parent not in inside:
            continue
        nullable = cols.get((child, col), (False, ""))[0]
        left = "|o" if nullable else "||"
        key = (parent, child, col)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f'    {parent} {left}--o{{ {child} : "{col}"')
    return "\n".join(lines)


def as_json(domains, tables, cols, pks, fks, order, uniques) -> dict:
    """카드형 ERD 가 읽는 데이터. **모든 컬럼과 타입**을 담는다.

    mermaid 도표는 키만 실었지만 카드형은 컬럼 정의를 다 보여주는 것이 목적이다.
    여기서도 손으로 적지 않는다 — 전부 pg_catalog 에서 온다.
    """
    where = {t: title for title, _, members in domains for t in members}
    fk_of = {(c, col): p for c, col, p in fks}

    out: dict = {"tables": [], "edges": [], "domains": [d[0] for d in domains]}
    for t in tables:
        columns = []
        for c in order.get(t, []):
            nullable, typ = cols.get((t, c), (True, "?"))
            columns.append({
                "name": c,
                "type": (typ.replace("character varying", "varchar")
                            .replace("timestamp with time zone", "timestamptz")
                            .replace("double precision", "float8")),
                "null": nullable,
                "pk": (t, c) in pks,
                "fk": fk_of.get((t, c)),
            })
        out["tables"].append({"name": t, "domain": where.get(t, "기타"),
                              "columns": columns, "uniques": uniques.get(t, [])})

    seen = set()
    for child, col, parent in fks:
        if parent not in tables:
            continue                      # auth.users 같은 스키마 밖 부모
        if (child, parent, col) in seen:
            continue
        seen.add((child, parent, col))
        out["edges"].append({"from": child, "col": col, "to": parent,
                             "null": cols.get((child, col), (True, ""))[0]})
    return out


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["local", "supabase"], default="supabase")
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()

    with psycopg.connect(dsn(args.target), connect_timeout=30) as conn, conn.cursor() as cur:
        tables, cols, pks, fks, order, uniques = fetch(cur)

    placed = {t for _, _, members in DOMAINS for t in members}
    leftover = [t for t in tables if t not in placed]

    domains = list(DOMAINS)
    if leftover:
        domains.append(("기타", "도메인 분류에 없는 테이블이다. db/erd.py 의 DOMAINS 에 넣어라.",
                        leftover))

    out = [
        "# ERD",
        "",
        "> ⚠️ **이 파일은 생성물이다. 손으로 고치지 마라.**",
        "> 살아 있는 스키마에서 뽑는다 — `python db/erd.py`",
        ">",
        "> 관계는 실제로 걸려 있는 FK 만 나온다. 컬럼은 **키(PK·FK)만** 싣는다.",
        "> 전체 컬럼 정의는 `db/ddl/` 이 진실이다.",
        "",
        f"테이블 **{len(tables)}개** · FK **{len(fks)}개**",
        "",
        "점선(`|o`)으로 시작하는 관계는 FK 가 NULL 을 허용한다는 뜻이다.",
        "",
    ]

    out += ["## 전체", "",
            "42개를 한 장에 놓은 것이다. 색이 도메인이고, 화살표는 자식 → 부모다.",
            "같은 두 테이블 사이에 FK 가 여럿이면 선 하나로 접고 `×N` 을 붙였다.", "",
            "```mermaid", whole(domains, tables, fks), "```", ""]

    for title, note, members in domains:
        members = [t for t in members if t in tables]
        if not members:
            continue
        out += [f"## {title}", "", note, "", "```mermaid", diagram(members, cols, pks, fks),
                "```", ""]

    # 도메인 경계를 넘는 FK. 도표에서 뺀 것들이라 여기 모아 둔다.
    where = {t: title for title, _, members in domains for t in members}
    cross = [(where.get(c, "?"), c, col, where.get(p, "스키마 밖"), p)
             for c, col, p in fks if where.get(c) != where.get(p)]
    if cross:
        out += ["## 도메인을 넘는 연결", "",
                "도표를 읽을 수 있게 위 그림에서는 뺐다. 실제로는 걸려 있는 FK 다.", "",
                "| 자식 | 컬럼 | 부모 |", "|---|---|---|"]
        for cd, c, col, pd, p in sorted(cross):
            out.append(f"| {c} <sub>({cd})</sub> | `{col}` | {p} <sub>({pd})</sub> |")
        out.append("")

    if not args.stdout:
        OUT_JSON.write_text(
            json.dumps(as_json(domains, tables, cols, pks, fks, order, uniques),
                       ensure_ascii=False, indent=1), encoding="utf-8")

    text = "\n".join(out)
    if args.stdout:
        print(text)
    else:
        OUT.write_text(text, encoding="utf-8")
        print(f"생성 완료 — {OUT.relative_to(ROOT)}")
        print(f"  테이블 {len(tables)}개 / FK {len(fks)}개 / 도메인 {len(domains)}개")
        if leftover:
            print(f"  ⚠️ 분류 안 된 테이블 {len(leftover)}개: {', '.join(leftover)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
