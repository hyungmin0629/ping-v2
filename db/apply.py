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


def confirm_supabase(drop: bool) -> bool:
    """실서비스 적용 전 확인.

    이 스크립트는 `db/migrations/*.sql` 을 **전부** 적용한다. 그래야 스키마를
    처음부터 다시 세울 수 있기 때문인데, 부작용이 하나 있다 —
    합성 데이터 작업용으로 만든 마이그레이션도 함께 간다.
    로컬에만 적용해 뒀더라도, 누군가 이 명령을 supabase 로 돌리는 순간
    실서비스에 반영된다.

    실유저가 있는 DB 다. 그래서 무엇이 적용되는지와 지금 누가 쓰고 있는지를
    보여주고 확인을 받는다. 자동화에서는 --yes 로 건너뛴다.
    """
    print("=" * 62)
    print("⚠️  실서비스(Supabase)에 스키마를 적용하려고 합니다")
    print("=" * 62)

    try:
        with psycopg.connect(dsn("supabase"), connect_timeout=30) as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM app_user WHERE NOT is_synthetic")
            users = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM vote_item WHERE voted_at IS NOT NULL")
            votes = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM post WHERE status = 'PUBLISHED'")
            posts = cur.fetchone()[0]
        print(f"\n지금 이 DB 에는 실유저 {users}명 · 투표 {votes}건 · 게시글 {posts}건이 있습니다.")
    except Exception as e:
        print(f"\n(현재 상태를 읽지 못했습니다: {type(e).__name__})")

    print(f"\n적용될 마이그레이션 {len(MIGRATION_FILES)}개:")
    for name in MIGRATION_FILES:
        print(f"  - {name}")
    if drop:
        print("\n🔴 --drop 이 켜져 있습니다. **모든 테이블을 지우고 다시 만듭니다.**")
        print("   실유저 데이터가 전부 사라집니다.")

    print("\n로컬 합성 데이터 작업이라면 --target local 을 써야 합니다.")
    answer = input("\n계속하려면 'supabase' 를 입력하세요: ").strip()
    return answer == "supabase"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["local", "supabase"], required=True)
    ap.add_argument("--drop", action="store_true", help="public 스키마를 비우고 새로 만든다")
    ap.add_argument("--yes", action="store_true", help="supabase 확인 절차를 건너뛴다")
    args = ap.parse_args()

    files = list(DDL_FILES)
    if args.target == "supabase":
        files += [f for f in SUPABASE_EXTRA if (DDL_DIR / f).exists()]

    if args.target == "supabase" and not args.yes:
        if not confirm_supabase(args.drop):
            print("취소했습니다.")
            return 1

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
