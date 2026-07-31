"""
NEIS 에서 학사일정을 받아 적재한다. (W8)

왜 미리 받아두나:
    급식과 같다. NEIS 인증키는 서버 비밀이라 브라우저가 직접 부를 수 없다.
    받아서 DB 에 넣어두고, 앱은 RLS 를 통해 자기 학교 것만 읽는다.

어느 학교 이름으로 저장하나:
    급식과 같다. **실제 데이터를 제공한 학교**(서울고등학교) 아래 저장하고,
    테스트 조직은 school.info_school_id 로 그 학교를 가리킨다.

NEIS 는 하루씩 준다 — 우리는 기간으로 묶는다:
    "여름방학"이 7월 20일부터 8월 17일까지면 NEIS 는 **29개 행**을 준다.
    그대로 넣으면 달력이 방학으로 도배되고, 목록에도 같은 이름이 29번 나온다.
    school_event 가 start_date/end_date 를 따로 가진 것이 이걸 하라는 뜻이라
    이어지는 날짜를 하나로 합친다.

    주말은 건너뛴다 — 학교가 토·일에 일정을 안 넣는 경우가 많아서,
    끊긴 것으로 보면 "1학기 기말고사"가 주 단위로 쪼개진다.

다시 받으면 어떻게 되나:
    합치는 범위가 바뀔 수 있어(뒤에 하루가 더 붙는 등) ON CONFLICT 로는
    옛 조각이 남는다. 그래서 **받은 기간의 NEIS 행을 지우고 다시 넣는다.**
    사람이 손댄 행(is_manually_overridden)은 지우지 않는다.

사용법:
    python db/neis_events.py --school "서울고등학교"
    python db/neis_events.py --school 7010083 --from 20260301 --to 20270228
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import psycopg
from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
from neis_schools import call, env, find_school  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# 제목에서 종류를 읽는다. NEIS 는 종류를 주지 않고 이름과 휴업일 여부만 준다.
# 위에서부터 먼저 걸리는 것을 쓴다 — "방학식"은 CEREMONY 가 아니라 HOLIDAY 다.
EVENT_KINDS: list[tuple[str, tuple[str, ...]]] = [
    ("HOLIDAY",    ("방학", "휴업", "휴일", "재량", "개교기념")),
    ("EXAM",       ("고사", "시험", "평가", "수능", "모의", "학력")),
    ("FIELD_TRIP", ("수학여행", "수련", "체험", "현장", "소풍", "답사", "견학")),
    ("CEREMONY",   ("입학", "졸업", "개학", "종업", "기념식", "체육대회", "축제", "발표회")),
]

# NEIS 의 학년별 해당 여부 컬럼. 순서가 곧 학년이다.
GRADE_FIELDS = [
    "ONE_GRADE_EVENT_YN", "TW_GRADE_EVENT_YN", "THREE_GRADE_EVENT_YN",
    "FR_GRADE_EVENT_YN", "FIV_GRADE_EVENT_YN", "SIX_GRADE_EVENT_YN",
]


# 학교가 안 여는 날. NEIS 는 나머지에 "해당없음"이라는 **문자열**을 넣는다 —
# 빈 값이 아니다. 처음에 그걸 놓쳐 299건이 전부 휴업일로 들어갔다.
CLOSED_DAYS = {"휴업일", "공휴일"}


def classify(title: str, closed: str) -> str:
    """제목으로 종류를 정한다. 못 알아보면 ETC 다.

    학교가 안 여는 날로 표시돼 있으면(SBTR_DD_SC_NM) 이름과 상관없이
    HOLIDAY 다 — "재량휴업"처럼 이름이 제각각이라 제목만으로는 놓친다.
    """
    if closed.strip() in CLOSED_DAYS:
        return "HOLIDAY"
    for kind, words in EVENT_KINDS:
        if any(word in title for word in words):
            return kind
    return "ETC"


def grade_of(row: dict) -> int | None:
    """딱 한 학년만 해당하면 그 학년, 아니면 NULL(전교).

    두세 학년에 걸치는 일정은 표현할 방법이 없다 — grade_scope 가 숫자
    하나다. 그런 경우는 전교로 두는 편이 낫다. 한 학년 것을 전교로 보여주는
    쪽이, 3학년 일정을 1학년에게 감추는 것보다 덜 틀리기 때문이다.
    """
    marked = [i + 1 for i, f in enumerate(GRADE_FIELDS)
              if (row.get(f) or "").strip().upper() == "Y"]
    return marked[0] if len(marked) == 1 else None


def merge_spans(days: list[dt.date]) -> list[tuple[dt.date, dt.date]]:
    """이어지는 날짜를 기간으로 묶는다. 사이에 낀 주말은 이어진 것으로 본다."""
    spans: list[tuple[dt.date, dt.date]] = []
    for day in sorted(days):
        if spans and bridged(spans[-1][1], day):
            spans[-1] = (spans[-1][0], day)
        else:
            spans.append((day, day))
    return spans


def bridged(last: dt.date, day: dt.date) -> bool:
    """last 와 day 사이가 비어 있거나 주말뿐인가."""
    if day <= last:
        return True
    gap = [last + dt.timedelta(days=n) for n in range(1, (day - last).days)]
    return all(d.weekday() >= 5 for d in gap)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    today = dt.date.today()
    ap = argparse.ArgumentParser()
    ap.add_argument("--school", required=True, metavar="학교명|학교코드")
    ap.add_argument("--from", dest="date_from", default=f"{today.year}0101")
    ap.add_argument("--to", dest="date_to", default=f"{today.year}1231")
    args = ap.parse_args()

    key = env("NEIS_API_KEY")
    with psycopg.connect(env("SUPABASE_DB_URL"), connect_timeout=30) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            school_id, name, school_code, office_code = find_school(cur, args.school)
            if not office_code:
                sys.exit(f"{name} 에 교육청코드가 없습니다. neis_schools.py --schools 를 먼저.")

            rows = call("SchoolSchedule", key,
                        ATPT_OFCDC_SC_CODE=office_code, SD_SCHUL_CODE=school_code,
                        AA_FROM_YMD=args.date_from, AA_TO_YMD=args.date_to)
            print(f"{name} — {args.date_from}~{args.date_to} 학사일정 {len(rows)}건 받음")

            # 같은 일정의 날짜들을 모은다. 종류·학년까지 같아야 한 덩어리다 —
            # 이름만 같고 학년이 다르면 다른 일정이다("체험학습" 1학년/2학년).
            buckets: dict[tuple[str, str, int | None], list[dt.date]] = {}
            for row in rows:
                title = (row.get("EVENT_NM") or "").strip()
                ymd = (row.get("AA_YMD") or "").strip()
                if not title or not ymd:
                    continue
                # "토요휴업일"은 매주 토요일마다 들어와 달력을 덮는다. 학사일정이
                # 아니라 그냥 주말이므로 뺀다.
                if title in ("토요휴업일", "토요휴업"):
                    continue
                kind = classify(title, row.get("SBTR_DD_SC_NM") or "")
                bucket = (title[:120], kind, grade_of(row))
                buckets.setdefault(bucket, []).append(
                    dt.datetime.strptime(ymd, "%Y%m%d").date())

            # 받은 기간의 NEIS 행을 비우고 다시 넣는다. 사람이 고친 것은 남긴다.
            first = dt.datetime.strptime(args.date_from, "%Y%m%d").date()
            last = dt.datetime.strptime(args.date_to, "%Y%m%d").date()
            cur.execute("""
                DELETE FROM school_event
                 WHERE school_id = %s AND source = 'NEIS'
                   AND NOT is_manually_overridden
                   AND start_date <= %s AND end_date >= %s
            """, (school_id, last, first))
            removed = cur.rowcount

            saved = 0
            for (title, kind, grade), days in buckets.items():
                for start, end in merge_spans(days):
                    external = f"{start:%Y%m%d}-{end:%Y%m%d}-{grade or 'A'}-{title}"
                    cur.execute("""
                        INSERT INTO school_event
                               (school_id, title, event_type, start_date, end_date,
                                grade_scope, source, external_id, synced_at)
                        VALUES (%s, %s, %s, %s, %s, %s, 'NEIS', %s, now())
                        -- 부분 인덱스라 조건까지 적어야 짝이 맞는다.
                        -- 앞에서 지우고 넣으므로 부딪히는 경우는 제목이 길어
                        -- 80자에서 잘려 겹칠 때뿐이다.
                        ON CONFLICT (school_id, external_id)
                          WHERE external_id IS NOT NULL DO NOTHING
                    """, (school_id, title, kind, start, end, grade, external[:80]))
                    saved += cur.rowcount

            cur.execute("""
                SELECT event_type, count(*), min(start_date), max(end_date)
                  FROM school_event WHERE school_id = %s
                 GROUP BY event_type ORDER BY count(*) DESC
            """, (school_id,))
            print(f"\n적재 완료 — 옛 행 {removed}개 정리, {saved}건 저장")
            for kind, count, begins, ends in cur.fetchall():
                print(f"  {kind:<11} {count:>3}건   {begins} ~ {ends}")
        conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
