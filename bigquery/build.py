"""
stg / mart 빌드 (P6).

`bigquery/staging/*.sql` 과 `bigquery/mart/*.sql` 을 **파일 이름 순서대로** 실행한다.
순서가 있는 이유는 mart 가 stg 를 읽고, stg 안에서도 뒤 파일이 앞 뷰를 참조하기
때문이다. 그래서 파일 이름에 `10_` `20_` 같은 번호를 붙인다.

두 층의 성격이 다르다.

  staging  **뷰**로 만든다. 저장 용량이 0 이다 — raw 가 이미 8.74 GiB 라
           무료 한도 10 GiB 의 여유가 1 GiB 남짓뿐이다. stg 를 테이블로 구우면
           그 여유가 사라진다. 뷰는 조회할 때마다 raw 를 다시 읽지만,
           **사람과 mart 만 읽으므로** 그 비용은 작다.

  mart     **테이블**로 만든다. 집계된 뒤라 작고(수천~수만 행),
           대시보드가 하루에 수십 번 읽기 때문이다. 뷰로 두면 루커 스튜디오가
           화면을 그릴 때마다 1억 2천만 행을 다시 읽는다.

SQL 파일 안에서는 데이터셋 이름을 직접 쓰지 않고 자리표시자를 쓴다.
`.env` 가 바뀌어도 SQL 을 고칠 필요가 없게 하려는 것이다.

    {{raw}}   → ping-v2-503916.raw
    {{stg}}   → ping-v2-503916.stg
    {{mart}}  → ping-v2-503916.mart

사용법:
    python bigquery/build.py --layer stg --dry-run   # 문법·스캔량만 확인
    python bigquery/build.py --layer stg
    python bigquery/build.py --layer mart
    python bigquery/build.py --layer all
    python bigquery/build.py --only mart_user
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "pipeline"))

from extract_load import require_env, resolve_credentials  # noqa: E402

LAYERS = {"stg": HERE / "staging", "mart": HERE / "mart"}


def datasets() -> dict[str, str]:
    project = require_env("GCP_PROJECT_ID")
    return {
        "raw": f"{project}.{os.getenv('BQ_DATASET_RAW', 'raw')}",
        "stg": f"{project}.{os.getenv('BQ_DATASET_STG', 'stg')}",
        "mart": f"{project}.{os.getenv('BQ_DATASET_MART', 'mart')}",
    }


def ensure_dataset(bq: bigquery.Client, dataset_id: str, location: str) -> None:
    """데이터셋이 없으면 만든다. 있으면 아무 일도 하지 않는다."""
    try:
        bq.get_dataset(dataset_id)
    except NotFound:
        ds = bigquery.Dataset(dataset_id)
        ds.location = location
        bq.create_dataset(ds)
        print(f"  데이터셋 생성 {dataset_id} ({location})")


def render(sql: str, ds: dict[str, str]) -> str:
    for key, value in ds.items():
        sql = sql.replace("{{" + key + "}}", value)
    return sql


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", choices=["stg", "mart", "all"], default="all")
    ap.add_argument("--only", help="파일 이름 일부. 그 파일 하나만 돌린다")
    ap.add_argument("--dry-run", action="store_true",
                    help="실행하지 않고 문법과 예상 스캔량만 본다")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    resolve_credentials()
    ds = datasets()
    location = os.getenv("BQ_LOCATION", "asia-northeast3")
    bq = bigquery.Client(project=require_env("GCP_PROJECT_ID"), location=location)

    order = ["stg", "mart"] if args.layer == "all" else [args.layer]
    files: list[tuple[str, Path]] = []
    for layer in order:
        for path in sorted(LAYERS[layer].glob("*.sql")):
            if args.only and args.only not in path.stem:
                continue
            files.append((layer, path))

    if not files:
        print("돌릴 SQL 파일이 없습니다.")
        return 1

    # --dry-run 이어도 데이터셋은 만든다. CREATE VIEW 는 문법 검사조차
    # 대상 데이터셋이 있어야 통과하기 때문이다(빈 데이터셋은 저장비가 0 이다).
    for layer in order:
        ensure_dataset(bq, ds[layer], location)

    total = 0
    for layer, path in files:
        sql = render(path.read_text(encoding="utf-8"), ds)
        cfg = bigquery.QueryJobConfig(dry_run=args.dry_run, use_query_cache=False)
        try:
            job = bq.query(sql, job_config=cfg)
            if args.dry_run:
                scanned = job.total_bytes_processed
            else:
                job.result()
                scanned = job.total_bytes_processed or 0
        except Exception as e:  # 어느 파일에서 깨졌는지 이름과 함께 알려준다
            print(f"❌ {layer}/{path.name}\n   {str(e).splitlines()[0]}")
            return 1
        total += scanned
        mark = "확인" if args.dry_run else "생성"
        print(f"  {mark}  {layer:4} {path.stem:28} 스캔 {scanned / 2**30:7.3f} GiB")

    print(f"\n{len(files)}개 파일 · 스캔 합계 {total / 2**30:,.3f} GiB "
          f"(월 1 TiB 무료 한도의 {total / 2**30 / 1024 * 100:.3f}%)")
    if args.dry_run:
        print("문법 확인만 했습니다. 실제로 만들려면 --dry-run 을 빼고 다시 돌리세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
