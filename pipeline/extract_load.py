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
#
# `--batch-rows` 로 키울 수 있다. 키우는 이유는 속도가 아니라 **적재 작업 수**다 —
# BigQuery 는 **테이블당 하루 1,500건**까지만 받는데, 합성 1억 2,370만 행을
# 5만씩 끊으면 vote_candidate 하나가 1,342건이다. 한 번 실패하면 그날은 다시
# 못 돌린다. 20만으로 키우면 336건이라 재시도 여유가 생긴다.
# 대신 한 덩어리가 통째로 메모리에 올라가므로 무한정 키우지는 않는다.
BATCH_ROWS = 50_000

STATE_TABLE = "_load_state"

# 워터마크를 스냅샷 시각보다 이만큼 뒤로 물려 저장한다.
#
# 왜 필요한가 — 워터마크 경합.
#   updated_at 은 트리거가 now() 로 채우는데, now() 는 **트랜잭션이 시작한
#   시각**이다. 쓰기 트랜잭션 W 가 09:00:00 에 시작해 updated_at=09:00:00 을
#   박고 09:00:02 에 커밋한다고 하자. 적재가 09:00:01 에 스냅샷을 뜨면
#   W 는 아직 커밋 전이라 **보이지 않는다.** 그런데 워터마크는 09:00:01 로
#   전진한다. 다음 적재는 `updated_at > 09:00:01` 을 뜨므로 W 의 행
#   (updated_at=09:00:00)은 **영원히 걸리지 않는다.**
#
#   그래서 워터마크를 5분 물려 저장하고, 매번 최근 5분치를 다시 읽는다.
#   MERGE 는 같은 행을 몇 번 읽어도 결과가 같으므로(멱등) 손해는 재읽기뿐이다.
#   5분은 이 앱의 트랜잭션 길이(RPC 하나, 밀리초 단위)보다 압도적으로 길다.
WATERMARK_LAG = timedelta(minutes=5)

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
    # 원천에서 사라진 행에 찍는다. 행을 지우지는 않는다 — raw 는 이력을 잃지 않는다.
    # 이게 없으면 지워진 계정과 살아 있는 계정을 **분간할 수 없다.**
    fields.append(bigquery.SchemaField("_deleted_at", "TIMESTAMP", mode="NULLABLE"))
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
        table = bq.get_table(table_id)
    except NotFound:
        table = None

    if table is not None:
        # 원천에 컬럼이 생겼으면 따라간다.
        # 합성 데이터 생성기를 다시 만들면 스키마가 같이 바뀐다. 그때마다
        # 손으로 ALTER 하게 두면 적재가 "컬럼이 없다"로 죽는다.
        have = {f.name for f in table.schema}
        added = [f for f in schema if f.name not in have]
        if added:
            # 이미 행이 있는 테이블에는 REQUIRED 를 붙일 수 없다(기존 행이 NULL).
            table.schema = list(table.schema) + [
                bigquery.SchemaField(f.name, f.field_type, mode="NULLABLE") for f in added
            ]
            table = bq.update_table(table, ["schema"])
            print(f"  컬럼 추가  {table_id.split('.')[-1]} ← {', '.join(f.name for f in added)}")
        # 사라진 컬럼은 지우지 않는다. 지우면 과거 데이터를 잃는다.
        # 앞으로 들어오는 행에서 NULL 로 남을 뿐이다.
        return table
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
    bq: bigquery.Client,
    state_id: str,
    source: str,
    table: str,
    watermark,
    rows: int,
    reset: bool,
) -> None:
    """워터마크를 전진시킨다.

    row_count 는 **그 원천에서 지금까지 옮긴 누적 행 수**다. 테이블의 현재
    크기가 아니다(갱신된 행은 여러 번 세어진다). 전체 재적재는 앞의 기록을
    무의미하게 만들므로 그때는 누적을 0부터 다시 센다.
    """
    bq.query(
        f"""
        MERGE `{state_id}` T
        USING (SELECT @src AS source, @tbl AS table_name) S
          ON T.source = S.source AND T.table_name = S.table_name
        WHEN MATCHED THEN UPDATE SET
            watermark = @wm,
            row_count = IF(@reset, @rows, T.row_count + @rows),
            loaded_at = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN INSERT (source, table_name, watermark, row_count, loaded_at)
            VALUES (@src, @tbl, @wm, @rows, CURRENT_TIMESTAMP())
        """,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("src", "STRING", source),
                bigquery.ScalarQueryParameter("tbl", "STRING", table),
                bigquery.ScalarQueryParameter("wm", "TIMESTAMP", watermark),
                bigquery.ScalarQueryParameter("rows", "INT64", rows),
                bigquery.ScalarQueryParameter("reset", "BOOL", reset),
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


def mark_deleted(bq: bigquery.Client, conn, dataset_id: str, source: str,
                 table: str, pk: str, snapshot_at: datetime) -> int:
    """원천에서 사라진 행에 `_deleted_at` 을 찍는다.

    왜 필요한가 — 증분 MERGE 는 INSERT/UPDATE 만 한다(그건 의도된 설계다.
    raw 는 이력을 지우지 않는다). 그런데 표시가 없으면 **지워진 행과 살아 있는
    행을 분간할 수 없다.**

    2026-07-30 에 실제로 물렸다. 시험 계정을 정리한 뒤 "오늘 투표한 수"를 물었더니
    이미 지운 투표 20건이 오늘 것으로 셈해졌다. 쿼리는 오류를 내지 않았다.

    원천의 PK 전부를 임시 테이블로 올려 대조한다. 행이 많은 원천에서는 비싸므로
    실유저(supabase)에만 기본으로 돈다 — 합성 데이터는 재생성 때 통째로
    갈아끼우므로(--full-refresh) 유령이 생기지 않는다.
    """
    target_id = f"{dataset_id}.{table}"
    temp_id = f"{dataset_id}._live_{table}_{source}"

    with conn.cursor(name=f"pk_{table}") as cur:
        cur.execute(f'SELECT "{pk}" FROM public."{table}"')
        rows = [{"k": to_json_value(r[0])} for r in cur.fetchall()]

    schema = [bigquery.SchemaField("k", "STRING")]
    bq.delete_table(temp_id, not_found_ok=True)
    temp = bigquery.Table(temp_id, schema=schema)
    temp.expires = datetime.now(timezone.utc) + timedelta(hours=6)
    bq.create_table(temp)
    try:
        if rows:
            load_batches(bq, temp_id, schema, (rows[i:i + BATCH_ROWS]
                                               for i in range(0, len(rows), BATCH_ROWS)))
        job = bq.query(
            f"""
            UPDATE `{target_id}` T
               SET _deleted_at = @ts
             WHERE T._source = @src
               AND T._deleted_at IS NULL
               AND CAST(T.`{pk}` AS STRING) NOT IN (SELECT k FROM `{temp_id}`)
            """,
            job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("src", "STRING", source),
                bigquery.ScalarQueryParameter("ts", "TIMESTAMP", snapshot_at),
            ]),
        )
        job.result()
        return job.num_dml_affected_rows or 0
    finally:
        bq.delete_table(temp_id, not_found_ok=True)


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

    target = ensure_table(bq, target_id, schema, "updated_at" if mode == "incremental" else None)
    # 대상 테이블에 적재할 때는 **대상의 스키마**를 쓴다. 원천에서 사라진 컬럼이
    # BigQuery 에는 남아 있을 수 있는데, 그걸 뺀 스키마로 올리면 적재가 거부된다.
    # 없는 값은 NULL 로 들어간다.
    target_schema = list(target.schema)

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
        # ⚠️ 파티션 컬럼 순서로 꺼낸다. 성능이 아니라 **한도** 때문이다.
        #
        # BigQuery 는 파티션 테이블 하나에 **하루 4,000회**의 파티션 수정만 받는다.
        # 적재 작업 하나가 N개 파티션에 걸치면 N회를 먹는다. 저장 순서대로 꺼내면
        # 20만 행 한 덩어리가 30일치에 흩어져 작업당 30회씩 나가고, 6,708만 행짜리
        # vote_candidate 는 131건 만에 한도가 찬다 — 2026-08-06 에 실제로 막혔다.
        #
        # 파티션 컬럼으로 정렬해 꺼내면 한 덩어리가 하루치 안에 들어가 1~2회로 떨어진다.
        # (일 20만 행 규모라 20만 배치와 거의 일치한다.) `updated_at` 에는
        # 인덱스가 있어 정렬 비용도 들지 않는다.
        if mode == "incremental":
            sql += f' ORDER BY "{spec["watermark"]}"'

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
            return load_batches(bq, target_id, target_schema, batches), "전체"

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
    global BATCH_ROWS

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["supabase", "local"], required=True)
    ap.add_argument("--table", help="이 테이블 하나만")
    ap.add_argument("--exclude", default="",
                    help="이 테이블은 빼고 (쉼표로 여러 개). 한도에 걸린 표를 "
                         "건너뛰고 나머지를 마저 올릴 때 쓴다")
    ap.add_argument("--full-refresh", action="store_true", help="워터마크를 무시하고 처음부터")
    ap.add_argument("--dry-run", action="store_true", help="BigQuery 에 쓰지 않고 대상만 보여준다")
    ap.add_argument("--no-mark-deleted", action="store_true",
                    help="원천에서 사라진 행에 _deleted_at 을 찍지 않는다")
    ap.add_argument("--batch-rows", type=int, default=BATCH_ROWS,
                    help=f"한 적재 작업에 올리는 행 수 (기본 {BATCH_ROWS:,})")
    args = ap.parse_args()

    if args.batch_rows < 1:
        sys.exit("--batch-rows 는 1 이상이어야 합니다")
    BATCH_ROWS = args.batch_rows

    load_dotenv(ROOT / ".env")
    plan = load_manifest()

    if args.table:
        if args.table not in plan:
            sys.exit(f"{args.table} 은 tables.yaml 에 없습니다")
        plan = {args.table: plan[args.table]}

    skip = {t.strip() for t in args.exclude.split(",") if t.strip()}
    unknown = skip - set(plan)
    if unknown:
        sys.exit(f"--exclude 에 없는 테이블: {', '.join(sorted(unknown))}")
    if skip:
        plan = {k: v for k, v in plan.items() if k not in skip}
        print(f"  건너뜀  {', '.join(sorted(skip))}")

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
    tombstoned = 0
    # 합성 원천에서는 기본으로 끈다. PK 786만 개를 올려 대조하는 값이 얻는 것보다
    # 크고, 재생성은 --full-refresh 라 애초에 유령이 생기지 않는다.
    mark_del = not args.no_mark_deleted and args.source == "supabase"
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
                    write_watermark(
                        bq, state_id, args.source, name,
                        snapshot_at - WATERMARK_LAG, n, args.full_refresh,
                    )
                    if mark_del:
                        gone = mark_deleted(bq, conn, dataset_id, args.source,
                                            name, spec["pk"], snapshot_at)
                        if gone:
                            tombstoned += gone
                            how = f"{how}·삭제{gone}"
                print(f"  {how:6} {name:26} {n:>9,}행")

    print(f"\n적재 완료 — {args.source} → {dataset_id}")
    print(f"  {len(plan)}개 테이블 / {total:,}행")
    if tombstoned:
        print(f"  원천에서 사라진 {tombstoned:,}행에 _deleted_at 을 찍었습니다")
        print("  (행은 지우지 않는다. 분석에서는 `_deleted_at IS NULL` 로 거른다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
