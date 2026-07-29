"""
DDL을 대상 DB에 적용한다.

대상은 두 곳이다:
  local    — 로컬 Docker Postgres. 합성 데이터용.
  supabase — Supabase. 실유저 전용. 합성 데이터를 넣지 않는다.

⚠️ 70_deferred_v2.sql 은 적용 대상이 아니다(MVP 미사용, 개인정보 관련).
   그래서 와일드카드를 쓰지 않고 파일을 명시적으로 나열한다.

사용법:
    python db/apply.py --target local
    python db/apply.py --target supabase
    python db/apply.py --target supabase --drop    # 기존 테이블 지우고 새로
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DDL_DIR = ROOT / "db" / "ddl"
MIGRATION_DIR = ROOT / "db" / "migrations"

# 실행 순서가 곧 의존 순서다. 와일드카드 금지.
DDL_FILES = [
    "00_enums.sql",
    "10_reference_user.sql",
    "20_social.sql",
    "30_question_vote.sql",
    "40_heart_report.sql",
    "50_school_service.sql",
    "60_board.sql",
    "90_seed_master.sql",
]

# Supabase 전용 추가분 (auth.users 연결 등). 로컬에는 auth 스키마가 없어 적용하지 않는다.
SUPABASE_EXTRA = ["supabase/10_auth_link.sql"]

# 스키마 변경 이력. DDL 을 처음부터 다시 올려도 여기까지 적용해야 현재 스키마가 된다.
# 빠뜨리면 neis_office_code / info_school_id / padded_count 가 없는 반쪽 스키마가 된다.
MIGRATION_FILES = sorted(f.name for f in MIGRATION_DIR.glob("*.sql"))


def dsn(target: str) -> str:
    load_dotenv(ROOT / ".env")
    if target == "supabase":
        url = os.getenv("SUPABASE_DB_URL", "").strip()
        if not url:
            sys.exit("SUPABASE_DB_URL 이 .env 에 없습니다")
        return url
    return (
        f"host={os.getenv('PGHOST','localhost')} "
        f"port={os.getenv('PGPORT','5433')} "
        f"dbname={os.getenv('PGDATABASE','pingv2')} "
        f"user={os.getenv('PGUSER','postgres')} "
        f"password={os.getenv('PGPASSWORD','test')}"
    )


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["local", "supabase"], required=True)
    ap.add_argument("--drop", action="store_true", help="public 스키마를 비우고 새로 만든다")
    args = ap.parse_args()

    files = list(DDL_FILES)
    if args.target == "supabase":
        files += [f for f in SUPABASE_EXTRA if (DDL_DIR / f).exists()]

    with psycopg.connect(dsn(args.target), connect_timeout=30) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            if args.drop:
                print("기존 객체 삭제...")
                # Supabase 는 public 스키마 자체를 지우면 곤란하므로 내용만 비운다
                cur.execute("""
                    DO $$
                    DECLARE r record;
                    BEGIN
                        FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='public' LOOP
                            EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', r.tablename);
                        END LOOP;
                        FOR r IN SELECT t.typname FROM pg_type t
                                 JOIN pg_namespace n ON n.oid=t.typnamespace
                                 WHERE n.nspname='public' AND t.typtype='e' LOOP
                            EXECUTE format('DROP TYPE IF EXISTS public.%I CASCADE', r.typname);
                        END LOOP;
                    END $$;
                """)

            for name in files:
                path = DDL_DIR / name
                cur.execute(path.read_text(encoding="utf-8"))
                print(f"  적용  {name}")

            for name in MIGRATION_FILES:
                cur.execute((MIGRATION_DIR / name).read_text(encoding="utf-8"))
                print(f"  적용  migrations/{name}")

            cur.execute("""
                SELECT
                  (SELECT count(*) FROM information_schema.tables
                     WHERE table_schema='public' AND table_type='BASE TABLE'),
                  (SELECT count(*) FROM information_schema.table_constraints
                     WHERE table_schema='public' AND constraint_type='FOREIGN KEY')
            """)
            tables, fks = cur.fetchone()
        conn.commit()

    print(f"\n적용 완료 — {args.target}")
    print(f"  테이블 {tables}개 / FK {fks}개 / 마이그레이션 {len(MIGRATION_FILES)}개")
    if tables != 42:
        print(f"  ⚠️ 42개가 아닙니다. 70_deferred_v2.sql 이 섞였는지 확인하세요.")
        return 1
    if args.target == "supabase":
        print("\n다음: RLS 와 RPC 를 순서대로 올립니다 (CLAUDE.md 참조)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
