"""
NEIS 에서 급식표를 받아 적재한다. (W8)

왜 미리 받아두나:
    NEIS 인증키는 서버 쪽 비밀이라 브라우저가 직접 부를 수 없다.
    받아서 DB 에 넣어두고, 앱은 RLS 를 통해 자기 학교 것만 읽는다.

어느 학교 이름으로 저장하나:
    **실제 데이터를 제공한 학교**(서울고등학교) 아래 저장한다.
    테스트 조직은 school.info_school_id 로 그 학교를 가리키고 있고,
    RLS 가 그 연결을 따라가 자기 학교 급식으로 보여준다.
    조직 밑에 복사해두면 같은 급식이 조직 수만큼 늘어난다.

끼니:
    NEIS 는 조식/중식/석식을 따로 준다. 학교에 따라 중식만 있기도 하다.
    화면에서 고를 수 있게 받은 것을 그대로 넣는다.

사용법:
    python db/neis_meals.py --school "서울고등학교"
    python db/neis_meals.py --school "서울고등학교" --from 20260301 --to 20270228
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

import psycopg
from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
from neis_schools import call, env, find_school  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

MEAL_TYPES = {"조식": "BREAKFAST", "중식": "LUNCH", "석식": "DINNER"}

# "양송이스프 (2.5.6.13.16)" → 이름과 알레르기 코드로 나눈다.
DISH = re.compile(r"^(?P<name>.*?)\s*\((?P<allergy>[\d.\s]+)\)\s*$")


def parse_dishes(raw: str) -> list[tuple[str, str | None]]:
    """DDISH_NM 한 덩어리를 요리 단위로 쪼갠다.

    한 덩어리 텍스트로 저장하면 "인기 메뉴" 같은 것을 셀 수 없다.
    구 서비스가 그렇게 저장해 분석이 막혔던 것과 같은 실수를 반복하지 않는다.
    """
    dishes = []
    for chunk in raw.split("<br/>"):
        chunk = chunk.replace("<br>", "").strip()
        if not chunk:
            continue
        matched = DISH.match(chunk)
        if matched:
            name = matched.group("name").strip()
            allergy = matched.group("allergy").replace(" ", "")
        else:
            name, allergy = chunk, None
        if name:
            dishes.append((name[:80], (allergy or None) and allergy[:60]))
    return dishes


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

            rows = call("mealServiceDietInfo", key,
                        ATPT_OFCDC_SC_CODE=office_code, SD_SCHUL_CODE=school_code,
                        MLSV_FROM_YMD=args.date_from, MLSV_TO_YMD=args.date_to)
            print(f"{name} — {args.date_from}~{args.date_to} 급식 {len(rows)}건 받음")

            plans = 0
            for row in rows:
                meal_type = MEAL_TYPES.get((row.get("MMEAL_SC_NM") or "").strip())
                if meal_type is None:
                    continue

                serve_date = dt.datetime.strptime(row["MLSV_YMD"], "%Y%m%d").date()
                calorie = None
                if match := re.search(r"[\d.]+", row.get("CAL_INFO") or ""):
                    calorie = float(match.group())

                # 학교·날짜·끼니가 UNIQUE 라 다시 받아도 덮어쓰기만 된다.
                # 손으로 고친 행(is_manually_overridden)은 건드리지 않는다.
                cur.execute("""
                    INSERT INTO meal_plan (school_id, serve_date, meal_type, calorie_kcal,
                                           source, external_id, synced_at)
                    VALUES (%s, %s, %s, %s, 'NEIS', %s, now())
                    ON CONFLICT (school_id, serve_date, meal_type) DO UPDATE
                       SET calorie_kcal = EXCLUDED.calorie_kcal, synced_at = now()
                     WHERE NOT meal_plan.is_manually_overridden
                    RETURNING id
                """, (school_id, serve_date, meal_type, calorie,
                      f"{row['MLSV_YMD']}-{row.get('MMEAL_SC_CODE', '')}"))

                result = cur.fetchone()
                if result is None:          # 사람이 손댄 행이라 건너뛴다
                    continue
                plan_id = result[0]

                cur.execute("DELETE FROM meal_menu_item WHERE meal_plan_id = %s", (plan_id,))
                for order, (dish, allergy) in enumerate(parse_dishes(row.get("DDISH_NM") or "")):
                    cur.execute(
                        "INSERT INTO meal_menu_item (meal_plan_id, dish_name, allergy_codes, sort_order) "
                        "VALUES (%s, %s, %s, %s)", (plan_id, dish, allergy, order))
                plans += 1

            cur.execute("""
                SELECT meal_type, count(*), min(serve_date), max(serve_date)
                  FROM meal_plan WHERE school_id = %s GROUP BY meal_type ORDER BY meal_type
            """, (school_id,))
            print(f"\n적재 완료 — {plans}건 반영")
            for meal_type, count, first, last in cur.fetchall():
                print(f"  {meal_type:<10} {count:>4}일   {first} ~ {last}")
        conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
