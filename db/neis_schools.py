"""
NEIS 교육정보 개방포털에서 학교와 학급을 받아 온다. (P3)

왜 필요한가:
    지금 소속은 클로즈드 테스트용 임시 조직("코드잇 DA 14기") 하나뿐이다.
    실제 학교 목록이 들어와야 이용자가 자기 학교를 고를 수 있고,
    급식·시간표(W8)도 그 학교 기준으로 부를 수 있다.

두 가지를 따로 받는다:
    학교  전국 중·고등학교 목록. 한 번 받아두면 자주 바뀌지 않는다.
    학급  **고른 학교 것만** 받는다. 학교마다 API 를 한 번씩 불러야 해서
          5천 개 학교의 학급을 미리 받아두는 것은 현실적이지 않다.

초등학교는 받지 않는다. school_type 이 MIDDLE/HIGH 뿐이고,
서비스 대상도 중·고등학생이다.

사용법:
    python db/neis_schools.py --schools                 # 전국 중·고 목록 적재
    python db/neis_schools.py --classes "가락고등학교"    # 그 학교의 학급 적재
    python db/neis_schools.py --classes 7010057          # 표준학교코드로도 된다
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import psycopg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
API = "https://open.neis.go.kr/hub/"

# 호출 한 번에 최대 1,000건 (포털 공지)
PAGE_SIZE = 1000

# SCHUL_KND_SC_NM → school_type
SCHOOL_TYPES = {"중학교": "MIDDLE", "고등학교": "HIGH"}


def env(name: str) -> str:
    value = (dotenv_values(ROOT / ".env").get(name) or "").strip()
    if not value:
        sys.exit(f".env 의 {name} 이 비어 있습니다")
    return value


def call(endpoint: str, key: str, **params) -> list[dict]:
    """한 엔드포인트를 끝까지 훑어 row 를 모은다.

    NEIS 는 결과가 없을 때 {'RESULT': {...}} 만 돌려준다. 오류가 아니라
    '해당하는 데이터가 없다'는 뜻이므로 빈 목록으로 취급한다.
    """
    rows: list[dict] = []
    page = 1
    while True:
        query = {"KEY": key, "Type": "json", "pIndex": page, "pSize": PAGE_SIZE, **params}
        url = API + endpoint + "?" + urllib.parse.urlencode(query)
        with urllib.request.urlopen(url, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))

        if endpoint not in body:
            code = body.get("RESULT", {}).get("CODE", "")
            if code and code != "INFO-200":       # INFO-200 = 데이터 없음
                sys.exit(f"NEIS 오류: {body.get('RESULT')}")
            break

        rows += body[endpoint][1].get("row", [])
        total = body[endpoint][0]["head"][0]["list_total_count"]
        if len(rows) >= total:
            break
        page += 1
        time.sleep(0.2)                            # 연속 호출 간격을 둔다
    return rows


def region_of(row: dict) -> tuple[str, str]:
    """소재지에서 시도·시군구를 뽑는다.

    LCTN_SC_NM 이 시도, 도로명주소의 두 번째 토큰이 시군구다.
    세종처럼 시군구가 없는 곳은 읍/면이 들어오는데, 지역 구분 용도로는 충분하다.
    """
    sido = (row.get("LCTN_SC_NM") or "").strip()
    address = (row.get("ORG_RDNMA") or "").split()
    sigungu = address[1] if len(address) > 1 else "기타"
    return sido[:20], sigungu[:30]


def load_schools(cur, key: str) -> None:
    total = 0
    for kind, school_type in SCHOOL_TYPES.items():
        rows = call("schoolInfo", key, SCHUL_KND_SC_NM=kind)
        print(f"  {kind}: {len(rows)}개 받음")

        for row in rows:
            sido, sigungu = region_of(row)
            if not sido:
                continue

            cur.execute(
                "INSERT INTO region (sido, sigungu) VALUES (%s, %s) "
                "ON CONFLICT (sido, sigungu) DO UPDATE SET sido = EXCLUDED.sido "
                "RETURNING id", (sido, sigungu))
            region_id = cur.fetchone()[0]

            # 표준학교코드가 UNIQUE 라 다시 받아도 덮어쓰기만 된다.
            cur.execute("""
                INSERT INTO school (name_masked, region_id, school_type,
                                    neis_school_code, neis_office_code)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (neis_school_code) DO UPDATE
                   SET name_masked = EXCLUDED.name_masked,
                       region_id = EXCLUDED.region_id,
                       school_type = EXCLUDED.school_type,
                       neis_office_code = EXCLUDED.neis_office_code,
                       updated_at = now()
            """, (row["SCHUL_NM"][:50], region_id, school_type,
                  row["SD_SCHUL_CODE"], row["ATPT_OFCDC_SC_CODE"]))
            total += 1

    cur.execute("SELECT count(*) FROM school WHERE neis_school_code IS NOT NULL")
    print(f"\n적재 완료 — NEIS 학교 {cur.fetchone()[0]}개")


def load_classes(cur, key: str, needle: str) -> None:
    cur.execute("""
        SELECT id, name_masked, neis_school_code, neis_office_code
          FROM school
         WHERE neis_school_code = %s OR name_masked = %s
         ORDER BY id LIMIT 2
    """, (needle, needle))
    found = cur.fetchall()

    if not found:
        cur.execute("SELECT id, name_masked, neis_school_code, neis_office_code "
                    "FROM school WHERE name_masked LIKE %s ORDER BY id LIMIT 6",
                    (f"%{needle}%",))
        found = cur.fetchall()

    if not found:
        sys.exit(f"'{needle}' 에 해당하는 학교가 없습니다. 먼저 --schools 를 실행하세요.")
    if len(found) > 1:
        print("여러 학교가 걸립니다. 정확한 이름이나 표준학교코드로 다시 지정하세요:")
        for _, name, code, _ in found:
            print(f"  {name}  ({code})")
        sys.exit(1)

    school_id, name, school_code, office_code = found[0]
    if not office_code:
        sys.exit(f"{name} 에 교육청코드가 없습니다. --schools 를 다시 실행하세요.")

    rows = call("classInfo", key,
                ATPT_OFCDC_SC_CODE=office_code, SD_SCHUL_CODE=school_code)
    if not rows:
        sys.exit(f"{name} 의 학급 정보가 없습니다. (분교·특수학교일 수 있습니다)")

    made = 0
    for row in rows:
        grade = int(row["GRADE"])
        raw = (row.get("CLASS_NM") or "").strip()
        # 반 이름이 숫자가 아닌 학교가 있다("가", "국제"). 그때는 label 로 보여준다.
        if raw.isdigit():
            class_num, label = int(raw), None
        else:
            class_num, label = 900 + made, f"{grade}학년 {raw}반"

        cur.execute("""
            INSERT INTO grade_class (school_id, grade, class_num, label)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (school_id, grade, class_num) DO UPDATE
               SET label = EXCLUDED.label
        """, (school_id, grade, class_num, label))
        made += 1

    cur.execute("SELECT count(*) FROM grade_class WHERE school_id = %s", (school_id,))
    print(f"{name} — 학급 {cur.fetchone()[0]}개 적재 (받은 행 {made})")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--schools", action="store_true", help="전국 중·고 목록 적재")
    ap.add_argument("--classes", metavar="학교명|학교코드", help="그 학교의 학급 적재")
    args = ap.parse_args()

    if not args.schools and not args.classes:
        ap.error("--schools 또는 --classes 중 하나가 필요합니다")

    key = env("NEIS_API_KEY")
    with psycopg.connect(env("SUPABASE_DB_URL"), connect_timeout=30) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            if args.schools:
                load_schools(cur, key)
            if args.classes:
                load_classes(cur, key, args.classes)
        conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
