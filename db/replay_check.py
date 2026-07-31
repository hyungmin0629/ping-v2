"""
처음부터 다시 만들어도 같은 스키마가 나오는가. (W18)

왜 필요한가:
    `apply.py` 는 `db/migrations/*.sql` 을 **전부** 다시 적용한다. 그래서
    옛 마이그레이션도 새 스키마 위에서 돌 수 있어야 하는데, 표를 지우거나
    이름을 바꾸면 그 전제가 조용히 깨진다.

    실제로 두 번 깨졌다(2026-07-31):
      009  DDL 이 더 이상 만들지 않는 admin_user 를 찾다가 실패
      010  004 가 이미 만든 트리거를 다시 만들다가 실패

    둘 다 **살아 있는 DB 에서는 안 보인다.** 거기서는 옛 표가 실제로 있었고
    트리거도 하나뿐이었기 때문이다. 새로 만들어 봐야만 드러난다.

무엇을 하나:
    로컬 Postgres 에 임시 DB 를 만들어 DDL + 마이그레이션을 전부 돌리고,
    살아 있는 Supabase 와 **테이블·컬럼을 대조**한 뒤 임시 DB 를 지운다.
    로컬의 합성 데이터는 건드리지 않는다 — 다른 데이터베이스를 쓴다.

사용법:
    python db/replay_check.py          # 로컬 Docker(pgtest)가 떠 있어야 한다
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply import DDL_FILES, MIGRATION_FILES, dsn  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEMP_DB = "replay_check"

SHAPE = """
    SELECT c.relname || '.' || a.attname
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
      JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
     WHERE n.nspname = 'public' AND c.relkind = 'r'
"""
TABLES = """
    SELECT table_name FROM information_schema.tables
     WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
"""


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    base = dsn("local")
    target = re.sub(r"dbname=\S+", f"dbname={TEMP_DB}", base)

    def admin(sql: str) -> None:
        conn = psycopg.connect(base, autocommit=True)
        conn.execute(sql)
        conn.close()

    try:
        admin(f"DROP DATABASE IF EXISTS {TEMP_DB}")
        admin(f"CREATE DATABASE {TEMP_DB}")
    except psycopg.OperationalError as e:
        print(f"로컬 Postgres 에 붙지 못했습니다 — 컨테이너가 떠 있는지 보세요.\n  {e}")
        return 1

    try:
        with psycopg.connect(target) as conn, conn.cursor() as cur:
            for name in DDL_FILES:
                cur.execute((ROOT / "db" / "ddl" / name).read_text(encoding="utf-8"))
            for name in MIGRATION_FILES:
                try:
                    cur.execute((ROOT / "db" / "migrations" / name).read_text(encoding="utf-8"))
                except Exception as e:
                    print(f"\n★ 마이그레이션 {name} 이 새 스키마 위에서 깨집니다\n  {e}")
                    return 1
            conn.commit()
            cur.execute(TABLES)
            fresh_tables = {r[0] for r in cur.fetchall()}
            cur.execute(SHAPE)
            fresh_cols = {r[0] for r in cur.fetchall()}

        print(f"DDL {len(DDL_FILES)}개 + 마이그레이션 {len(MIGRATION_FILES)}개 "
              f"→ 테이블 {len(fresh_tables)}개 / 컬럼 {len(fresh_cols)}개")

        load_dotenv(ROOT / ".env")
        with psycopg.connect(os.environ["SUPABASE_DB_URL"], connect_timeout=30) as conn, \
                conn.cursor() as cur:
            cur.execute(TABLES)
            live_tables = {r[0] for r in cur.fetchall()}
            cur.execute(SHAPE)
            live_cols = {r[0] for r in cur.fetchall()}
        print(f"살아 있는 Supabase{' ' * 17}"
              f"→ 테이블 {len(live_tables)}개 / 컬럼 {len(live_cols)}개")

        gaps = [
            ("새로 만든 쪽에만 있는 테이블", sorted(fresh_tables - live_tables)),
            ("Supabase 에만 있는 테이블", sorted(live_tables - fresh_tables)),
            ("새로 만든 쪽에만 있는 컬럼", sorted(fresh_cols - live_cols)),
            ("Supabase 에만 있는 컬럼", sorted(live_cols - fresh_cols)),
        ]
        bad = False
        for label, items in gaps:
            if items:
                bad = True
                print(f"\n★ {label} ({len(items)})")
                for i in items[:20]:
                    print(f"    {i}")
                if len(items) > 20:
                    print(f"    … 외 {len(items) - 20}개")

        if bad:
            print("\n어긋납니다 — DDL 이 진실인데 살아 있는 DB 와 다릅니다.")
            return 1
        print("\n일치 — 처음부터 다시 만들어도 같은 스키마가 나옵니다")
        return 0
    finally:
        admin(f"DROP DATABASE IF EXISTS {TEMP_DB}")


if __name__ == "__main__":
    sys.exit(main())
