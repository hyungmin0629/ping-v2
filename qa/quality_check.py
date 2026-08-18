"""
BigQuery raw 품질 검증 (P5).

적재가 **끝났는지**는 `pipeline/verify_load.py` 가 센다(원천 대 BigQuery 행 수).
이 스크립트는 그 다음 질문을 본다 — **올라온 행을 믿어도 되는가.**

raw 층은 일부러 제약이 없다. `extract_load.py` 가 모든 컬럼을 NULLABLE 로 만들고
외래키도 걸지 않는다. 원천 스키마가 느슨해질 때 적재가 통째로 죽지 않게 하려는
선택이고, 그래서 **검증은 적재 시점이 아니라 여기서** 한다.

검사는 손으로 적지 않는다. `docs/erd.json`(살아 있는 Supabase 스키마에서
`db/erd.py` 가 뽑은 것)을 읽어 표마다 자동으로 만든다 — 표가 늘면 검사도 는다.

  1. 유일성    (_source, id) 가 중복되지 않는가          — MERGE 키가 깨지면 여기서 드러난다
  2. 필수값    원천이 NOT NULL 인 컬럼에 NULL 이 없는가   — 컬럼 추가 후 워터마크가 멈추면 생긴다
  3. 참조      부모가 없는 자식 행이 없는가               — 같은 _source 안에서만 본다
  4. 시각      미래 시각 · 뒤집힌 순서가 없는가
  5. 적재 상태 워터마크가 언제 것인가 (정보)

사용법:
    python qa/quality_check.py --source local --estimate   # 스캔량만 보고 끝
    python qa/quality_check.py --source local
    python qa/quality_check.py --source supabase
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv
from google.cloud import bigquery

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))

from extract_load import require_env, resolve_credentials  # noqa: E402

ERD = ROOT / "docs" / "erd.json"
MANIFEST = ROOT / "pipeline" / "tables.yaml"
REPORTS = ROOT / "qa" / "reports"

# 한 번에 UNION ALL 로 묶는 검사 수. 크게 묶으면 왕복이 줄지만 쿼리 하나가 길어져
# 실패했을 때 어디가 문제인지 보기 어렵다.
CHUNK = 12

# 시각 순서 검사 — "뒤가 앞보다 이르면 안 된다". 표마다 다르므로 손으로 적는다.
TIME_ORDER = [
    ("vote_item", "voted_at", "served_at"),
    ("vote_session", "completed_at", "started_at"),
    ("user_session", "ended_at", "started_at"),
    ("ad_impression", "completed_at", "started_at"),
    ("heart_purchase", "completed_at", "created_at"),
    ("sanction", "ends_at", "starts_at"),
    ("vote_received", "read_at", "created_at"),
    ("vote_received", "answered_at", "created_at"),
    ("friendship", "ended_at", "created_at"),
]


def load_schema() -> tuple[dict, dict]:
    """erd.json → {표: 컬럼목록}, tables.yaml → {표: PK 컬럼}."""
    erd = json.loads(ERD.read_text(encoding="utf-8"))
    cols = {t["name"]: t["columns"] for t in erd["tables"]}

    m = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    overrides = m.get("pk_overrides") or {}
    default_pk = m["defaults"]["pk"]
    pks = {name: overrides.get(name, default_pk) for name in (m["full"] + m["incremental"])}
    return cols, pks


def build_checks(cols: dict, pks: dict, raw: str) -> list[tuple[str, str, str]]:
    """(구분, 이름, SQL) 목록. SQL 은 전부 `check_id, n` 두 컬럼을 낸다."""
    checks: list[tuple[str, str, str]] = []

    def add(kind: str, name: str, sql: str) -> None:
        checks.append((kind, name, " ".join(sql.split())))

    for table, columns in sorted(cols.items()):
        names = {c["name"] for c in columns}
        pk = pks.get(table, "id")
        live = "_source = @s AND _deleted_at IS NULL"

        # 1. 유일성 — 같은 원천 안에서 PK 가 두 번 나오면 MERGE 키가 깨진 것이다.
        add("유일성", f"{table}.{pk}", f"""
            SELECT '유일성|{table}.{pk}' AS check_id, COUNT(*) AS n FROM (
              SELECT {pk} FROM `{raw}.{table}` WHERE _source = @s
              GROUP BY {pk} HAVING COUNT(*) > 1)
        """)

        # 2. 필수값 — 원천이 NOT NULL 인데 raw 에 NULL 이 있으면 적재가 놓친 것이다.
        #    컬럼을 추가해도 updated_at 이 안 움직여 증분이 못 잡는 경우가 실제로 있었다.
        for c in columns:
            if c["null"]:
                continue
            add("필수값", f"{table}.{c['name']}", f"""
                SELECT '필수값|{table}.{c['name']}' AS check_id,
                       COUNTIF({c['name']} IS NULL) AS n
                FROM `{raw}.{table}` WHERE {live}
            """)

        # 3. 참조 — 부모를 **같은 원천에서만** 찾는다. _source 를 빼면 실유저의
        #    투표에 합성 유저가 붙어도 통과한다(두 원천의 id 가 실제로 겹친다).
        for c in columns:
            parent = c["fk"]
            if not parent or parent.startswith("auth."):
                continue  # auth.users 는 Supabase 내부 표라 BigQuery 에 없다
            ppk = pks.get(parent, "id")
            add("참조", f"{table}.{c['name']}→{parent}", f"""
                SELECT '참조|{table}.{c['name']}→{parent}' AS check_id, COUNT(*) AS n
                FROM `{raw}.{table}` AS c
                LEFT JOIN (SELECT {ppk} AS k FROM `{raw}.{parent}` WHERE _source = @s) AS p
                  ON p.k = c.{c['name']}
                WHERE c._source = @s AND c._deleted_at IS NULL
                  AND c.{c['name']} IS NOT NULL AND p.k IS NULL
            """)

        # 4-a. 미래 시각 — 적재 오류나 원천의 시계 문제. 파티션도 함께 어긋난다.
        if "updated_at" in names:
            add("시각", f"{table}.updated_at 미래", f"""
                SELECT '시각|{table}.updated_at 미래' AS check_id,
                       COUNTIF(updated_at > CURRENT_TIMESTAMP()) AS n
                FROM `{raw}.{table}` WHERE {live}
            """)

    # 4-b. 순서가 뒤집힌 시각
    for table, later, earlier in TIME_ORDER:
        add("시각", f"{table}.{later}<{earlier}", f"""
            SELECT '시각|{table}.{later}<{earlier}' AS check_id,
                   COUNTIF({later} < {earlier}) AS n
            FROM `{raw}.{table}`
            WHERE _source = @s AND _deleted_at IS NULL AND {later} IS NOT NULL
        """)

    return checks


def chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def run(bq: bigquery.Client, sqls: list[str], source: str, dry: bool = False):
    """묶음 하나를 실행한다. dry=True 면 스캔량만 재고 결과는 비운다."""
    union = "\nUNION ALL\n".join(sqls)
    cfg = bigquery.QueryJobConfig(
        dry_run=dry,
        use_query_cache=not dry,
        query_parameters=[bigquery.ScalarQueryParameter("s", "STRING", source)],
    )
    job = bq.query(union, job_config=cfg)
    if dry:
        return job.total_bytes_processed, {}
    rows = {r.check_id: r.n for r in job.result()}
    return job.total_bytes_processed, rows


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["supabase", "local"], required=True)
    ap.add_argument("--estimate", action="store_true", help="스캔량만 재고 끝낸다")
    ap.add_argument("--max-scan-gib", type=float, default=20.0,
                    help="예상 스캔량이 이보다 크면 멈춘다 (쿼리 무료 한도는 월 1 TiB)")
    ap.add_argument("--yes", action="store_true", help="스캔량 확인 없이 실행")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    resolve_credentials()
    project = require_env("GCP_PROJECT_ID")
    raw = f"{project}.{os.getenv('BQ_DATASET_RAW', 'raw')}"
    bq = bigquery.Client(project=project, location=os.getenv("BQ_LOCATION", "asia-northeast3"))

    cols, pks = load_schema()
    checks = build_checks(cols, pks, raw)
    print(f"검사 {len(checks)}개 · 원천 {args.source} · {raw}\n")

    # 먼저 얼마나 스캔하는지 잰다. 쿼리 무료 한도는 월 1 TiB 뿐이고
    # 이 검사는 매번 돌 물건이라, 비용을 모르고 켜지 않는다.
    batches = list(chunks([c[2] for c in checks], CHUNK))
    total_bytes = sum(run(bq, b, args.source, dry=True)[0] for b in batches)
    gib = total_bytes / 2**30
    print(f"예상 스캔량 {gib:,.3f} GiB — 월 1 TiB 무료 한도의 {gib / 1024 * 100:.3f}%")
    if args.estimate:
        return 0
    if gib > args.max_scan_gib and not args.yes:
        print(f"\n예상 스캔량이 --max-scan-gib({args.max_scan_gib}) 를 넘습니다.")
        print("그래도 돌리려면 --yes 를 붙이세요.")
        return 2

    results: dict[str, int] = {}
    for i, b in enumerate(batches, 1):
        print(f"  묶음 {i}/{len(batches)} 실행 중…", end="\r")
        results.update(run(bq, b, args.source)[1])
    print(" " * 40, end="\r")

    # 결과 정리 — 위반이 있는 것만 보여주고 나머지는 구분별로 세어 요약한다.
    by_kind: dict[str, list[tuple[str, int]]] = {}
    for kind, name, _ in checks:
        n = results.get(f"{kind}|{name}", 0)
        by_kind.setdefault(kind, []).append((name, n))

    lines = []
    failed = 0
    for kind in ["유일성", "필수값", "참조", "시각"]:
        items = by_kind.get(kind, [])
        bad = [(n, v) for n, v in items if v]
        failed += len(bad)
        mark = "❌" if bad else "✅"
        lines.append(f"{mark} {kind}  {len(items) - len(bad)}/{len(items)} 통과")
        for n, v in sorted(bad, key=lambda x: -x[1]):
            lines.append(f"     {n}  위반 {v:,}행")

    # 5. 적재 상태 — 검사가 아니라 정보다. 워터마크가 멈춰 있으면
    #    위 검사는 전부 통과하면서 데이터만 조용히 낡는다.
    state = list(bq.query(
        f"""SELECT table_name, watermark FROM `{raw}._load_state`
            WHERE source = @s ORDER BY watermark""",
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("s", "STRING", args.source)]
        ),
    ).result())
    lines.append("")
    if state:
        oldest, newest = state[0], state[-1]
        lines.append(
            f"ℹ️  워터마크 {len(state)}개 · 가장 오래된 {oldest.table_name} "
            f"{oldest.watermark:%Y-%m-%d %H:%M} · 가장 최근 {newest.table_name} "
            f"{newest.watermark:%Y-%m-%d %H:%M} (UTC)"
        )
    else:
        lines.append("ℹ️  워터마크 없음 — full 적재만 했거나 아직 증분이 안 돌았습니다")

    print("\n".join(lines))

    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = REPORTS / f"quality-{stamp}-{args.source}.md"
    out.write_text(
        f"# 품질 검증 · {args.source} · {stamp}\n\n"
        f"검사 {len(checks)}개 · 위반 {failed}개 · 스캔 {gib:,.3f} GiB\n\n```\n"
        + "\n".join(lines)
        + "\n```\n",
        encoding="utf-8",
    )
    print(f"\n리포트 → {out.relative_to(ROOT)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
