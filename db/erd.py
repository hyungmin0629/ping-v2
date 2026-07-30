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
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply import dsn  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "erd.md"

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

    cur.execute("""
        SELECT c.relname, count(*) FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public' AND c.relkind = 'r' GROUP BY 1
    """)
    tables = sorted(t for t, _ in cur.fetchall())
    return tables, cols, pks, fks


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
        tables, cols, pks, fks = fetch(cur)

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
