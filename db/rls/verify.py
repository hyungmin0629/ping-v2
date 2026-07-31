"""
RLS 침투 시험

정책이 "선언되어 있는 것"과 "실제로 막는 것"은 다르다.
그래서 시험용 계정 둘을 만들고, 유저 A 의 권한으로
유저 B 의 데이터를 실제로 훔쳐보려 시도한다.

Supabase 가 요청을 처리할 때와 같은 방식으로 흉내낸다:
    SET LOCAL ROLE authenticated;
    SET LOCAL request.jwt.claims = '{"sub": "<유저의 auth uuid>", ...}';

하나라도 뚫리면 종료 코드 1 을 돌려준다.
설계서상 이 시험을 통과하지 못하면 다음 단계로 넘어가지 않는다.

사용법:
    python db/rls/verify.py
    python db/rls/verify.py --keep    # 시험 데이터를 지우지 않는다(디버깅용)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

import psycopg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent.parent

A_AUTH = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001")
B_AUTH = uuid.UUID("bbbbbbbb-0000-4000-8000-000000000002")
# C 는 아직 온보딩하지 않은 계정이다. 가입 경로 자체를 시험하려면
# app_user 행이 없는 익명 계정이 하나 필요하다.
C_AUTH = uuid.UUID("cccccccc-0000-4000-8000-000000000003")

# D1~D4 는 5명 게이트를 시험하기 위한 친구들이다.
# A 가 B 까지 5명을 채우는 순간 service_unlocked_at 이 찍혀야 한다.
D_USERS = [
    (uuid.UUID(f"dddddddd-0000-4000-8000-00000000000{n}"), f"시험친구D{n}", code)
    for n, code in enumerate(["TESTDA", "TESTDB", "TESTDC", "TESTDD"], start=4)
]

FRIEND_GATE = 5   # friends.sql 의 refresh_friend_state 와 같은 값

INVITE_CODE_RE = re.compile(r"^[A-HJ-NP-Z2-9]{6,8}$")   # DDL 의 ck_invite_code 와 같다
SIGNUP_GRANT = 300                                       # onboarding.sql 이 지급하는 양


def check_unqualified_dml() -> list[str]:
    """WHERE 없는 DELETE/UPDATE 를 소스에서 찾는다.

    왜 소스 검사인가 — **이 시험으로는 런타임에 잡을 수 없기 때문이다.**

    브라우저는 PostgREST 를 거쳐 `authenticator` 역할로 접속하고, 그 역할에는
    `session_preload_libraries = supautils, safeupdate` 가 걸려 있다.
    safeupdate 는 WHERE 없는 DELETE/UPDATE 를 임시 테이블에서도 막는다.

    그런데 이 시험은 postgres 로 붙어 `SET LOCAL ROLE authenticated` 만 한다.
    preload 는 **세션이 열릴 때** 적용되므로 역할만 바꿔서는 안 걸린다.
    그래서 시험 128항목이 전부 통과해도 실제 앱은 죽을 수 있다 —
    2026-07-30 에 `start_vote_session` 의 `DELETE FROM picked_now` 로 실제로 그랬다.
    (postgres 는 `LOAD 'safeupdate'` 권한도 없어서 흉내낼 수도 없다)

    줄 첫머리에 오는 것만 본다. REVOKE ... UPDATE, FOR UPDATE, DO UPDATE 는
    문장이 아니라 절이므로 걸리면 안 된다.
    """
    bad = []
    for path in sorted((ROOT / "db" / "rls").glob("*.sql")):
        text = "\n".join(re.sub(r"--.*$", "", ln) for ln in
                         path.read_text(encoding="utf-8").splitlines())
        for m in re.finditer(r"^[ \t]*(?:DELETE\s+FROM|UPDATE)\s+[\w.\"]+.*?;",
                             text, re.S | re.I | re.M):
            if not re.search(r"\bWHERE\b", m.group(0), re.I):
                line = text[: m.start()].count("\n") + 1
                bad.append(f"{path.name}:{line}  {' '.join(m.group(0).split())[:70]}")
    return bad


def as_user(cur, auth_uuid: uuid.UUID | None):
    """이 세션을 해당 유저(또는 비로그인)로 가장한다."""
    if auth_uuid is None:
        cur.execute("SET LOCAL ROLE anon")
        cur.execute("SELECT set_config('request.jwt.claims', %s, true)",
                    (json.dumps({"role": "anon"}),))
    else:
        cur.execute("SET LOCAL ROLE authenticated")
        cur.execute("SELECT set_config('request.jwt.claims', %s, true)",
                    (json.dumps({"sub": str(auth_uuid), "role": "authenticated"}), ))


def rpc(cur, who: uuid.UUID, sql: str, params: tuple = ()):
    """해당 유저를 가장해 한 줄짜리 조회를 실행하고 첫 값을 돌려준다."""
    as_user(cur, who)
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.execute("SET LOCAL ROLE postgres")
    return row[0] if row else None


def expect_error(cur, who: uuid.UUID, sql: str, params: tuple = ()) -> bool:
    """실패해야 하는 호출. 막혔으면 True. 시도 자체는 되돌린다."""
    cur.execute("SAVEPOINT probe")
    try:
        rpc(cur, who, sql, params)
        return False
    except Exception:
        return True
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT probe")
        cur.execute("SET LOCAL ROLE postgres")


def setup(cur):
    cur.execute("SET LOCAL ROLE postgres")
    cur.execute("INSERT INTO auth.users (id) VALUES (%s), (%s), (%s) ON CONFLICT DO NOTHING",
                (A_AUTH, B_AUTH, C_AUTH))
    for auth_id, _, _ in D_USERS:
        cur.execute("INSERT INTO auth.users (id) VALUES (%s) ON CONFLICT DO NOTHING", (auth_id,))

    cur.execute("INSERT INTO region (sido, sigungu) VALUES ('시험','구') RETURNING id")
    rid = cur.fetchone()[0]
    cur.execute("INSERT INTO school (name_masked, region_id, school_type) "
                "VALUES ('시*학교', %s, 'HIGH') RETURNING id", (rid,))
    sid = cur.fetchone()[0]
    cur.execute("INSERT INTO grade_class (school_id, grade, class_num) "
                "VALUES (%s, 1, 1) RETURNING id", (sid,))
    cid = cur.fetchone()[0]

    ids = {}
    for label, auth_id, nick, code, gender in [("A", A_AUTH, "시험유저A", "TESTAA", "F"),
                                               ("B", B_AUTH, "시험유저B", "TESTBB", "M")]:
        cur.execute(
            "INSERT INTO app_user (auth_user_id, nickname, invite_code, class_id, gender, "
            "heart_balance) VALUES (%s, %s, %s, %s, %s, 5000) RETURNING id",
            (auth_id, nick, code, cid, gender))
        ids[label] = cur.fetchone()[0]

    for n, (auth_id, nick, code) in enumerate(D_USERS, start=1):
        cur.execute(
            "INSERT INTO app_user (auth_user_id, nickname, invite_code, class_id, gender) "
            "VALUES (%s, %s, %s, %s, 'X') RETURNING id", (auth_id, nick, code, cid))
        ids[f"D{n}"] = cur.fetchone()[0]

    # B 의 민감 데이터를 만들어 둔다 — A 가 이걸 훔쳐보려 시도할 것이다
    cur.execute("INSERT INTO heart_transaction (user_id, type_code, delta, balance_after) "
                "VALUES (%s, 'SIGNUP_GRANT', 300, 300)", (ids["B"],))
    cur.execute("INSERT INTO question (text, scope, category_id, status) "
                "SELECT '시험 질문', 'GLOBAL', id, 'ACTIVE' FROM question_category LIMIT 1 RETURNING id")
    qid = cur.fetchone()[0]
    cur.execute("INSERT INTO vote_session (user_id, item_count) VALUES (%s, 1) RETURNING id", (ids["A"],))
    sess = cur.fetchone()[0]
    cur.execute("INSERT INTO vote_item (session_id, user_id, question_id, candidate_scope, position, voted_at) "
                "VALUES (%s, %s, %s, 'GLOBAL', 1, now()) RETURNING id", (sess, ids["A"], qid))
    item = cur.fetchone()[0]
    # A 가 B 를 뽑았다 → B 입장에서 "누가 나를 뽑았나"가 유료 비밀이다
    cur.execute("INSERT INTO vote_received (vote_item_id, voter_id, receiver_id, question_id) "
                "VALUES (%s, %s, %s, %s) RETURNING id", (item, ids["A"], ids["B"], qid))
    recv = cur.fetchone()[0]
    return ids, {"question": qid, "item": item, "received": recv, "class": cid}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    url = dotenv_values(ROOT / ".env")["SUPABASE_DB_URL"].strip()
    failures = []

    # 접속하기 전에 소스부터 본다. 이건 DB 에 물어봐도 알 수 없는 종류다.
    print("=" * 62)
    print("소스 검사 — WHERE 없는 DELETE/UPDATE")
    print("=" * 62)
    unqualified = check_unqualified_dml()
    if unqualified:
        for b in unqualified:
            print(f"  걸림!! {b}")
            failures.append(f"[safeupdate] {b}")
        print("\n  Supabase 의 authenticator 역할에는 safeupdate 가 걸려 있다.")
        print("  WHERE 를 붙여라 — 임시 테이블이라도 막힌다. `WHERE true` 면 충분하다.")
    else:
        print("  깨끗함  db/rls/*.sql 에 WHERE 없는 DELETE/UPDATE 가 없음")
    print()

    with psycopg.connect(url, connect_timeout=30, autocommit=False) as conn:
        with conn.cursor() as cur:
            ids, ctx = setup(cur)
            A, B = ids["A"], ids["B"]

            # (설명, 가장할 유저, 쿼리, 인자, 기대 행수)
            tests = [
                ("A 가 B 의 계정 정보를 조회",
                 A_AUTH, "SELECT 1 FROM app_user WHERE id=%s", (B,), 0),
                ("A 가 B 의 하트 잔액을 조회",
                 A_AUTH, "SELECT 1 FROM app_user WHERE heart_balance > 0 AND id<>%s", (A,), 0),
                ("A 가 B 의 하트 거래내역을 조회",
                 A_AUTH, "SELECT 1 FROM heart_transaction WHERE user_id=%s", (B,), 0),
                ("A 가 전체 유저 목록을 훑기",
                 A_AUTH, "SELECT 1 FROM app_user", (), 1),          # 자기 행 1개만 보여야 정상
                ("B 가 vote_received 를 직접 조회 (voter_id 유출 시도)",
                 B_AUTH, "SELECT 1 FROM vote_received", (), 0),
                ("B 가 미공개 상태에서 투표자를 알아내기",
                 B_AUTH, "SELECT 1 FROM my_vote_received WHERE voter_id IS NOT NULL", (), 0),
                ("A 가 B 의 투표 기록을 조회",
                 B_AUTH, "SELECT 1 FROM vote_item WHERE user_id=%s", (A,), 0),
                ("A 가 남의 운영자 여부를 조회",
                 A_AUTH, "SELECT 1 FROM app_user WHERE is_admin", (), 0),
                ("A 가 자동제재 임계값을 조회",
                 A_AUTH, "SELECT 1 FROM sanction_policy", (), 0),
                ("비로그인 상태로 유저 목록 조회",
                 None, "SELECT 1 FROM app_user", (), 0),
                ("비로그인 상태로 학교 목록 조회",
                 None, "SELECT 1 FROM school", (), 0),
            ]

            print("=" * 62)
            print("RLS 침투 시험")
            print("=" * 62)

            for desc, who, sql, params, expect in tests:
                cur.execute("SAVEPOINT sp")
                try:
                    as_user(cur, who)
                    cur.execute(sql, params)
                    got = len(cur.fetchall())
                    ok = got == expect
                except psycopg.errors.InsufficientPrivilege:
                    got, ok = "권한거부", True
                except Exception as e:
                    got, ok = f"{type(e).__name__}", True
                finally:
                    cur.execute("ROLLBACK TO SAVEPOINT sp")
                    cur.execute("SET LOCAL ROLE postgres")

                mark = "막힘  " if ok else "뚫림!!"
                print(f"  {mark} {desc}")
                if not ok:
                    print(f"         기대 {expect}행 / 실제 {got}행")
                    failures.append(desc)

            # 쓰기 시도 — 하트를 스스로 늘릴 수 있는가
            print()
            write_tests = [
                ("A 가 자기 하트 잔액을 직접 수정",
                 A_AUTH, "UPDATE app_user SET heart_balance = 999999 WHERE id=%s", (A,)),
                ("A 가 하트 거래를 직접 생성",
                 A_AUTH, "INSERT INTO heart_transaction (user_id,type_code,delta,balance_after) "
                         "VALUES (%s,'ADMIN_ADJUST',999999,999999)", (A,)),
                ("A 가 B 의 닉네임을 변경",
                 A_AUTH, "UPDATE app_user SET nickname='해킹됨' WHERE id=%s", (B,)),
                # ★ 운영자 표시를 스스로 켤 수 있으면 안 된다. admin_user 를
                #   없애고 app_user 로 접으면서 생긴 위험이다(migration 009) —
                #   운영자 여부가 이제 **유저가 UPDATE 하는 표**에 산다.
                ("A 가 스스로 운영자가 되기",
                 A_AUTH, "UPDATE app_user SET is_admin=true WHERE id=%s", (A,)),
                ("A 가 남의 명의로 친구요청 생성",
                 A_AUTH, "INSERT INTO friend_request (sender_id,receiver_id,source) "
                         "VALUES (%s,%s,'INVITE_CODE')", (B, A)),
                # 코드를 몰라도 id 만 바꿔가며 아무에게나 요청을 뿌릴 수 있으면 안 된다
                ("A 가 코드 없이 id 로 친구요청 생성",
                 A_AUTH, "INSERT INTO friend_request (sender_id,receiver_id,source) "
                         "VALUES (%s,%s,'INVITE_CODE')", (A, B)),
                ("A 가 요청 상태를 직접 수락으로 변경",
                 A_AUTH, "UPDATE friend_request SET status='ACCEPTED' WHERE receiver_id=%s", (A,)),
                ("A 가 친구 관계를 직접 생성",
                 A_AUTH, "INSERT INTO friendship (user_low_id,user_high_id,source) "
                         "VALUES (%s,%s,'INVITE_CODE')", (min(A, B), max(A, B))),
                # 후보를 직접 만들 수 있으면 아무나 지목할 수 있다
                ("A 가 투표 후보를 직접 생성",
                 A_AUTH, "INSERT INTO vote_candidate (vote_item_id,candidate_user_id,slot) "
                         "VALUES (%s,%s,1)", (ctx["item"], B)),
                ("A 가 지목 기록을 직접 생성",
                 A_AUTH, "INSERT INTO vote_received (vote_item_id,voter_id,receiver_id,question_id) "
                         "VALUES (%s,%s,%s,%s)",
                 (ctx["item"], A, B, ctx["question"])),
                ("A 가 셔플 횟수를 직접 되돌림",
                 A_AUTH, "UPDATE vote_item SET shuffle_count=0 WHERE user_id=%s", (A,)),
                # 접속 시각을 조작할 수 있으면 리텐션 지표가 통째로 오염된다
                ("A 가 접속 기록을 직접 생성(과거 시각으로)",
                 A_AUTH, "INSERT INTO user_session (user_id,platform,app_version,started_at) "
                         "VALUES (%s,'WEB','1.0','2020-01-01')", (A,)),
                # 힌트를 공짜로 만들 수 있으면 수익 구조가 통째로 무너진다
                ("B 가 힌트 구매 기록을 직접 생성",
                 B_AUTH, "INSERT INTO hint_purchase "
                         "(vote_received_id,user_id,hint_type,step,heart_cost) "
                         "VALUES (%s,%s,'FULL_NAME',1,0)", (ctx["received"], B)),
                ("B 가 공개 상태를 직접 REVEALED 로 변경",
                 B_AUTH, "UPDATE vote_received SET reveal_status='REVEALED' WHERE id=%s",
                 (ctx["received"],)),
            ]
            for desc, who, sql, params in write_tests:
                cur.execute("SAVEPOINT sp")
                blocked, detail = False, ""
                try:
                    as_user(cur, who)
                    cur.execute(sql, params)
                    blocked = cur.rowcount == 0
                    detail = f"{cur.rowcount}행 변경됨"
                except Exception as e:
                    blocked, detail = True, type(e).__name__
                finally:
                    cur.execute("ROLLBACK TO SAVEPOINT sp")
                    cur.execute("SET LOCAL ROLE postgres")

                print(f"  {'막힘  ' if blocked else '뚫림!!'} {desc}  ({detail})")
                if not blocked:
                    failures.append(desc)

            # ---------------------------------------------------------
            # 온보딩 — 가입 경로가 정말 RPC 하나뿐인가 (W3)
            #
            # 가입은 유일하게 "없던 행을 만드는" 동작이라 따로 시험한다.
            # 여기가 열려 있으면 하트를 얹은 계정을 스스로 만들 수 있다.
            # ---------------------------------------------------------
            print()
            print("온보딩 시험 (W3)")

            cid = ctx["class"]

            # 1) 직접 INSERT — 하트까지 얹어서 시도해 본다
            cur.execute("SAVEPOINT sp")
            blocked, detail = False, ""
            try:
                as_user(cur, C_AUTH)
                cur.execute(
                    "INSERT INTO app_user (auth_user_id,nickname,invite_code,class_id,"
                    "heart_balance,is_synthetic) "
                    "VALUES (%s,'몰래가입','ZZZZZZ',%s,999999,true)", (C_AUTH, cid))
                blocked, detail = cur.rowcount == 0, f"{cur.rowcount}행 생성됨"
            except Exception as e:
                blocked, detail = True, type(e).__name__
            finally:
                cur.execute("ROLLBACK TO SAVEPOINT sp")
                cur.execute("SET LOCAL ROLE postgres")

            print(f"  {'막힘  ' if blocked else '뚫림!!'} 직접 INSERT 로 가입 시도  ({detail})")
            if not blocked:
                failures.append("[온보딩] 직접 INSERT 로 계정이 만들어짐")

            # 2~4) RPC 로는 제대로 가입되는가
            cur.execute("SAVEPOINT onboarding")
            try:
                as_user(cur, C_AUTH)
                cur.execute("SELECT id, nickname, invite_code, heart_balance, is_synthetic "
                            "FROM complete_onboarding('새로온사람', %s, 'F')", (cid,))
                new_id, nick, code, bal, synth = cur.fetchone()
                cur.execute("SET LOCAL ROLE postgres")

                ok = (nick == "새로온사람"
                      and bool(INVITE_CODE_RE.match(code or ""))
                      and bal == SIGNUP_GRANT
                      and synth is False)
                print(f"  {'동작함' if ok else '실패!!'} RPC 로 가입  "
                      f"(코드={code}, 하트={bal}, 합성데이터={synth})")
                if not ok:
                    failures.append("[온보딩] 가입 결과가 기대와 다름")

                # 새로고침이나 중복 클릭으로 두 번 불려도 계정이 갈라지면 안 된다
                as_user(cur, C_AUTH)
                cur.execute("SELECT id FROM complete_onboarding('다른이름', %s, 'M')", (cid,))
                again_id = cur.fetchone()[0]
                cur.execute("SET LOCAL ROLE postgres")
                cur.execute("SELECT count(*) FROM app_user WHERE auth_user_id=%s", (C_AUTH,))
                cnt = cur.fetchone()[0]

                ok = again_id == new_id and cnt == 1
                print(f"  {'동작함' if ok else '실패!!'} 재호출해도 계정은 하나  "
                      f"(id={again_id}, 행수={cnt})")
                if not ok:
                    failures.append("[온보딩] 재호출로 계정이 갈라짐")

                # 잔액과 원장의 일치 — 구 시스템 최대 결함이 이 자리였다
                cur.execute(
                    "SELECT u.heart_balance, coalesce(sum(t.delta),0) "
                    "FROM app_user u LEFT JOIN heart_transaction t ON t.user_id = u.id "
                    "WHERE u.id = %s GROUP BY u.heart_balance", (new_id,))
                bal, ledger = cur.fetchone()

                ok = bal == ledger == SIGNUP_GRANT
                print(f"  {'동작함' if ok else '실패!!'} 가입 하트의 잔액=원장  "
                      f"(잔액={bal}, 원장={ledger})")
                if not ok:
                    failures.append("[온보딩] 하트 잔액과 원장이 어긋남")
            except Exception as e:
                print(f"  실패!! 온보딩 RPC 호출  ({type(e).__name__}: {e})")
                failures.append("[온보딩] complete_onboarding 호출 실패")
            finally:
                cur.execute("ROLLBACK TO SAVEPOINT onboarding")
                cur.execute("SET LOCAL ROLE postgres")

            # ---------------------------------------------------------
            # 친구 맺기 — 초대 코드 말고는 상대를 지목할 수 없는가 (W4)
            # ---------------------------------------------------------
            print()
            print("친구 시험 (W4)")

            def check(desc: str, ok: bool, detail=""):
                print(f"  {'동작함' if ok else '실패!!'} {desc}  ({detail})")
                if not ok:
                    failures.append(f"[친구] {desc}")

            cur.execute("SAVEPOINT friends")
            try:
                check("A 가 B 의 코드로 요청",
                      rpc(cur, A_AUTH, "SELECT send_friend_request('TESTBB')") == "SENT", "SENT")
                check("같은 요청을 또 보냄",
                      rpc(cur, A_AUTH, "SELECT send_friend_request('TESTBB')") == "ALREADY_SENT",
                      "ALREADY_SENT 기대")
                check("내 코드를 입력",
                      rpc(cur, A_AUTH, "SELECT send_friend_request('TESTAA')") == "SELF",
                      "SELF 기대")
                check("없는 코드를 입력",
                      rpc(cur, A_AUTH, "SELECT send_friend_request('ZZZZZZ')") == "NOT_FOUND",
                      "NOT_FOUND 기대")

                # 아직 친구가 아닌 상대의 닉네임이 요청 목록에는 보여야 한다
                as_user(cur, B_AUTH)
                cur.execute("SELECT id, direction, counterpart_nickname "
                            "FROM my_friend_request WHERE status='PENDING'")
                rows = cur.fetchall()
                cur.execute("SET LOCAL ROLE postgres")
                ok = (len(rows) == 1 and rows[0][1] == "INCOMING"
                      and rows[0][2] == "시험유저A")
                check("B 가 받은 요청에서 A 를 봄", ok, rows)
                req_id = rows[0][0] if rows else None

                # 남이 받은 요청을 제3자가 대신 수락할 수 없다
                check("제3자가 남의 요청을 수락 시도",
                      rpc(cur, D_USERS[0][0],
                          "SELECT accept_friend_request(%s)", (req_id,)) == "NOT_FOUND",
                      "NOT_FOUND 기대")

                check("B 가 수락",
                      rpc(cur, B_AUTH,
                          "SELECT accept_friend_request(%s)", (req_id,)) == "ACCEPTED",
                      "ACCEPTED 기대")

                cur.execute("SELECT friend_count, service_unlocked_at FROM app_user WHERE id=%s",
                            (A,))
                cnt, unlocked = cur.fetchone()
                check("친구 1명 · 투표는 아직 잠김", cnt == 1 and unlocked is None,
                      f"{cnt}명, 해금={unlocked is not None}")

                # 5명을 채운다. 게이트는 수락 시점에 열려야 한다.
                for n, (d_auth, _, d_code) in enumerate(D_USERS, start=1):
                    sent = rpc(cur, A_AUTH, "SELECT send_friend_request(%s)", (d_code,))
                    rid = rpc(cur, d_auth, "SELECT id FROM my_friend_request "
                                           "WHERE status='PENDING' AND direction='INCOMING'")
                    acc = rpc(cur, d_auth, "SELECT accept_friend_request(%s)", (rid,))
                    if sent != "SENT" or acc != "ACCEPTED":
                        failures.append(f"[친구] D{n} 와의 요청·수락 실패 ({sent}/{acc})")

                cur.execute("SELECT friend_count, service_unlocked_at FROM app_user WHERE id=%s",
                            (A,))
                cnt, unlocked = cur.fetchone()
                check(f"{FRIEND_GATE}명째에 투표가 열림",
                      cnt == FRIEND_GATE and unlocked is not None,
                      f"{cnt}명, 해금={unlocked is not None}")

                check("이미 친구인 코드를 다시 입력",
                      rpc(cur, A_AUTH, "SELECT send_friend_request('TESTBB')") == "ALREADY_FRIEND",
                      "ALREADY_FRIEND 기대")

                check("친구 목록에 5명 + 나",
                      rpc(cur, A_AUTH, "SELECT count(*) FROM friend_profile") == FRIEND_GATE + 1,
                      f"{FRIEND_GATE + 1}행 기대")

                # 서로 코드를 주고받으면 수락을 기다리지 않고 맺어진다
                b_sent = rpc(cur, B_AUTH, "SELECT send_friend_request(%s)", (D_USERS[1][2],))
                auto = rpc(cur, D_USERS[1][0], "SELECT send_friend_request('TESTBB')")
                check("서로 코드를 입력하면 바로 친구",
                      b_sent == "SENT" and auto == "ACCEPTED", f"{b_sent} → {auto}")

                # 거절하면 관계가 만들어지지 않는다
                rpc(cur, B_AUTH, "SELECT send_friend_request(%s)", (D_USERS[2][2],))
                rid = rpc(cur, D_USERS[2][0], "SELECT id FROM my_friend_request "
                                              "WHERE status='PENDING' AND direction='INCOMING'")
                rejected = rpc(cur, D_USERS[2][0], "SELECT reject_friend_request(%s)", (rid,))
                cur.execute("SELECT public.is_friend(%s, %s)", (B, ids["D3"]))
                check("거절하면 친구가 되지 않음",
                      rejected == "REJECTED" and cur.fetchone()[0] is False, rejected)
            except Exception as e:
                print(f"  실패!! 친구 RPC 호출  ({type(e).__name__}: {e})")
                failures.append("[친구] RPC 호출 실패")
            finally:
                cur.execute("ROLLBACK TO SAVEPOINT friends")
                cur.execute("SET LOCAL ROLE postgres")

            # ---------------------------------------------------------
            # 투표 — 후보 규칙과 하트가 맞는가 (W5)
            # ---------------------------------------------------------
            print()
            print("투표 시험 (W5)")

            def vcheck(desc: str, ok: bool, detail=""):
                print(f"  {'동작함' if ok else '실패!!'} {desc}  ({detail})")
                if not ok:
                    failures.append(f"[투표] {desc}")

            cur.execute("SAVEPOINT voting")
            try:
                friends = [B, ids["D1"], ids["D2"], ids["D3"], ids["D4"]]

                # setup 이 만들어 둔 세션은 후보가 없는 더미다(RLS 시험용).
                # 닫아두지 않으면 start_vote_session 이 "진행 중인 세션"으로
                # 그걸 이어받아 버린다 — 함수가 아니라 시험 데이터의 문제다.
                cur.execute("UPDATE vote_session SET status='COMPLETED', completed_at=now() "
                            "WHERE user_id=%s AND status='IN_PROGRESS'", (A,))

                # 게이트 — 친구가 없으면 투표 자체가 열리지 않는다
                vcheck("친구 5명 미만이면 투표가 잠김",
                       expect_error(cur, A_AUTH, "SELECT start_vote_session()"),
                       "예외 기대")

                # 친구 5명을 붙인다 (맺는 절차 자체는 W4 에서 확인했다)
                for fid in friends:
                    cur.execute("INSERT INTO friendship (user_low_id,user_high_id,source) "
                                "VALUES (LEAST(%s,%s),GREATEST(%s,%s),'INVITE_CODE') "
                                "ON CONFLICT DO NOTHING", (A, fid, A, fid))
                    cur.execute("SELECT refresh_friend_state(%s)", (fid,))
                cur.execute("SELECT refresh_friend_state(%s)", (A,))

                session = rpc(cur, A_AUTH, "SELECT start_vote_session()")
                cur.execute("SELECT item_count FROM vote_session WHERE id=%s", (session,))
                items = cur.fetchone()[0]
                vcheck("세션이 열리고 문항이 만들어짐", items > 0, f"{items}문항")

                cur.execute("""
                    SELECT count(*) FROM vote_item v
                     WHERE v.session_id = %s
                       AND (SELECT count(*) FROM vote_candidate c
                             WHERE c.vote_item_id = v.id AND c.shuffle_round = 0) <> 4
                """, (session,))
                vcheck("모든 문항의 후보가 정확히 4명",
                       cur.fetchone()[0] == 0, f"{items}문항 검사")

                cur.execute("""
                    SELECT count(*) FROM vote_candidate c
                      JOIN vote_item v ON v.id = c.vote_item_id
                     WHERE v.session_id = %s
                       AND (c.candidate_user_id = %s
                            OR NOT public.is_friend(%s, c.candidate_user_id))
                """, (session, A, A))
                strangers = cur.fetchone()[0]
                vcheck("후보는 전부 내 친구이고 나 자신은 없음",
                       strangers == 0, f"규칙 위반 {strangers}명")

                vcheck("다시 열면 진행 중인 세션을 이어받음",
                       rpc(cur, A_AUTH, "SELECT start_vote_session()") == session,
                       f"세션 {session}")

                # --- 투표 제출 -------------------------------------------
                cur.execute("SELECT id FROM vote_item WHERE session_id=%s "
                            "ORDER BY position LIMIT 1", (session,))
                item = cur.fetchone()[0]
                cur.execute("SELECT candidate_user_id FROM vote_candidate "
                            "WHERE vote_item_id=%s AND shuffle_round=0 LIMIT 1", (item,))
                pick = cur.fetchone()[0]

                cur.execute("SELECT id FROM app_user WHERE id <> %s AND id NOT IN "
                            "(SELECT candidate_user_id FROM vote_candidate WHERE vote_item_id=%s) "
                            "LIMIT 1", (A, item))
                outsider = cur.fetchone()
                if outsider:
                    vcheck("후보에 없는 사람은 지목할 수 없음",
                           expect_error(cur, A_AUTH, "SELECT submit_vote(%s,%s)",
                                        (item, outsider[0])), "예외 기대")

                cur.execute("SELECT heart_balance FROM app_user WHERE id IN (%s,%s) ORDER BY id",
                            (A, pick))
                before = [r[0] for r in cur.fetchall()]

                reward = rpc(cur, A_AUTH, "SELECT submit_vote(%s,%s)", (item, pick))
                cur.execute("SELECT heart_balance FROM app_user WHERE id IN (%s,%s) ORDER BY id",
                            (A, pick))
                after = [r[0] for r in cur.fetchall()]

                vcheck("투표하면 하트가 적립됨 (5~15)",
                       5 <= reward <= 15, f"+{reward}")
                vcheck("투표자와 지목당한 사람 양쪽에 지급",
                       all(a > b for a, b in zip(after, before)),
                       f"{before} → {after}")

                # 잔액을 바꾼 자리에서 원장도 썼는가
                cur.execute("""
                    SELECT count(*) FROM heart_transaction t
                      JOIN app_user u ON u.id = t.user_id
                     WHERE t.vote_item_id = %s AND t.balance_after <> u.heart_balance
                """, (item,))
                vcheck("원장의 balance_after 가 실제 잔액과 일치",
                       cur.fetchone()[0] == 0, "2건 검사")

                cur.execute("SELECT voter_id, receiver_id FROM vote_received WHERE vote_item_id=%s",
                            (item,))
                got = cur.fetchone()
                vcheck("지목 기록이 남음", got == (A, pick), str(got))

                vcheck("같은 문항에 다시 투표할 수 없음",
                       expect_error(cur, A_AUTH, "SELECT submit_vote(%s,%s)", (item, pick)),
                       "예외 기대")

                # 내가 한 투표는 내 기록이므로 그대로 보인다
                as_user(cur, A_AUTH)
                cur.execute("SELECT chosen_user_id, question_text FROM my_vote_history "
                            "WHERE vote_item_id=%s", (item,))
                hist = cur.fetchone()
                cur.execute("SET LOCAL ROLE postgres")
                vcheck("내가 한 투표가 목록에 남음",
                       hist is not None and hist[0] == pick, str(hist and hist[0]))

                # 남이 한 투표는 보이지 않는다
                cur.execute("SELECT count(*) FROM vote_item WHERE user_id=%s", (A,))
                mine = cur.fetchone()[0]
                vcheck("남의 투표 기록은 내 목록에 없음",
                       rpc(cur, B_AUTH, "SELECT count(*) FROM my_vote_history") == 0,
                       f"A 의 기록 {mine}건은 B 에게 0건")

                # --- 셔플 -------------------------------------------------
                cur.execute("SELECT id FROM vote_item WHERE session_id=%s AND voted_at IS NULL "
                            "ORDER BY position LIMIT 1", (session,))
                item2 = cur.fetchone()[0]
                rpc(cur, A_AUTH, "SELECT shuffle_candidates(%s)", (item2,))

                cur.execute("SELECT count(*) FROM vote_candidate "
                            "WHERE vote_item_id=%s AND shuffle_round=1", (item2,))
                vcheck("셔플하면 새 후보 4명이 뽑힘", cur.fetchone()[0] == 4)

                cur.execute("SELECT count(*) FROM vote_shuffle s "
                            "JOIN ad_impression a ON a.id = s.ad_impression_id "
                            "WHERE s.vote_item_id=%s AND a.status='COMPLETED'", (item2,))
                vcheck("셔플에는 광고 시청 기록이 따라붙음", cur.fetchone()[0] == 1)

                vcheck("셔플은 문항당 1회뿐",
                       expect_error(cur, A_AUTH, "SELECT shuffle_candidates(%s)", (item2,)),
                       "DB 제약이 막음")

                # --- 후보 채우기 -------------------------------------------
                # 같은 반 친구를 다른 반으로 옮기면 CLASS 후보가 모자라진다.
                # 스코프를 낮추는 대신 다른 친구로 채워야 한다.
                cur.execute("SAVEPOINT downgrade")
                cur.execute("INSERT INTO grade_class (school_id, grade, class_num) "
                            "SELECT school_id, 2, 1 FROM grade_class WHERE id=%s RETURNING id",
                            (ctx["class"],))
                class2 = cur.fetchone()[0]
                cur.execute("UPDATE app_user SET class_id=%s WHERE id = ANY(%s)",
                            (class2, [ids["D1"], ids["D2"], ids["D3"], ids["D4"]]))
                cur.execute("UPDATE vote_session SET status='COMPLETED', completed_at=now() "
                            "WHERE id=%s", (session,))

                session2 = rpc(cur, A_AUTH, "SELECT start_vote_session()")
                cur.execute("""
                    SELECT count(*) FILTER (WHERE q.scope='CLASS'),
                           count(*) FILTER (WHERE q.scope='CLASS' AND v.candidate_scope<>'CLASS'),
                           coalesce(sum(v.padded_count) FILTER (WHERE q.scope='CLASS'), 0)
                      FROM vote_item v JOIN question q ON q.id = v.question_id
                     WHERE v.session_id = %s
                """, (session2,))
                class_items, downgraded, padded = cur.fetchone()
                vcheck("스코프는 낮추지 않고 유지된다",
                       downgraded == 0, f"CLASS 질문 {class_items}개 중 바뀐 것 {downgraded}개")
                vcheck("모자란 자리는 다른 친구로 채운다",
                       class_items == 0 or padded > 0, f"채운 후보 {padded}명")

                # 채운 후보까지 포함해 언제나 4명이어야 한다
                cur.execute("""
                    SELECT count(*) FROM vote_item v
                     WHERE v.session_id = %s
                       AND (SELECT count(*) FROM vote_candidate c
                             WHERE c.vote_item_id = v.id AND c.shuffle_round = 0) <> 4
                """, (session2,))
                vcheck("채운 뒤에도 후보는 4명", cur.fetchone()[0] == 0)

                # 친구가 전부 사라지면 4명을 못 채운다 → 세션이 열리지 않는다
                cur.execute("UPDATE app_user SET status='WITHDRAWN' WHERE id = ANY(%s)",
                            (friends,))
                cur.execute("UPDATE vote_session SET status='COMPLETED', completed_at=now() "
                            "WHERE id=%s", (session2,))
                vcheck("친구 전체로도 4명이 안 되면 질문을 내지 않음",
                       expect_error(cur, A_AUTH, "SELECT start_vote_session()"), "예외 기대")

                cur.execute("ROLLBACK TO SAVEPOINT downgrade")
                cur.execute("SET LOCAL ROLE postgres")
            except Exception as e:
                print(f"  실패!! 투표 RPC 호출  ({type(e).__name__}: {e})")
                failures.append("[투표] RPC 호출 실패")
            finally:
                cur.execute("ROLLBACK TO SAVEPOINT voting")
                cur.execute("SET LOCAL ROLE postgres")

            # ---------------------------------------------------------
            # 받은 투표 · 힌트 — 값을 치르기 전에는 새지 않는가 (W6)
            #
            # "누가 나를 뽑았는가"를 하트로 파는 것이 이 서비스의 수익 구조다.
            # 공짜로 알아낼 수 있는 경로가 하나라도 있으면 서비스가 성립하지 않는다.
            # ---------------------------------------------------------
            # 받은 투표(W6)의 순차 힌트 시험은 W14 에서 걷어냈다.
            # 힌트가 순차 4단계에서 선택형 5+1 로 바뀌어 시험 대상이 사라졌다.
            # 새 시험은 아래 "선택형 힌트 시험" 에 있다.
            # ---------------------------------------------------------
            # ---------------------------------------------------------
            # 접속 로그 — 리텐션을 실측할 재료가 실제로 쌓이는가
            # ---------------------------------------------------------
            print()
            print("접속 로그 시험")

            def scheck(desc: str, ok: bool, detail=""):
                print(f"  {'동작함' if ok else '실패!!'} {desc}  ({detail})")
                if not ok:
                    failures.append(f"[접속로그] {desc}")

            def session_count() -> int:
                cur.execute("SELECT count(*) FROM user_session WHERE user_id=%s", (A,))
                return cur.fetchone()[0]

            cur.execute("SAVEPOINT sessionlog")
            try:
                cur.execute("DELETE FROM user_session WHERE user_id=%s", (A,))
                cur.execute("UPDATE app_user SET last_active_at=NULL WHERE id=%s", (A,))

                s1 = rpc(cur, A_AUTH, "SELECT touch_session('WEB','test')")
                cur.execute("SELECT last_active_at IS NOT NULL FROM app_user WHERE id=%s", (A,))
                active = cur.fetchone()[0]
                scheck("접속하면 세션이 기록되고 마지막 활동 시각이 찍힘",
                       s1 is not None and session_count() == 1 and active,
                       f"세션 {session_count()}개")

                s2 = rpc(cur, A_AUTH, "SELECT touch_session('WEB','test')")
                scheck("새로고침해도 세션이 늘어나지 않음",
                       s2 == s1 and session_count() == 1, "30분 안은 같은 세션")

                # 30분이 지나면 새 세션으로 센다
                cur.execute("UPDATE user_session SET started_at = now() - interval '2 hours', "
                            "ended_at = now() - interval '2 hours' WHERE user_id=%s", (A,))
                s3 = rpc(cur, A_AUTH, "SELECT touch_session('WEB','test')")
                scheck("30분이 지나면 새 세션", s3 != s1 and session_count() == 2, "2개 기대")

                # 온보딩 전(프로필 없음)에는 조용히 넘어가야 한다
                scheck("프로필이 없으면 오류 없이 넘어감",
                       rpc(cur, C_AUTH, "SELECT touch_session('WEB','test')") is None,
                       "NULL 반환")
            except Exception as e:
                print(f"  실패!! 접속 로그 RPC  ({type(e).__name__}: {e})")
                failures.append("[접속로그] touch_session 호출 실패")
            finally:
                cur.execute("ROLLBACK TO SAVEPOINT sessionlog")
                cur.execute("SET LOCAL ROLE postgres")

            # ---------------------------------------------------------
            # 프로필 수정 (W11)
            #
            # 가입과 수정이 **같은 규칙**을 따르는지가 전부다.
            # 직접 UPDATE 권한이 남아 있으면 규칙을 건너뛸 수 있다.
            # ---------------------------------------------------------
            print()
            print("프로필 수정 시험")

            def pcheck(desc: str, ok: bool, detail=""):
                print(f"  {'동작함' if ok else '실패!!'} {desc}  ({detail})")
                if not ok:
                    failures.append(f"[프로필] {desc}")

            cur.execute("SAVEPOINT profile")
            try:
                # 시험 학급은 selectable_school 에 들어가야 고를 수 있다.
                cur.execute("SELECT count(*) FROM selectable_school WHERE id = "
                            "(SELECT school_id FROM grade_class WHERE id=%s)", (ctx["class"],))
                selectable = cur.fetchone()[0] == 1

                pcheck("app_user 를 직접 UPDATE 할 수 없음",
                       expect_error(cur, A_AUTH,
                                    "UPDATE app_user SET nickname='직접수정' "
                                    "WHERE id=%s RETURNING id", (A,)),
                       "권한거부")

                if selectable:
                    row = rpc(cur, A_AUTH, "SELECT nickname FROM "
                              "update_profile('바꾼이름', %s, 'M')", (ctx["class"],))
                    pcheck("RPC 로는 바꿀 수 있음", row == "바꾼이름", f"{row}")
                else:
                    pcheck("RPC 로는 바꿀 수 있음", True, "시험 학교가 목록 밖이라 건너뜀")

                pcheck("빈 닉네임은 거부",
                       expect_error(cur, A_AUTH,
                                    "SELECT update_profile('  ', %s, 'M')", (ctx["class"],)),
                       "차단")
                pcheck("한 글자 닉네임은 거부",
                       expect_error(cur, A_AUTH,
                                    "SELECT update_profile('가', %s, 'M')", (ctx["class"],)),
                       "차단")
                pcheck("성별 없이는 거부",
                       expect_error(cur, A_AUTH,
                                    "SELECT update_profile('이름', %s, NULL)", (ctx["class"],)),
                       "차단")
                pcheck("고를 수 없는 학급으로는 못 옮김",
                       expect_error(cur, A_AUTH,
                                    "SELECT update_profile('이름', 999999999, 'M')"),
                       "차단")

                # 하트·초대코드는 이 통로로도 못 바꾼다.
                cur.execute("SELECT heart_balance, invite_code FROM app_user WHERE id=%s", (A,))
                before = cur.fetchone()
                if selectable:
                    rpc(cur, A_AUTH, "SELECT id FROM update_profile('또바꿈', %s, 'F')",
                        (ctx["class"],))
                cur.execute("SELECT heart_balance, invite_code FROM app_user WHERE id=%s", (A,))
                pcheck("하트와 초대코드는 그대로", cur.fetchone() == before, "변화 없음")
            except Exception as e:
                print(f"  실패!! 프로필 RPC  ({type(e).__name__}: {e})")
                failures.append("[프로필] RPC 호출 실패")
            finally:
                cur.execute("ROLLBACK TO SAVEPOINT profile")
                cur.execute("SET LOCAL ROLE postgres")

            # ---------------------------------------------------------
            # 1회성 답장 (W15)
            #
            # 방향이 헷갈리기 쉽다 — **지목당한 쪽이 뽑은 쪽에게** 보낸다.
            # 한 번뿐이고, 뽑은 사람만 볼 수 있어야 한다.
            # ---------------------------------------------------------
            print()
            print("답장 시험")

            def rcheck2(desc: str, ok: bool, detail=""):
                print(f"  {'동작함' if ok else '실패!!'} {desc}  ({detail})")
                if not ok:
                    failures.append(f"[답장] {desc}")

            cur.execute("SAVEPOINT reply")
            try:
                recv = ctx["received"]      # A 가 B 를 뽑았다 → B 가 답장한다
                cur.execute("UPDATE app_user SET heart_balance = 100 WHERE id=%s", (B,))

                rcheck2("빈 답장은 거부",
                        rpc(cur, B_AUTH, "SELECT send_reply(%s,'   ')", (recv,)) == "EMPTY",
                        "EMPTY")
                rcheck2("30자를 넘으면 거부",
                        rpc(cur, B_AUTH, "SELECT send_reply(%s,%s)", (recv, "가" * 31))
                        == "TOO_LONG", "TOO_LONG")
                rcheck2("남이 받은 투표에는 답장 못 함",
                        rpc(cur, A_AUTH, "SELECT send_reply(%s,'침입')", (recv,)) == "NOT_FOUND",
                        "NOT_FOUND")

                rcheck2("답장이 보내짐",
                        rpc(cur, B_AUTH, "SELECT send_reply(%s,'고마워요')", (recv,)) == "OK",
                        "OK")
                rcheck2("두 번은 못 보냄",
                        rpc(cur, B_AUTH, "SELECT send_reply(%s,'또')", (recv,)) == "ALREADY",
                        "ALREADY")

                cur.execute("SELECT heart_balance FROM app_user WHERE id=%s", (B,))
                rcheck2("하트가 20 빠짐", cur.fetchone()[0] == 80, "100 → 80")
                cur.execute("""SELECT delta, type_code FROM heart_transaction
                                WHERE user_id=%s AND type_code='VOTE_REPLY'""", (B,))
                rcheck2("원장에 VOTE_REPLY 로 남음", cur.fetchone() == (-20, "VOTE_REPLY"),
                        "-20")

                # my_vote_history 는 "선택된 후보"가 있어야 행을 낸다.
                # setup 은 후보를 만들지 않으므로 여기서 하나 넣는다.
                cur.execute("INSERT INTO vote_candidate "
                            "(vote_item_id, candidate_user_id, shuffle_round, slot, is_chosen) "
                            "VALUES (%s,%s,0,1,true) ON CONFLICT DO NOTHING",
                            (ctx["item"], B))
                got = rpc(cur, A_AUTH,
                          "SELECT reply_text FROM my_vote_history WHERE vote_item_id=%s",
                          (ctx["item"],))
                rcheck2("뽑은 사람에게 답장이 보임", got == "고마워요", f"{got}")

                # 힌트와 무관하다 — 아무것도 안 열어도 보냈다.
                cur.execute("SELECT count(*) FROM hint_purchase WHERE vote_received_id=%s",
                            (recv,))
                rcheck2("힌트를 열지 않아도 보낼 수 있음", cur.fetchone()[0] == 0, "힌트 0개")

                # 신고
                rcheck2("받은 답장을 신고할 수 있음",
                        rpc(cur, A_AUTH,
                            "SELECT report_reply(%s,'U_HARASSMENT','시험')", (ctx["item"],))
                        == "OK", "OK")
                rcheck2("같은 사람을 두 번 신고해도 한 건",
                        rpc(cur, A_AUTH,
                            "SELECT report_reply(%s,'U_HARASSMENT',NULL)", (ctx["item"],))
                        == "ALREADY", "ALREADY")
                rcheck2("게시글용 사유로는 신고 못 함",
                        expect_error(cur, A_AUTH,
                                     "SELECT report_reply(%s,'P_ABUSE',NULL)", (ctx["item"],)),
                        "차단")

                # 하트가 모자라면
                cur.execute("UPDATE app_user SET heart_balance = 5 WHERE id=%s", (B,))
                cur.execute("UPDATE vote_received SET reply_text=NULL, replied_at=NULL "
                            "WHERE id=%s", (recv,))
                rcheck2("하트가 모자라면 못 보냄",
                        rpc(cur, B_AUTH, "SELECT send_reply(%s,'또')", (recv,)) == "NOT_ENOUGH",
                        "NOT_ENOUGH")

                rcheck2("vote_received 를 직접 못 고침",
                        expect_error(cur, B_AUTH,
                                     "UPDATE vote_received SET reply_text='직접' "
                                     "WHERE id=%s RETURNING id", (recv,)),
                        "권한거부")
            except Exception as e:
                print(f"  실패!! 답장 RPC  ({type(e).__name__}: {e})")
                failures.append("[답장] RPC 호출 실패")
            finally:
                cur.execute("ROLLBACK TO SAVEPOINT reply")
                cur.execute("SET LOCAL ROLE postgres")

            # ---------------------------------------------------------
            # 선택형 힌트 (W14)
            #
            # 순차 4단계에서 **골라 사는 5+1** 로 바뀌었다. 확인할 것은 —
            # 안 산 것이 뷰로 새지 않는가, 이름이 3개 전에는 안 열리는가,
            # 광고 무료 열기가 하루 한 번인가.
            # ---------------------------------------------------------
            print()
            print("선택형 힌트 시험")

            def hcheck(desc: str, ok: bool, detail=""):
                print(f"  {'동작함' if ok else '실패!!'} {desc}  ({detail})")
                if not ok:
                    failures.append(f"[힌트] {desc}")

            cur.execute("SAVEPOINT hints")
            try:
                recv = ctx["received"]
                cur.execute("UPDATE app_user SET heart_balance = 1000 WHERE id=%s", (B,))
                cur.execute("UPDATE app_user SET nickname = '김형민' WHERE id=%s", (A,))

                def view(col):
                    return rpc(cur, B_AUTH,
                               f"SELECT {col} FROM my_vote_received WHERE id=%s", (recv,))

                hcheck("아무것도 안 샀으면 전부 가려짐",
                       (view("voter_gender"), view("voter_id"), view("voter_grade")) ==
                       (None, None, None), "성별·id·반 모두 NULL")
                hcheck("안 산 자모는 아예 안 나감",
                       (view("lead_hint"), view("vowel_hint"), view("tail_hint")) ==
                       (None, None, None), "셋 다 NULL")

                # 순서 없이 아무거나
                hcheck("성별부터 살 수 있음",
                       rpc(cur, B_AUTH, "SELECT buy_hint(%s,'GENDER')", (recv,)) == "OK", "OK")
                hcheck("반을 그다음에 살 수 있음",
                       rpc(cur, B_AUTH, "SELECT buy_hint(%s,'CLASS')", (recv,)) == "OK",
                       "순차가 아님")
                hcheck("산 것만 값이 나옴",
                       view("voter_gender") is not None and view("voter_grade") is not None
                       and view("voter_id") is None, "성별·반 나옴 / id 는 아직")
                hcheck("같은 유형은 두 번 못 삼",
                       rpc(cur, B_AUTH, "SELECT buy_hint(%s,'GENDER')", (recv,)) == "ALREADY",
                       "ALREADY")

                # ★ 3개 전에는 이름이 안 열린다
                hcheck("기본 2개로는 이름을 못 삼",
                       rpc(cur, B_AUTH, "SELECT buy_hint(%s,'FULL_NAME')", (recv,)) == "NEED_MORE",
                       "NEED_MORE")

                hcheck("초성을 사면 한 글자가 드러남",
                       rpc(cur, B_AUTH, "SELECT buy_hint(%s,'INITIAL')", (recv,)) == "OK", "OK")
                lead = view("lead_hint")
                hcheck("초성 힌트가 한 자리만 연다",
                       lead is not None and len(lead) == 3 and lead.count("○") == 2, lead)
                hcheck("초성을 샀어도 중성·종성은 닫혀 있음",
                       (view("vowel_hint"), view("tail_hint")) == (None, None),
                       "자모는 따로 산다")

                hcheck("3개가 되면 이름이 열림", view("can_unlock_name") is True, "can_unlock_name")
                hcheck("이름을 살 수 있음",
                       rpc(cur, B_AUTH, "SELECT buy_hint(%s,'FULL_NAME')", (recv,)) == "OK", "OK")
                hcheck("이름과 id 가 나옴",
                       view("voter_nickname") == "김형민" and view("voter_id") == A,
                       "김형민")

                cur.execute("SELECT heart_balance FROM app_user WHERE id=%s", (B,))
                hcheck("값이 20·20·20·100 으로 빠짐",
                       cur.fetchone()[0] == 1000 - 160, "1000 → 840")

                cur.execute("""SELECT count(*) FROM heart_transaction
                                WHERE user_id=%s AND type_code='HINT_PURCHASE'""", (B,))
                hcheck("원장에 네 건이 남음", cur.fetchone()[0] == 4, "4건")

                # 남의 것
                hcheck("남이 받은 투표에는 힌트를 못 삼",
                       rpc(cur, A_AUTH, "SELECT buy_hint(%s,'GENDER')", (recv,)) == "NOT_FOUND",
                       "NOT_FOUND")

                # 하트 부족
                # 새 vote_item 을 만들어야 한다. vote_received.vote_item_id 가
                # UNIQUE 라 기존 항목을 재사용하면 충돌한다.
                cur.execute("UPDATE app_user SET heart_balance = 5 WHERE id=%s", (B,))
                cur.execute("INSERT INTO vote_item (session_id, user_id, question_id, "
                            "candidate_scope, position, voted_at) "
                            "SELECT session_id, user_id, question_id, candidate_scope, 99, now() "
                            "FROM vote_item WHERE id=%s RETURNING id", (ctx["item"],))
                item2 = cur.fetchone()[0]
                cur.execute("INSERT INTO vote_received "
                            "(vote_item_id, voter_id, receiver_id, question_id) "
                            "VALUES (%s,%s,%s,%s) RETURNING id",
                            (item2, A, B, ctx["question"]))
                recv2 = cur.fetchone()[0]
                hcheck("하트가 모자라면 못 삼",
                       rpc(cur, B_AUTH, "SELECT buy_hint(%s,'GENDER')", (recv2,))
                       == "NOT_ENOUGH", "NOT_ENOUGH")

                # 광고
                hcheck("오늘 광고를 쓸 수 있음",
                       rpc(cur, B_AUTH, "SELECT ad_available FROM my_hint_ad_state") is True,
                       "ad_available")
                hcheck("hint_purchase 에 직접 INSERT 못 함",
                       expect_error(cur, B_AUTH,
                                    "INSERT INTO hint_purchase "
                                    "(vote_received_id, user_id, hint_type, step, heart_cost) "
                                    "VALUES (%s,%s,'FULL_NAME',1,0) RETURNING id", (recv, B)),
                       "권한거부")
            except Exception as e:
                print(f"  실패!! 힌트 RPC  ({type(e).__name__}: {e})")
                failures.append("[힌트] RPC 호출 실패")
            finally:
                cur.execute("ROLLBACK TO SAVEPOINT hints")
                cur.execute("SET LOCAL ROLE postgres")

            # ---------------------------------------------------------
            # 하트 충전 (W13)
            #
            # 결제가 없으므로 **하루 한 번**이 하트 경제를 지키는 유일한 장치다.
            # 뚫리면 하트가 무한이 되고, 힌트 가격도 소비 패턴도 관찰할 수 없다.
            # ---------------------------------------------------------
            print()
            print("하트 충전 시험")

            def tcheck(desc: str, ok: bool, detail=""):
                print(f"  {'동작함' if ok else '실패!!'} {desc}  ({detail})")
                if not ok:
                    failures.append(f"[충전] {desc}")

            cur.execute("SAVEPOINT topup")
            try:
                cur.execute("SELECT heart_balance FROM app_user WHERE id=%s", (A,))
                before = cur.fetchone()[0]

                tcheck("살 수 있는 상태로 시작",
                       rpc(cur, A_AUTH, "SELECT can_purchase FROM my_topup_state") is True,
                       "can_purchase = true")

                tcheck("없는 상품은 거부",
                       rpc(cur, A_AUTH, "SELECT purchase_hearts('heart.999')") == "NOT_FOUND",
                       "NOT_FOUND")

                tcheck("충전이 처리됨",
                       rpc(cur, A_AUTH, "SELECT purchase_hearts('heart.1000')") == "OK", "OK")

                cur.execute("SELECT heart_balance FROM app_user WHERE id=%s", (A,))
                after = cur.fetchone()[0]
                tcheck("하트가 상품 수량만큼 늘어남", after == before + 1000,
                       f"{before} → {after}")

                cur.execute("""SELECT t.delta, t.balance_after, t.purchase_id IS NOT NULL
                                 FROM heart_transaction t
                                WHERE t.user_id=%s AND t.type_code='TOPUP'""", (A,))
                tx = cur.fetchone()
                tcheck("원장에 남고 잔액이 일치", tx == (1000, after, True), f"{tx}")

                cur.execute("""SELECT status, store_transaction_id LIKE 'MVP-STUB-%%'
                                 FROM heart_purchase WHERE user_id=%s""", (A,))
                pur = cur.fetchone()
                tcheck("스텁 결제임이 기록에 남음", pur == ("SUCCESS", True),
                       "MVP-STUB- 접두어")

                # ★ 이것이 이 기능의 전부다.
                tcheck("같은 날 두 번째는 막힘",
                       rpc(cur, A_AUTH, "SELECT purchase_hearts('heart.4000')") == "ALREADY_TODAY",
                       "ALREADY_TODAY")
                tcheck("제일 싼 것을 골라도 막힘",
                       rpc(cur, A_AUTH, "SELECT purchase_hearts('heart.200')") == "ALREADY_TODAY",
                       "상품을 가리지 않음")
                tcheck("상태도 못 산다고 알려줌",
                       rpc(cur, A_AUTH, "SELECT can_purchase FROM my_topup_state") is False,
                       "can_purchase = false")

                cur.execute("SELECT heart_balance FROM app_user WHERE id=%s", (A,))
                tcheck("막힌 시도로 하트가 늘지 않음", cur.fetchone()[0] == after, f"{after}")

                # 어제 산 것으로 바꾸면 다시 열려야 한다.
                cur.execute("UPDATE heart_purchase SET created_at = now() - interval '2 days' "
                            "WHERE user_id=%s", (A,))
                tcheck("날이 바뀌면 다시 살 수 있음",
                       rpc(cur, A_AUTH, "SELECT can_purchase FROM my_topup_state") is True,
                       "can_purchase = true")

                tcheck("heart_purchase 에 직접 INSERT 못 함",
                       expect_error(cur, A_AUTH,
                                    "INSERT INTO heart_purchase "
                                    "(user_id, product_id, platform, status, price_krw, heart_amount) "
                                    "SELECT %s, id, 'WEB', 'SUCCESS', 0, 99999 "
                                    "FROM heart_product LIMIT 1 RETURNING id", (A,)),
                       "권한거부")
            except Exception as e:
                print(f"  실패!! 충전 RPC  ({type(e).__name__}: {e})")
                failures.append("[충전] RPC 호출 실패")
            finally:
                cur.execute("ROLLBACK TO SAVEPOINT topup")
                cur.execute("SET LOCAL ROLE postgres")

            # ---------------------------------------------------------
            # 계정 삭제 (W12)
            #
            # 행을 지우지 않고 status 를 바꾼다. 확인할 것은 셋이다 —
            # 사유가 남는가, 목록에서 사라지는가, 다시 못 들어오는가.
            # ---------------------------------------------------------
            print()
            print("계정 삭제 시험")

            def wcheck(desc: str, ok: bool, detail=""):
                print(f"  {'동작함' if ok else '실패!!'} {desc}  ({detail})")
                if not ok:
                    failures.append(f"[탈퇴] {desc}")

            cur.execute("SAVEPOINT withdraw")
            try:
                wcheck("없는 사유로는 탈퇴할 수 없음",
                       expect_error(cur, B_AUTH, "SELECT withdraw_account('없는사유')"),
                       "차단")
                wcheck("user_withdrawal 에 직접 INSERT 못 함",
                       expect_error(cur, B_AUTH,
                                    "INSERT INTO user_withdrawal (user_id, reason_code) "
                                    "VALUES (%s,'OTHER') RETURNING id", (A,)),
                       "권한거부")

                gone = rpc(cur, B_AUTH,
                           "SELECT withdraw_account('NOT_USING', '시험 탈퇴')")
                wcheck("탈퇴가 처리됨", gone is True, "true")

                cur.execute("SELECT status, auth_user_id IS NULL FROM app_user WHERE id=%s", (B,))
                st, unlinked = cur.fetchone()
                wcheck("행은 남고 상태만 바뀜", st == "WITHDRAWN", f"{st}")
                wcheck("로그인 연결이 끊김", unlinked, "auth_user_id = NULL")

                cur.execute("SELECT reason_code, reason_text FROM user_withdrawal "
                            "WHERE user_id=%s", (B,))
                row = cur.fetchone()
                wcheck("누가 왜 그만뒀는지 남음",
                       row == ("NOT_USING", "시험 탈퇴"), f"{row}")

                wcheck("탈퇴한 사람은 친구 목록에서 사라짐",
                       rpc(cur, A_AUTH,
                           "SELECT count(*) FROM friend_profile WHERE id=%s", (B,)) == 0,
                       "0행")
                wcheck("탈퇴한 사람은 추천에도 안 뜸",
                       rpc(cur, A_AUTH,
                           "SELECT count(*) FROM friend_suggestion WHERE id=%s", (B,)) == 0,
                       "0행")
                wcheck("탈퇴한 계정으로는 아무것도 못 함",
                       rpc(cur, B_AUTH, "SELECT current_app_user_id()") is None,
                       "프로필 없음")
            except Exception as e:
                print(f"  실패!! 탈퇴 RPC  ({type(e).__name__}: {e})")
                failures.append("[탈퇴] RPC 호출 실패")
            finally:
                cur.execute("ROLLBACK TO SAVEPOINT withdraw")
                cur.execute("SET LOCAL ROLE postgres")

            # ---------------------------------------------------------
            # 자유게시판 (W9)
            #
            # 익명이 아니라 닉네임이 드러나는 형태다. 확인할 것은 셋이다 —
            # 같은 학교 안에서만 보이는가, 쓰기가 RPC 밖으로 새지 않는가,
            # 그리고 한 사람이 한 글에 댓글을 여러 번 달 수 있는가
            # (익명 번호 UNIQUE 가 이걸 막고 있었다. 마이그레이션 005).
            # ---------------------------------------------------------
            print()
            print("자유게시판 시험")

            def bcheck(desc: str, ok: bool, detail=""):
                print(f"  {'동작함' if ok else '실패!!'} {desc}  ({detail})")
                if not ok:
                    failures.append(f"[게시판] {desc}")

            cur.execute("SAVEPOINT board")
            try:
                # 다른 학교 사람 하나. 게시판이 학교 밖으로 새는지 보려면 필요하다.
                out_auth = uuid.UUID("eeeeeeee-0000-4000-8000-000000000005")
                cur.execute("INSERT INTO auth.users (id) VALUES (%s) ON CONFLICT DO NOTHING",
                            (out_auth,))
                cur.execute("INSERT INTO region (sido, sigungu) VALUES ('시험','타구') "
                            "ON CONFLICT (sido, sigungu) DO UPDATE SET sido=EXCLUDED.sido "
                            "RETURNING id")
                rid2 = cur.fetchone()[0]
                cur.execute("INSERT INTO school (name_masked, region_id, school_type) "
                            "VALUES ('타*학교', %s, 'HIGH') RETURNING id", (rid2,))
                sid2 = cur.fetchone()[0]
                cur.execute("INSERT INTO grade_class (school_id, grade, class_num) "
                            "VALUES (%s, 1, 1) RETURNING id", (sid2,))
                cid2 = cur.fetchone()[0]
                cur.execute("INSERT INTO app_user (auth_user_id, nickname, invite_code, class_id) "
                            "VALUES (%s, '타교유저', 'TESTEE', %s) RETURNING id", (out_auth, cid2))
                outsider = cur.fetchone()[0]

                # --- 글쓰기 ---
                pid = rpc(cur, A_AUTH, "SELECT create_post('시험 제목', '시험 본문')")
                bcheck("글을 쓰면 id 가 돌아옴", pid is not None, f"post {pid}")

                seen = rpc(cur, B_AUTH,
                           "SELECT count(*) FROM board_post WHERE id=%s", (pid,))
                bcheck("같은 학교 사람에게 보임", seen == 1, f"{seen}건")

                nick = rpc(cur, B_AUTH,
                           "SELECT author_nickname FROM board_post WHERE id=%s", (pid,))
                bcheck("글쓴이 닉네임이 드러남 (익명 아님)", nick == "시험유저A", f"{nick}")

                out_seen = rpc(cur, out_auth,
                               "SELECT count(*) FROM board_post WHERE id=%s", (pid,))
                bcheck("다른 학교 사람에게는 안 보임", out_seen == 0, f"{out_seen}건")

                # --- 댓글 ---
                c1 = rpc(cur, B_AUTH, "SELECT create_comment(%s, '첫 댓글')", (pid,))
                c2 = rpc(cur, B_AUTH, "SELECT create_comment(%s, '같은 사람이 또 답글')", (pid,))
                bcheck("한 사람이 한 글에 댓글을 두 번 달 수 있음 (마이그레이션 005)",
                       c1 is not None and c2 is not None and c1 != c2, f"{c1}, {c2}")

                cnt = rpc(cur, A_AUTH, "SELECT comment_count FROM board_post WHERE id=%s", (pid,))
                bcheck("댓글 수 집계가 맞음", cnt == 2, f"{cnt}개")

                # 이건 postgres 로 본다. post_comment 는 유저에게 안 열려 있어서
                # (뷰로만 노출) 유저 권한으로 세면 RLS 에 막혀 0 이 나온다.
                cur.execute("SELECT count(*) FROM post_comment WHERE post_id=%s "
                            "AND anonymous_seq IS NULL", (pid,))
                cseq = cur.fetchone()[0]
                bcheck("익명 번호를 쓰지 않음", cseq == 2, f"NULL {cseq}개")

                # 학교 경계는 읽기만 막아서는 부족하다. 글 id 는 순번이라
                # 찍어볼 수 있으므로 **쓰는 쪽 경로를 전부** 확인한다.
                bcheck("다른 학교 글에는 댓글을 못 닮",
                       expect_error(cur, out_auth, "SELECT create_comment(%s, '침입')", (pid,)),
                       "차단")
                bcheck("다른 학교 글에 좋아요를 못 누름",
                       expect_error(cur, out_auth, "SELECT toggle_post_like(%s)", (pid,)),
                       "차단")
                bcheck("다른 학교 댓글에 좋아요를 못 누름",
                       expect_error(cur, out_auth, "SELECT toggle_comment_like(%s)", (c1,)),
                       "차단")
                bcheck("다른 학교 글을 신고해도 접수되지 않음",
                       rpc(cur, out_auth,
                           "SELECT report_content('POST', %s, 'P_ABUSE', NULL)", (pid,))
                       == "NOT_FOUND", "NOT_FOUND")
                bcheck("다른 학교 글은 지울 수 없음",
                       rpc(cur, out_auth, "SELECT delete_own_post(%s)", (pid,)) is False, "false")
                rpc(cur, out_auth, "SELECT bump_post_view(%s)", (pid,))
                cur.execute("SELECT view_count, report_count, status FROM post WHERE id=%s", (pid,))
                vc, rc, st = cur.fetchone()
                bcheck("외부인이 건드려도 글은 그대로",
                       (vc, rc, st) == (0, 0, "PUBLISHED"),
                       f"조회 {vc} / 신고 {rc} / {st}")
                bcheck("외부인은 댓글 목록도 못 봄",
                       rpc(cur, out_auth,
                           "SELECT count(*) FROM board_comment WHERE post_id=%s", (pid,)) == 0,
                       "0건")

                # --- 좋아요 ---
                on = rpc(cur, B_AUTH, "SELECT toggle_post_like(%s)", (pid,))
                liked = rpc(cur, A_AUTH, "SELECT like_count FROM board_post WHERE id=%s", (pid,))
                bcheck("좋아요를 누르면 켜지고 집계가 오름", on is True and liked == 1, f"{liked}개")

                off = rpc(cur, B_AUTH, "SELECT toggle_post_like(%s)", (pid,))
                unliked = rpc(cur, A_AUTH, "SELECT like_count FROM board_post WHERE id=%s", (pid,))
                bcheck("다시 누르면 꺼지고 집계가 내려감",
                       off is False and unliked == 0, f"{unliked}개")

                # --- 쓰기가 RPC 밖으로 새지 않는가 ---
                bcheck("post 에 직접 INSERT 못 함",
                       expect_error(cur, A_AUTH,
                                    "INSERT INTO post (school_id, category_id, author_id, title, body) "
                                    "SELECT 1, 1, %s, 'x', 'y' RETURNING id", (B,)),
                       "권한거부")
                bcheck("post_like 에 직접 INSERT 못 함 (좋아요 조작)",
                       expect_error(cur, A_AUTH,
                                    "INSERT INTO post_like (post_id, user_id) "
                                    "VALUES (%s, %s) RETURNING id", (pid, A)),
                       "권한거부")
                bcheck("남의 글을 직접 UPDATE 못 함",
                       expect_error(cur, B_AUTH,
                                    "UPDATE post SET title='탈취' WHERE id=%s RETURNING id", (pid,)),
                       "권한거부")

                # --- 신고 ---
                r1 = rpc(cur, B_AUTH, "SELECT report_content('POST', %s, 'P_ABUSE', '욕설')", (pid,))
                bcheck("신고가 접수됨", r1 == "OK", f"{r1}")

                r2 = rpc(cur, B_AUTH, "SELECT report_content('POST', %s, 'P_ABUSE', NULL)", (pid,))
                bcheck("같은 사람이 두 번 신고해도 한 건", r2 == "ALREADY", f"{r2}")

                cur.execute("SELECT report_count FROM post WHERE id=%s", (pid,))
                rcnt = cur.fetchone()[0]
                bcheck("신고 수가 한 번만 오름", rcnt == 1, f"{rcnt}건")

                r3 = rpc(cur, A_AUTH, "SELECT report_content('POST', %s, 'P_ABUSE', NULL)", (pid,))
                bcheck("자기 글은 신고할 수 없음", r3 == "SELF", f"{r3}")

                bcheck("댓글용 사유로 글을 신고할 수 없음",
                       expect_error(cur, B_AUTH,
                                    "SELECT report_content('POST', %s, 'C_ABUSE', NULL)", (pid,)),
                       "차단")

                # 신고해도 글은 그대로 있어야 한다. 자동 숨김은 집단 신고에 취약해
                # 채택하지 않았다(DECISIONS).
                still = rpc(cur, B_AUTH, "SELECT count(*) FROM board_post WHERE id=%s", (pid,))
                bcheck("신고해도 자동으로 내려가지 않음", still == 1, "사람이 판단")

                # --- 삭제 ---
                bcheck("남의 글은 지울 수 없음",
                       rpc(cur, B_AUTH, "SELECT delete_own_post(%s)", (pid,)) is False, "false")

                gone = rpc(cur, A_AUTH, "SELECT delete_own_post(%s)", (pid,))
                left = rpc(cur, B_AUTH, "SELECT count(*) FROM board_post WHERE id=%s", (pid,))
                bcheck("내 글을 지우면 목록에서 사라짐", gone is True and left == 0, f"{left}건")

                cur.execute("SELECT status FROM post WHERE id=%s", (pid,))
                bcheck("행은 남는다 (신고 기록이 가리키고 있다)",
                       cur.fetchone()[0] == "DELETED", "DELETED")
            except Exception as e:
                print(f"  실패!! 게시판 RPC  ({type(e).__name__}: {e})")
                failures.append("[게시판] RPC 호출 실패")
            finally:
                cur.execute("ROLLBACK TO SAVEPOINT board")
                cur.execute("SET LOCAL ROLE postgres")

            # ---------------------------------------------------------
            # 친구 추천 (W10)
            #
            # 이 기능은 "초대 코드로만 친구를 맺는다"를 좁은 범위에서 연다.
            # 그래서 **범위가 정확히 그만큼인지**가 전부다 —
            # 같은 학교만, 더미는 빼고, 코드는 내보내지 않고.
            # ---------------------------------------------------------
            print()
            print("친구 추천 시험")

            def rcheck(desc: str, ok: bool, detail=""):
                print(f"  {'동작함' if ok else '실패!!'} {desc}  ({detail})")
                if not ok:
                    failures.append(f"[추천] {desc}")

            cur.execute("SAVEPOINT recommend")
            try:
                # A 와 같은 학교의 생판 남 하나, 그리고 같은 학교의 더미 하나.
                far_auth = uuid.UUID("ffffffff-0000-4000-8000-000000000006")
                cur.execute("INSERT INTO auth.users (id) VALUES (%s) ON CONFLICT DO NOTHING",
                            (far_auth,))
                cur.execute("INSERT INTO grade_class (school_id, grade, class_num) "
                            "SELECT g.school_id, 2, 7 FROM grade_class g WHERE g.id=%s "
                            "RETURNING id", (ctx["class"],))
                other_class = cur.fetchone()[0]
                cur.execute("INSERT INTO app_user (auth_user_id, nickname, invite_code, class_id) "
                            "VALUES (%s, '같은학교남', 'TESTFF', %s) RETURNING id",
                            (far_auth, other_class))
                stranger = cur.fetchone()[0]
                cur.execute("INSERT INTO app_user (nickname, invite_code, class_id, is_synthetic) "
                            "VALUES ('더미친구', 'TESTGG', %s, true) RETURNING id", (ctx["class"],))
                dummy = cur.fetchone()[0]

                # 다른 학교 사람. 게시판 블록의 것은 롤백돼 사라졌으므로 새로 만든다
                # — 없는 유저로 시험하면 "프로필이 없어서" 0행이 나와 통과한 것처럼 보인다.
                far2 = uuid.UUID("ffffffff-0000-4000-8000-000000000008")
                cur.execute("INSERT INTO auth.users (id) VALUES (%s) ON CONFLICT DO NOTHING", (far2,))
                cur.execute("INSERT INTO region (sido, sigungu) VALUES ('추천시','구') RETURNING id")
                r2 = cur.fetchone()[0]
                cur.execute("INSERT INTO school (name_masked, region_id, school_type) "
                            "VALUES ('추*학교', %s, 'HIGH') RETURNING id", (r2,))
                s2 = cur.fetchone()[0]
                cur.execute("INSERT INTO grade_class (school_id, grade, class_num) "
                            "VALUES (%s,1,1) RETURNING id", (s2,))
                c2 = cur.fetchone()[0]
                cur.execute("INSERT INTO app_user (auth_user_id, nickname, invite_code, class_id) "
                            "VALUES (%s, '타교사람', 'TESTJJ', %s) RETURNING id", (far2, c2))
                far_user = cur.fetchone()[0]

                shown = rpc(cur, A_AUTH,
                            "SELECT count(*) FROM friend_suggestion WHERE id=%s", (stranger,))
                rcheck("같은 학교 사람이 추천에 뜸", shown == 1, f"{shown}건")

                # ★ 더미를 남겨둔 근거가 "테스터가 마주칠 경로가 없다"였다.
                dshown = rpc(cur, A_AUTH,
                             "SELECT count(*) FROM friend_suggestion WHERE id=%s", (dummy,))
                rcheck("더미는 추천에 뜨지 않음", dshown == 0, f"{dshown}건")

                oshown = rpc(cur, far2,
                             "SELECT count(*) FROM friend_suggestion WHERE id=%s", (stranger,))
                rcheck("다른 학교 사람은 서로 추천되지 않음", oshown == 0, f"{oshown}건")

                cur.execute("SELECT count(*) FROM information_schema.columns "
                            "WHERE table_name='friend_suggestion' AND column_name='invite_code'")
                rcheck("추천 목록에 초대 코드가 없음", cur.fetchone()[0] == 0, "컬럼 없음")

                # 보내기
                sent = rpc(cur, A_AUTH, "SELECT send_request_to(%s)", (stranger,))
                rcheck("추천에서 요청을 보낼 수 있음", sent == "SENT", f"{sent}")

                left = rpc(cur, A_AUTH,
                           "SELECT count(*) FROM friend_suggestion WHERE id=%s", (stranger,))
                rcheck("보낸 뒤에는 목록에서 사라짐", left == 0, f"{left}건")

                # ★ 추천 밖의 사람은 지목할 수 없다. 이게 뚫리면 이 함수가
                #   곧 전체 가입자 지목 통로가 된다.
                rcheck("더미에게는 요청을 보낼 수 없음",
                       rpc(cur, A_AUTH, "SELECT send_request_to(%s)", (dummy,)) == "NOT_FOUND",
                       "NOT_FOUND")
                rcheck("다른 학교 사람에게는 요청을 보낼 수 없음",
                       rpc(cur, A_AUTH, "SELECT send_request_to(%s)", (far_user,)) == "NOT_FOUND",
                       "NOT_FOUND")
                rcheck("다른 학교에서 이쪽으로도 못 보냄",
                       rpc(cur, far2, "SELECT send_request_to(%s)", (stranger,)) == "NOT_FOUND",
                       "NOT_FOUND")

                # 안 볼래
                cur.execute("INSERT INTO auth.users (id) VALUES (%s) ON CONFLICT DO NOTHING",
                            (uuid.UUID("ffffffff-0000-4000-8000-000000000007"),))
                cur.execute("INSERT INTO app_user (auth_user_id, nickname, invite_code, class_id) "
                            "VALUES (%s, '안볼사람', 'TESTHH', %s) RETURNING id",
                            (uuid.UUID("ffffffff-0000-4000-8000-000000000007"), other_class))
                skip = cur.fetchone()[0]

                rcheck("안 볼래를 누르면 true",
                       rpc(cur, A_AUTH, "SELECT dismiss_suggestion(%s)", (skip,)) is True, "true")
                rcheck("안 볼래 한 사람은 목록에서 사라짐",
                       rpc(cur, A_AUTH,
                           "SELECT count(*) FROM friend_suggestion WHERE id=%s", (skip,)) == 0,
                       "0건")
                # 안 볼래는 차단이 아니다. 상대는 여전히 나를 부를 수 있어야 한다.
                rcheck("안 볼래 해도 상대에게는 내가 보임",
                       rpc(cur, uuid.UUID("ffffffff-0000-4000-8000-000000000007"),
                           "SELECT count(*) FROM friend_suggestion WHERE id=%s", (A,)) == 1,
                       "차단이 아님")

                rcheck("friend_recommendation 에 직접 INSERT 못 함",
                       expect_error(cur, A_AUTH,
                                    "INSERT INTO friend_recommendation "
                                    "(user_id, recommended_user_id, reason) "
                                    "VALUES (%s, %s, 'SAME_SCHOOL') RETURNING id", (B, A)),
                       "권한거부")
            except Exception as e:
                print(f"  실패!! 추천 RPC  ({type(e).__name__}: {e})")
                failures.append("[추천] RPC 호출 실패")
            finally:
                cur.execute("ROLLBACK TO SAVEPOINT recommend")
                cur.execute("SET LOCAL ROLE postgres")

            # ---------------------------------------------------------
            # 학교 정보 — 급식 · 학사일정 (W8 · W16)
            #
            # 이 둘은 RPC 가 없다. **정책 하나가 안전장치 전부**라서, 그
            # 정책이 학교 경계를 정말 지키는지 여기서 본다.
            #
            # 빌려 쓰는 경로(info_school_id)도 함께 본다 — 테스트 조직은
            # 자기 학교에 급식이 없고 서울고 것을 본다. 그 연결이 끊기면
            # 화면이 빈 달력이 되는데, 그건 오류를 내지 않는다.
            # ---------------------------------------------------------
            print()
            print("학교 정보 시험 (급식 · 학사일정)")

            def scheck(desc: str, ok: bool, detail=""):
                print(f"  {'동작함' if ok else '실패!!'} {desc}  ({detail})")
                if not ok:
                    failures.append(f"[학교정보] {desc}")

            cur.execute("SAVEPOINT schoolinfo")
            try:
                cur.execute("SELECT school_id FROM grade_class WHERE id=%s", (ctx["class"],))
                my_school = cur.fetchone()[0]

                # 남의 학교 하나. A 는 여기 소속이 아니다.
                cur.execute("INSERT INTO school (name_masked, region_id, school_type) "
                            "SELECT '남*학교', region_id, 'HIGH' FROM school WHERE id=%s "
                            "RETURNING id", (my_school,))
                far_school = cur.fetchone()[0]

                for sid, title in [(my_school, "우리 학교 시험기간"),
                                   (far_school, "남의 학교 시험기간")]:
                    cur.execute(
                        "INSERT INTO school_event (school_id, title, event_type, "
                        "start_date, end_date, source) "
                        "VALUES (%s, %s, 'EXAM', '2026-07-01', '2026-07-03', 'NEIS')",
                        (sid, title))
                    cur.execute(
                        "INSERT INTO meal_plan (school_id, serve_date, meal_type, source) "
                        "VALUES (%s, '2026-07-01', 'LUNCH', 'NEIS') RETURNING id", (sid,))
                    cur.execute("INSERT INTO meal_menu_item (meal_plan_id, dish_name, sort_order) "
                                "VALUES (%s, %s, 0)", (cur.fetchone()[0], title))

                scheck("내 학교 학사일정이 보임",
                       rpc(cur, A_AUTH, "SELECT count(*) FROM school_event") == 1, "1건")
                scheck("남의 학교 학사일정은 안 보임",
                       rpc(cur, A_AUTH,
                           "SELECT count(*) FROM school_event WHERE school_id=%s",
                           (far_school,)) == 0, "0건")
                scheck("내 학교 급식이 보임",
                       rpc(cur, A_AUTH, "SELECT count(*) FROM meal_plan") == 1, "1건")
                scheck("남의 학교 급식은 안 보임",
                       rpc(cur, A_AUTH,
                           "SELECT count(*) FROM meal_plan WHERE school_id=%s",
                           (far_school,)) == 0, "0건")
                # 메뉴는 부모의 학교까지 따라가 확인해야 한다. 부모가 존재하기만
                # 하면 통과하던 정책이 실제로 있었다(W8 에서 고침).
                scheck("남의 학교 메뉴는 안 보임",
                       rpc(cur, A_AUTH, "SELECT count(*) FROM meal_menu_item") == 1, "내 것 1건")

                # ★ 쓰기. 정책이 없어 RLS 가 막지만, 권한도 없어야 한다 —
                #   정책 하나를 잘못 넓히는 순간 뚫리기 때문이다.
                scheck("학사일정에 직접 INSERT 못 함",
                       expect_error(cur, A_AUTH,
                                    "INSERT INTO school_event (school_id, title, event_type, "
                                    "start_date, end_date) VALUES "
                                    "(%s, '가짜 방학', 'HOLIDAY', '2026-07-01', '2026-07-01') "
                                    "RETURNING id", (my_school,)),
                       "권한거부")
                scheck("학사일정을 고칠 수 없음",
                       expect_error(cur, A_AUTH,
                                    "UPDATE school_event SET title='조작' "
                                    "WHERE school_id=%s RETURNING id", (my_school,)),
                       "권한거부")
                scheck("학사일정을 지울 수 없음",
                       expect_error(cur, A_AUTH,
                                    "DELETE FROM school_event WHERE school_id=%s RETURNING id",
                                    (my_school,)), "권한거부")
                scheck("급식에 직접 INSERT 못 함",
                       expect_error(cur, A_AUTH,
                                    "INSERT INTO meal_plan (school_id, serve_date, meal_type) "
                                    "VALUES (%s, '2026-07-02', 'LUNCH') RETURNING id", (my_school,)),
                       "권한거부")

                # 빌려 쓰기 — 내 학교를 남의 학교 정보에 붙이면 그쪽이 보여야 한다.
                cur.execute("UPDATE school SET info_school_id=%s WHERE id=%s",
                            (far_school, my_school))
                scheck("빌려 쓰면 그 학교 학사일정이 보임",
                       rpc(cur, A_AUTH,
                           "SELECT count(*) FROM school_event WHERE school_id=%s",
                           (far_school,)) == 1, "1건")
                scheck("빌려 쓰면 내 학교 것은 안 보임",
                       rpc(cur, A_AUTH,
                           "SELECT count(*) FROM school_event WHERE school_id=%s",
                           (my_school,)) == 0, "0건")
                scheck("빌려 쓰는 사실이 화면에 전달됨",
                       rpc(cur, A_AUTH, "SELECT borrowed FROM my_school_source") is True,
                       "borrowed=true")
            except Exception as e:
                print(f"  실패!! 학교 정보  ({type(e).__name__}: {e})")
                failures.append("[학교정보] 시험 실행 실패")
            finally:
                cur.execute("ROLLBACK TO SAVEPOINT schoolinfo")
                cur.execute("SET LOCAL ROLE postgres")

            # ---------------------------------------------------------
            # 반대 방향 — 정상 동작이 막히지 않았는가
            #
            # 전부 차단해버려도 위 침투 시험은 통과한다. 그래서 이 시험이 필요하다.
            # 보안 검증은 "막을 것을 막았는가"와 "열 것을 열었는가"가 둘 다 필요하다.
            # ---------------------------------------------------------
            print()
            print("정상 동작 시험 (열려 있어야 할 것)")

            cur.execute("SET LOCAL ROLE postgres")
            cur.execute("INSERT INTO friendship (user_low_id, user_high_id, source) "
                        "VALUES (%s, %s, 'INVITE_CODE') ON CONFLICT DO NOTHING",
                        (min(A, B), max(A, B)))
            cur.execute("UPDATE vote_received SET reveal_status='PARTIAL' WHERE id=%s",
                        (ctx["received"],))
            cur.execute("INSERT INTO heart_transaction (user_id, type_code, delta, balance_after) "
                        "VALUES (%s,'SIGNUP_GRANT',300,300)", (A,))

            positive = [
                ("본인 계정 조회",          A_AUTH, "SELECT 1 FROM app_user", (), 1),
                ("본인 하트 내역 조회",     A_AUTH, "SELECT 1 FROM heart_transaction", (), None),
                ("학교 목록 조회(온보딩)",  A_AUTH, "SELECT 1 FROM school", (), None),
                ("질문 목록 조회(투표)",    A_AUTH, "SELECT 1 FROM question", (), None),
                ("친구 프로필 조회",        A_AUTH, "SELECT 1 FROM friend_profile", (), 2),
                ("초대코드로 친구 찾기",    A_AUTH, "SELECT 1 FROM find_by_invite_code('TESTBB')", (), 1),
                ("내가 받은 투표 조회",     B_AUTH, "SELECT 1 FROM my_vote_received", (), None),
            ]
            for desc, who, sql, params, expect in positive:
                cur.execute("SAVEPOINT sp")
                try:
                    as_user(cur, who)
                    cur.execute(sql, params)
                    got = len(cur.fetchall())
                    ok = got > 0 if expect is None else got == expect
                except Exception as e:
                    got, ok = type(e).__name__, False
                finally:
                    cur.execute("ROLLBACK TO SAVEPOINT sp")
                    cur.execute("SET LOCAL ROLE postgres")
                print(f"  {'동작함' if ok else '막힘!!'} {desc}  ({got}행)")
                if not ok:
                    failures.append(f"[정상동작] {desc}")

            # 힌트를 하나 사면 그 값만 열리고 voter_id 는 닫혀 있어야 한다.
            cur.execute("SAVEPOINT sp")
            rpc(cur, B_AUTH, "SELECT buy_hint(%s,'GENDER')", (ctx["received"],))
            as_user(cur, B_AUTH)
            cur.execute("SELECT voter_id, voter_gender FROM my_vote_received")
            row = cur.fetchone()
            cur.execute("ROLLBACK TO SAVEPOINT sp")
            cur.execute("SET LOCAL ROLE postgres")
            ok = bool(row) and row[0] is None and row[1] is not None
            print(f"  {'동작함' if ok else '실패!!'} 성별만 사면 성별만 열림 "
                  f"(voter_id={row[0] if row else '?'}, 성별={row[1] if row else '?'})")
            if not ok:
                failures.append("[정상동작] 선택형 힌트 노출 범위")

        if args.keep:
            conn.commit()
            print("\n시험 데이터를 남겨둡니다 (--keep)")
        else:
            conn.rollback()

    print()
    print("=" * 62)
    if failures:
        print(f"실패 {len(failures)}건 — 다음 단계로 넘어가면 안 됩니다")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("전 항목 통과 — 남의 데이터에 접근할 수 없습니다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
