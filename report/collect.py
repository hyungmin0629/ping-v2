"""
주간 보고서 · ① 숫자 층 — mart 를 읽어 JSON 하나로 만든다.

    python report/collect.py                      # 지난주(월~일)
    python report/collect.py --week 2026-08-17    # 그 날이 속한 주
    python report/collect.py --source local       # 합성 데이터로

**렌더링과 완전히 분리한다.** 숫자가 틀렸을 때 그림을 뜯어보지 않고
JSON 만 열어보면 되게 하려는 것이다. `render.py` 는 이 파일만 읽는다.

⚠️ **`raw` 를 붙이지 않는다.** 여기서 읽는 것은 `mart` 뿐이다.
   raw 를 한 번이라도 조회하면 1억 2천만 행을 읽어 무료 한도가 사라진다.
   `--max-scan-gib` 가 그 사고를 막는다 — 예상 스캔량을 먼저 재고
   상한을 넘으면 **한 줄도 실행하지 않고** 멈춘다.

⚠️ 주의 시작은 **월요일**이다. `mart_backlog_weekly` 가 이미 그 기준이다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "pipeline"))

from extract_load import require_env, resolve_credentials  # noqa: E402

QUERIES = HERE / "queries"
OUT = HERE / "out"

# JSON 의 키 이름. 파일 번호가 아니라 이 이름으로 렌더러가 찾는다.
SECTIONS = {
    "01_freshness":        "freshness",
    "10_weekly_core":      "weeks",
    "20_funnel_user":      "funnel_user",
    "30_funnel_received":  "funnel_received",
    "40_cohort":           "cohort",
    "50_segments":         "segments",
    "60_heart_flow":       "heart_flow",
    "70_backlog":          "backlog",
    "80_stage":            "stage",
}


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def default_week() -> date:
    """지난주 월요일. **이번 주를 뽑지 않는다** — 아직 안 끝난 주라
    금요일에 돌리면 5일치가 한 주로 보고된다."""
    return monday_of(date.today()) - timedelta(days=7)


def jsonable(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--week", help="그 날이 속한 주(월요일 시작). 없으면 지난주")
    ap.add_argument("--source", default=os.getenv("WEEKLY_REPORT_SOURCE", "supabase"),
                    choices=["supabase", "local"])
    ap.add_argument("--max-scan-gib", type=float, default=5.0,
                    help="예상 스캔량 상한. 넘으면 한 줄도 실행하지 않는다")
    ap.add_argument("--out", help="JSON 경로. 없으면 report/out/weekly-<주>.json")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    resolve_credentials()
    project = require_env("GCP_PROJECT_ID")
    mart = f"{project}.{os.getenv('BQ_DATASET_MART', 'mart')}"
    location = os.getenv("BQ_LOCATION", "asia-northeast3")
    bq = bigquery.Client(project=project, location=location)

    week_start = monday_of(date.fromisoformat(args.week)) if args.week else default_week()
    week_end = week_start + timedelta(days=6)
    print(f"보고 주간 {week_start} ~ {week_end}  원천 {args.source}")

    params = [
        bigquery.ScalarQueryParameter("week_start", "DATE", week_start),
        bigquery.ScalarQueryParameter("source", "STRING", args.source),
    ]
    files = sorted(QUERIES.glob("*.sql"))
    sqls = {p.stem: p.read_text(encoding="utf-8").replace("{{mart}}", mart) for p in files}

    # ① 먼저 전부 재본다. 절반 실행하고 상한에 걸리는 것이 제일 나쁘다 —
    #    돈은 이미 나갔는데 결과는 없다.
    est = 0
    for name, sql in sqls.items():
        cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False, query_parameters=params)
        try:
            est += bq.query(sql, job_config=cfg).total_bytes_processed or 0
        except Exception as e:
            print(f"❌ {name}.sql 문법 오류\n   {str(e).splitlines()[0]}")
            return 1
    gib = est / 1024**3
    print(f"예상 스캔량 {gib:.3f} GiB (상한 {args.max_scan_gib})")
    if gib > args.max_scan_gib:
        print("❌ 상한을 넘어 멈춥니다. mart 가 아닌 것을 읽고 있지 않은지 보세요.")
        return 1

    # ② 실행
    data: dict = {
        "meta": {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "source": args.source,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "project": project,
            "scanned_gib": round(gib, 4),
        }
    }
    for name, sql in sqls.items():
        key = SECTIONS.get(name, name)
        cfg = bigquery.QueryJobConfig(query_parameters=params)
        rows = [{k: jsonable(v) for k, v in dict(r).items()}
                for r in bq.query(sql, job_config=cfg).result()]
        data[key] = rows[0] if key == "freshness" and rows else rows
        print(f"  {name:<20} {len(rows):>4}행")

    OUT.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else OUT / f"weekly-{week_start}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
