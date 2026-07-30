"""
적재 검증 — Postgres 와 BigQuery 의 행 수를 테이블마다 대조한다.

증분 적재는 조용히 틀린다. 워터마크가 한 번 어긋나면 그 뒤로 계속 빠진 채
흐르고, 쿼리는 아무 오류 없이 답을 준다. 그래서 적재 후에는 반드시 센다.

같은 BigQuery 테이블에 두 원천이 섞여 있으므로 `_source` 로 걸러 비교한다.

사용법:
    python pipeline/verify_load.py --source supabase
    python pipeline/verify_load.py --source local
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from extract_load import load_manifest, pg_dsn, require_env, resolve_credentials  # noqa: E402


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["supabase", "local"], required=True)
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    resolve_credentials()
    project = require_env("GCP_PROJECT_ID")
    dataset = os.getenv("BQ_DATASET_RAW", "raw")
    dataset_id = f"{project}.{dataset}"

    bq = bigquery.Client(project=project, location=os.getenv("BQ_LOCATION", "asia-northeast3"))
    plan = load_manifest()

    # 매니페스트에 없는 테이블은 **BigQuery 로 아예 가지 않는다.** 오류도 경고도
    # 없어서, 새 테이블을 만들고 tables.yaml 을 잊으면 그 데이터는 조용히 사라진다.
    # 행 수를 세기 전에 목록부터 맞춰 본다.
    with psycopg.connect(pg_dsn(args.source), connect_timeout=60) as conn, conn.cursor() as cur:
        cur.execute("""SELECT table_name FROM information_schema.tables
                        WHERE table_schema='public' AND table_type='BASE TABLE'""")
        actual = {r[0] for r in cur.fetchall()}

    missing = sorted(actual - set(plan))
    stale = sorted(set(plan) - actual)
    if missing or stale:
        print("❌ pipeline/tables.yaml 이 실제 스키마와 어긋납니다\n")
        for t in missing:
            print(f"   매니페스트에 없음  {t}  ← 이 테이블은 BigQuery 로 가지 않습니다")
        for t in stale:
            print(f"   원천에 없음        {t}  ← 매니페스트에서 지우세요")
        print("\n   full / incremental 중 하나에 넣어야 적재됩니다.")
        print("   작고 거의 안 변하면 full, 활동이 쌓이면 incremental 입니다.")
        return 1
    print(f"매니페스트 대조 — {len(plan)}개 테이블이 실제 스키마와 일치\n")

    # BigQuery 쪽은 한 번에 센다. 테이블마다 쿼리를 날리면 42번 왕복한다.
    union = "\nUNION ALL\n".join(
        f"SELECT '{t}' AS table_name, count(*) AS n FROM `{dataset_id}.{t}` WHERE _source = @s"
        for t in plan
    )
    try:
        rows = bq.query(
            union,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("s", "STRING", args.source)]
            ),
        ).result()
    except NotFound as e:
        sys.exit(f"BigQuery 에 테이블이 없습니다. 먼저 적재하세요.\n  {e}")
    bq_counts = {r.table_name: r.n for r in rows}

    # 부족한 것과 남는 것은 성격이 다르다.
    #   pg > bq  적재가 빠뜨렸다. 결함이다.
    #   pg < bq  원천에서 지워졌는데 BigQuery 에는 남아 있다.
    #            증분 MERGE 는 DELETE 를 옮기지 않기 때문이다(의도된 동작 —
    #            raw 는 이력을 지우지 않는다). reset_users.py 를 돌린 뒤 이렇게 된다.
    missing, leftover = [], []
    with psycopg.connect(pg_dsn(args.source), connect_timeout=60) as conn, conn.cursor() as cur:
        for table in plan:
            cur.execute(f'SELECT count(*) FROM public."{table}"')
            pg_n = cur.fetchone()[0]
            bq_n = bq_counts.get(table, 0)
            if pg_n > bq_n:
                mark = "빠짐"
                missing.append((table, pg_n, bq_n))
            elif pg_n < bq_n:
                mark = "남음"
                leftover.append((table, pg_n, bq_n))
            else:
                mark = "일치"
            print(f"  {mark}  {table:26} pg {pg_n:>9,}  bq {bq_n:>9,}")

    print()
    total = sum(bq_counts.values())

    if leftover:
        print(f"ℹ️  {len(leftover)}개 테이블에 원천보다 많은 행이 있습니다 (원천에서 삭제된 이력)")
        for table, pg_n, bq_n in leftover:
            print(f"   {table}: pg {pg_n:,} < bq {bq_n:,} (+{bq_n - pg_n:,})")
        print()

    if missing:
        print(f"❌ {len(missing)}개 테이블이 빠졌습니다 — {args.source}")
        for table, pg_n, bq_n in missing:
            print(f"   {table}: pg {pg_n:,} > bq {bq_n:,} ({pg_n - bq_n:,}행 부족)")
        print("\n   --full-refresh 로 다시 적재하면 워터마크를 무시하고 처음부터 받습니다.")
        return 1

    print(f"빠진 행 없음 — {args.source} · {len(plan)}개 테이블 / BigQuery {total:,}행")
    return 0


if __name__ == "__main__":
    sys.exit(main())
