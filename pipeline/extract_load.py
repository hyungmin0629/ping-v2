"""
Postgres → BigQuery raw 적재.

원천은 두 곳이고 **같은 BigQuery 테이블**로 흐른다.
  supabase — 실유저
  local    — 합성 데이터 (786만 행)

둘 다 id 가 1부터 시작하는 identity 라 그대로 섞으면 서로를 덮어쓴다.
그래서 모든 행에 `_source` 를 붙이고 키를 (_source, id) 로 쓴다.
분석에서 실유저만 보려면 `WHERE _source = 'supabase'` 다.

적재 방식은 pipeline/tables.yaml 이 정한다(full / incremental).

사용법:
    python pipeline/extract_load.py --source supabase
    python pipeline/extract_load.py --source supabase --table app_user
    python pipeline/extract_load.py --source supabase --full-refresh
    python pipeline/extract_load.py --source local --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import psycopg
import yaml
from dotenv import load_dotenv
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = Path(__file__).resolve().parent / "tables.yaml"

# 한 번에 BigQuery 로 올리는 행 수. 786만 행을 한 덩어리로 만들면 메모리가 터진다.
BATCH_ROWS = 50_000

STATE_TABLE = "_load_state"

# Postgres 타입 → BigQuery 타입.
# 열거형(USER-DEFINED)과 배열은 문자열로 눕힌다. raw 층은 원본 보존이 목적이고,
# 의미 부여는 stg 층에서 한다.
TYPE_MAP = {
    "bigint": "INT64",
    "integer": "INT64",
    "smallint": "INT64",
    "boolean": "BOOL",
    "double precision": "FLOAT64",
    "real": "FLOAT64",
    "numeric": "NUMERIC",
    "date": "DATE",
    "timestamp with time zone": "TIMESTAMP",
    "timestamp without time zone": "TIMESTAMP",
    "time without time zone": "STRING",
    "interval": "STRING",
    "uuid": "STRING",
    "json": "STRING",
    "jsonb": "STRING",
    "ARRAY": "STRING",
    "USER-DEFINED": "STRING",
}


# ---------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------
def load_manifest() -> dict:
    m = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    overrides = m.get("pk_overrides") or {}
    plan = {}
    for name in m["full"]:
        plan[name] = {"mode": "full", "pk": overrides.get(name, m["defaults"]["pk"])}
    for name in m["incremental"]:
        plan[name] = {
            "mode": "incremental",
            "pk": overrides.get(name, m["defaults"]["pk"]),
            "watermark": m["defaults"]["watermark"],
        }
    return plan


def pg_dsn(source: str) -> str:
    if source == "supabase":
        url = os.getenv("SUPABASE_DB_URL", "").strip()
        if not url:
            sys.exit("SUPABASE_DB_URL 이 .env 에 없습니다")
        return url
    return (
        f"host={os.getenv('PGHOST', 'localhost')} "
        f"port={os.getenv('PGPORT', '5433')} "
        f"dbname={os.getenv('PGDATABASE', 'pingv2')} "
        f"user={os.getenv('PGUSER', 'postgres')} "
        f"password={os.getenv('PGPASSWORD', 'test')}"
    )


def resolve_credentials() -> None:
    """GOOGLE_APPLICATION_CREDENTIALS 의 상대경로를 프로젝트 루트 기준으로 편다.

    .env 에는 `./credentials.json` 으로 들어 있다. 구글 라이브러리는 이걸
    **실행 위치** 기준으로 찾기 때문에, Airflow 컨테이너처럼 다른 곳에서
    돌리면 파일을 못 찾는다.
    """
    raw = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not raw:
        return
    path = Path(raw)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    if not path.exists():
        sys.exit(f"서비스 계정 키를 찾을 수 없습니다: {path}")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(path)


def require_env(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        sys.exit(f"{name} 이 .env 에 없습니다. README 의 P4 준비 절차를 보세요.")
    return v


# ---------------------------------------------------------------------
# 스키마
# ---------------------------------------------------------------------
def pg_columns(cur, table: str) -> list[tuple[str, str, bool]]:
    """(컬럼명, pg타입, nullable) — 선언 순서 그대로."""
    cur.execute(
        """
        SELECT column_name, data_type, is_nullable = 'YES'
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return cur.fetchall()


def bq_schema(cols: list[tuple[str, str, bool]]) -> list[bigquery.SchemaField]:
    """raw 층은 전부 NULLABLE 로 만든다.

    원천의 NOT NULL 을 그대로 옮기면, 나중에 스키마가 느슨해질 때
    적재가 통째로 실패한다. 제약 검증은 P5(품질검증)의 일이다.
    """
    fields = [
        bigquery.SchemaField(name, TYPE_MAP.get(pg_type, "STRING"), mode="NULLABLE")
        for name, pg_type, _ in cols
    ]
    fields.append(bigquery.SchemaField("_source", "STRING", mode="REQUIRED"))
    fields.append(bigquery.SchemaField("_loaded_at", "TIMESTAMP", mode="REQUIRED"))
    return fields


def to_json_value(v):
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, (dict, list, tuple)):
        return json.dumps(v, ensure_ascii=False, default=str)
    if isinstance(v, (bytes, memoryview)):
        return bytes(v).hex()
    return str(v)


# ---------------------------------------------------------------------
# BigQuery 준비
# ---------------------------------------------------------------------
def ensure_dataset(bq: bigquery.Client, dataset_id: str, location: str) -> None:
    try:
        bq.get_dataset(dataset_id)
    except NotFound:
        ds = bigquery.Dataset(dataset_id)
        ds.location = location
        bq.create_dataset(ds)
        print(f"  데이터셋 생성  {dataset_id} ({location})")


def ensure_table(
    bq: bigquery.Client, table_id: str, schema: list[bigquery.SchemaField], partition_on: str | None
) -> bigquery.Table:
    try:
        return bq.get_table(table_id)
    except NotFound:
        pass
    table = bigquery.Table(table_id, schema=schema)
    # updated_at 으로 나눈다. 행이 갱신되면 파티션을 옮겨 다니지만,
    # "최근 바뀐 것"이 분석의 기본 질문이라 이쪽이 맞다.
    if partition_on and any(f.name == partition_on and f.field_type == "TIMESTAMP" for f in schema):
        table.time_partitioning = bigquery.TimePartitioning(field=partition_on)
    table = bq.create_table(table)
    print(f"  테이블 생성  {table_id.split('.')[-1]}")
    return table


def ensure_state_table(bq: bigquery.Client, dataset_id: str) -> str:
    table_id = f"{dataset_id}.{STATE_TABLE}"
    schema = [
        bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("table_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("watermark", "TIMESTAMP"),
        bigquery.SchemaField("row_count", "INT64"),
        bigquery.SchemaField("loaded_at", "TIMESTAMP", mode="REQUIRED"),
    ]
    try:
        bq.get_table(table_id)
    except NotFound:
        bq.create_table(bigquery.Table(table_id, schema=schema))
        print(f"  테이블 생성  {STATE_TABLE} (적재 상태)")
    return table_id


def read_watermarks(bq: bigquery.Client, state_id: str, source: str) -> dict[str, datetime]:
    rows = bq.query(
        f"SELECT table_name, watermark FROM `{state_id}` WHERE source = @s",
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("s", "STRING", source)]
        ),
    ).result()
    return {r.table_name: r.watermark for r in rows if r.watermark is not None}


def write_watermark(
    bq: bigquery.Client, state_id: str, source: str, table: str, watermark, rows: int
) -> None:
    bq.query(
        f"""
        MERGE `{state_id}` T
        USING (SELECT @src AS source, @tbl AS table_name) S
          ON T.source = S.source AND T.table_name = S.table_name
        WHEN MATCHED THEN UPDATE SET
            watermark = @wm, row_count = T.row_count + @rows, loaded_at = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN INSERT (source, table_name, watermark, row_count, loaded_at)
            VALUES (@src, @tbl, @wm, @rows, CURRENT_TIMESTAMP())
        """,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("src", "STRING", source),
                bigquery.ScalarQueryParameter("tbl", "STRING", table),
                bigquery.ScalarQueryParameter("wm", "TIMESTAMP", watermark),
                bigquery.ScalarQueryParameter("rows", "INT64", rows),
            ]
        ),
    ).result()


# ---------------------------------------------------------------------
# 적재
# ---------------------------------------------------------------------
def load_batches(bq: bigquery.Client, table_id: str, schema, batches) -> int:
    """행 묶음을 BigQuery 에 이어붙인다. 올린 행 수를 돌려준다."""
    cfg = bigquery.LoadJobConfig(
        schema=schema,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )
    total = 0
    for rows in batches:
        if not rows:
            continue
        bq.load_table_from_json(rows, table_id, job_config=cfg).result()
        total += len(rows)
    return total


def fetch_batches(cur, sql: str, params, colnames: list[str], source: str, loaded_at: str):
    """서버 커서로 흘려 읽어 BATCH_ROWS 씩 넘긴다. 전체를 메모리에 올리지 않는다."""
    cur.execute(sql, params)
    while True:
        chunk = cur.fetchmany(BATCH_ROWS)
        if not chunk:
            return
        yield [
            {
                **{c: to_json_value(v) for c, v in zip(colnames, row)},
                "_source": source,
                "_loaded_at": loaded_at,
            }
            for row in chunk
        ]


def merge_from_temp(bq: bigquery.Client, target_id: str, temp_id: str, cols: list[str], pk: str) -> None:
    assign = ", ".join(f"T.`{c}` = S.`{c}`" for c in cols)
    collist = ", ".join(f"`{c}`" for c in cols)
    srclist = ", ".join(f"S.`{c}`" for c in cols)
    bq.query(
        f"""
        MERGE `{target_id}` T
        USING `{temp_id}` S
          ON T._source = S._source AND T.`{pk}` = S.`{pk}`
        WHEN MATCHED THEN UPDATE SET {assign}
        WHEN NOT MATCHED THEN INSERT ({collist}) VALUES ({srclist})
        """
    ).result()


def load_table(
    bq: bigquery.Client,
    conn,
    meta,
    dataset_id: str,
    source: str,
    table: str,
    spec: dict,
    watermark,
    snapshot_at: datetime,
    full_refresh: bool,
) -> tuple[int, str]:
    cols = pg_columns(meta, table)
    if not cols:
        return 0, "없음"

    colnames = [c[0] for c in cols]
    schema = bq_schema(cols)
    all_cols = colnames + ["_source", "_loaded_at"]
    target_id = f"{dataset_id}.{table}"
    loaded_at = snapshot_at.isoformat()

    mode = spec["mode"]
    incremental = mode == "incremental" and not full_refresh

    ensure_table(bq, target_id, schema, "updated_at" if mode == "incremental" else None)

    if incremental and watermark is not None:
        sql = (
            f'SELECT {", ".join(chr(34) + c + chr(34) for c in colnames)} FROM public."{table}" '
            f'WHERE "{spec["watermark"]}" > %s AND "{spec["watermark"]}" <= %s'
        )
        params = (watermark, snapshot_at)
    else:
        # 첫 적재이거나 full 이다. 스냅샷 시각까지 전부 가져온다.
        sql = f'SELECT {", ".join(chr(34) + c + chr(34) for c in colnames)} FROM public."{table}"'
        params = None

    # 추출은 서버 커서로 흘려 읽는다(테이블마다 새로 연다).
    with conn.cursor(name=f"x_{table}") as cur:
        batches = fetch_batches(cur, sql, params, colnames, source, loaded_at)

        if not incremental or watermark is None:
            # 이 원천의 기존 행만 지운다. 다른 원천 것은 건드리지 않는다.
            # 갓 만든 테이블에는 지울 게 없으므로 DML 을 아낀다.
            if bq.get_table(target_id).num_rows:
                bq.query(
                    f"DELETE FROM `{target_id}` WHERE _source = @s",
                    job_config=bigquery.QueryJobConfig(
                        query_parameters=[bigquery.ScalarQueryParameter("s", "STRING", source)]
                    ),
                ).result()
            return load_batches(bq, target_id, schema, batches), "전체"

        # 증분 — 임시 테이블에 받아서 MERGE 한다.
        # 중간에 죽어도 남지 않도록 만료를 걸어 둔다.
        temp_id = f"{dataset_id}._tmp_{table}_{source}"
        bq.delete_table(temp_id, not_found_ok=True)
        temp = bigquery.Table(temp_id, schema=schema)
        temp.expires = datetime.now(timezone.utc) + timedelta(hours=6)
        bq.create_table(temp)
        try:
            n = load_batches(bq, temp_id, schema, batches)
            if n:
                merge_from_temp(bq, target_id, temp_id, all_cols, spec["pk"])
        finally:
            bq.delete_table(temp_id, not_found_ok=True)
        return n, "증분"


# ---------------------------------------------------------------------
def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["supabase", "local"], required=True)
    ap.add_argument("--table", help="이 테이블 하나만")
    ap.add_argument("--full-refresh", action="store_true", help="워터마크를 무시하고 처음부터")
    ap.add_argument("--dry-run", action="store_true", help="BigQuery 에 쓰지 않고 대상만 보여준다")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    plan = load_manifest()

    if args.table:
        if args.table not in plan:
            sys.exit(f"{args.table} 은 tables.yaml 에 없습니다")
        plan = {args.table: plan[args.table]}

    if args.dry_run:
        for name, spec in plan.items():
            print(f"  {spec['mode']:12} {name}")
        print(f"\n{len(plan)}개 테이블 · 원천 {args.source}")
        return 0

    resolve_credentials()
    project = require_env("GCP_PROJECT_ID")
    location = os.getenv("BQ_LOCATION", "asia-northeast3")
    dataset_id = f"{project}.{os.getenv('BQ_DATASET_RAW', 'raw')}"

    bq = bigquery.Client(project=project, location=location)
    ensure_dataset(bq, dataset_id, location)
    state_id = ensure_state_table(bq, dataset_id)
    watermarks = {} if args.full_refresh else read_watermarks(bq, state_id, args.source)

    total = 0
    with psycopg.connect(pg_dsn(args.source), connect_timeout=60) as conn:
        conn.read_only = True
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        with conn.cursor() as meta:
            # 트랜잭션 시작 시각 하나로 모든 테이블을 끊는다.
            # 테이블마다 now() 를 부르면 그 사이에 들어온 행이 테이블 간에
            # 어긋나 보인다 — vote_item 은 있는데 vote_candidate 는 없는 식으로.
            meta.execute("SELECT now()")
            snapshot_at = meta.fetchone()[0]

            for name, spec in plan.items():
                n, how = load_table(
                    bq, conn, meta, dataset_id, args.source, name, spec,
                    watermarks.get(name), snapshot_at, args.full_refresh,
                )
                total += n
                if spec["mode"] == "incremental":
                    write_watermark(bq, state_id, args.source, name, snapshot_at, n)
                print(f"  {how:4} {name:26} {n:>9,}행")

    print(f"\n적재 완료 — {args.source} → {dataset_id}")
    print(f"  {len(plan)}개 테이블 / {total:,}행")
    return 0


if __name__ == "__main__":
    sys.exit(main())
