"""
SQL 파일 하나를 대상 DB 에 적용한다.

apply.py 는 스키마 전체를 정해진 순서로 올리는 스크립트다.
정책·함수·시드처럼 나중에 하나씩 추가되는 파일은 이걸로 올린다.
파일 전체가 한 트랜잭션이라, 중간에 실패하면 아무것도 반영되지 않는다.

사용법:
    python db/run_sql.py db/rls/onboarding.sql
    python db/run_sql.py db/seed_org.sql
    python db/run_sql.py db/rls/policies.sql --target local
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply import dsn  # noqa: E402  — DSN 규칙을 한 곳에만 둔다

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="적용할 .sql 파일")
    ap.add_argument("--target", choices=["local", "supabase"], default="supabase")
    args = ap.parse_args()

    path = Path(args.path)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        sys.exit(f"파일이 없습니다: {path}")

    sql = path.read_text(encoding="utf-8")

    with psycopg.connect(dsn(args.target), connect_timeout=30) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

    print(f"적용 완료 — {path.name} → {args.target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
