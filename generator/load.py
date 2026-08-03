"""
생성된 CSV를 Postgres에 적재한다.

FK 때문에 순서가 중요하다. 부모 테이블이 먼저 들어가야 한다.

적재 후 두 가지를 자동으로 실행한다.
  95_resync_sequences.sql   id를 직접 지정해 넣었으므로, 안 하면 이후 자동 발급이
                            PK 충돌로 실패한다.
  96_backfill_updated_at.sql  증분 워터마크를 각 행의 원래 시각으로 되돌린다.
                            안 하면 3개월치가 적재한 날 하루로 뭉친다.

사용법:
    python generator/load.py                      # .env 설정으로 적재
    python generator/load.py --in /tmp/syn_test   # 다른 위치의 CSV
    python generator/load.py --truncate           # 기존 데이터 지우고
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IN = ROOT / "data" / "synthetic"
RESYNC_SQL = ROOT / "db" / "ddl" / "95_resync_sequences.sql"
BACKFILL_SQL = ROOT / "db" / "ddl" / "96_backfill_updated_at.sql"

# 부모 → 자식 순서. FK 제약을 만족하려면 이 순서를 지켜야 한다.
LOAD_ORDER = [
    "region",
    "school",
    "grade_class",
    "app_user",
    "user_session",
    "user_withdrawal",
    "friend_request",
    "friendship",
    "question",
    "question_request",
    "vote_session",
    "vote_item",
    "vote_candidate",
    "ad_impression",
    "vote_shuffle",
    "vote_received",
    "hint_purchase",
    "heart_purchase",
    "heart_transaction",
    # 게시판 — post 가 있어야 댓글·좋아요·신고가 걸린다
    "post",
    "post_comment",
    "post_like",
    "comment_like",
    # 신고·제재·차단 — report 는 post·comment 를 가리키므로 그 뒤다
    "report",
    "sanction",
    "block_record",
    "rejected_friend_recommendations",
    # 학교 정보 — meal_menu_item 은 meal_plan 을, notice_read 는 notice 를 가리킨다
    "meal_plan",
    "meal_menu_item",
    "school_event",
    "school_notice",
    "school_notice_read",
    "timetable",
]


def connect() -> psycopg.Connection:
    load_dotenv(ROOT / ".env")
    return psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5433")),
        dbname=os.getenv("PGDATABASE", "pingv2"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "test"),
    )


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_dir", type=Path, default=DEFAULT_IN)
    ap.add_argument("--truncate", action="store_true", help="적재 전 기존 데이터 삭제")
    args = ap.parse_args()

    if not args.in_dir.exists():
        print(f"CSV 폴더가 없습니다: {args.in_dir}")
        return 1

    conn = connect()
    conn.autocommit = False
    total = 0

    with conn.cursor() as cur:
        if args.truncate:
            print("기존 데이터 삭제...")
            cur.execute(
                "TRUNCATE "
                + ", ".join(reversed(LOAD_ORDER))
                + " RESTART IDENTITY CASCADE"
            )

        for table in LOAD_ORDER:
            path = args.in_dir / f"{table}.csv"
            if not path.exists():
                print(f"  {table:<22} 건너뜀 (파일 없음)")
                continue

            with open(path, encoding="utf-8") as f:
                header = f.readline().strip().split(",")
                cols = ", ".join(f'"{c}"' for c in header)
                copy_sql = (
                    f"COPY {table} ({cols}) FROM STDIN "
                    "WITH (FORMAT csv, NULL '', ENCODING 'UTF8')"
                )
                with cur.copy(copy_sql) as cp:
                    while chunk := f.read(1 << 20):
                        cp.write(chunk)

            cur.execute(f"SELECT count(*) FROM {table}")
            n = cur.fetchone()[0]
            total += n
            print(f"  {table:<22} {n:>9,}")

    conn.commit()

    # 시퀀스 재동기화 — 명시적 id 삽입 뒤에는 필수
    print("\n시퀀스 재동기화...")
    with conn.cursor() as cur:
        cur.execute(RESYNC_SQL.read_text(encoding="utf-8"))
    conn.commit()

    # 워터마크 되돌리기 — updated_at 의 기본값이 now() 라, 방금 부어 넣은 행이
    # 전부 "적재한 순간"이 된다. 3개월치가 하루에 뭉치고 BigQuery 파티션이
    # 무의미해진다. 각 행의 원래 시각으로 되돌린다.
    if BACKFILL_SQL.exists():
        print("워터마크 되돌리기...")
        with conn.cursor() as cur:
            cur.execute(BACKFILL_SQL.read_text(encoding="utf-8"))
        conn.commit()

    conn.close()

    print(f"\n적재 완료 — 총 {total:,} 행")
    print("다음: python pipeline/extract_load.py --source local --full-refresh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
