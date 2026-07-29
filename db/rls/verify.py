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
                ("A 가 운영자 명단을 조회",
                 A_AUTH, "SELECT 1 FROM admin_user", (), 0),
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

                # --- 스코프 하향 -------------------------------------------
                # 같은 반 친구를 다른 반으로 옮기면 CLASS 후보가 모자라진다.
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
                           count(*) FILTER (WHERE q.scope='CLASS' AND v.candidate_scope='CLASS')
                      FROM vote_item v JOIN question q ON q.id = v.question_id
                     WHERE v.session_id = %s
                """, (session2,))
                class_items, still_class = cur.fetchone()
                vcheck("후보가 모자란 CLASS 질문은 스코프가 낮아짐",
                       still_class == 0, f"CLASS 질문 {class_items}개 중 그대로인 것 {still_class}개")

                # 친구가 전부 사라지면 GLOBAL 에서도 4명을 못 채운다 → 세션이 열리지 않는다
                cur.execute("UPDATE app_user SET status='WITHDRAWN' WHERE id = ANY(%s)",
                            (friends,))
                cur.execute("UPDATE vote_session SET status='COMPLETED', completed_at=now() "
                            "WHERE id=%s", (session2,))
                vcheck("GLOBAL 에서도 4명이 안 되면 질문을 내지 않음",
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
            print()
            print("받은 투표 시험 (W6)")

            def rcheck(desc: str, ok: bool, detail=""):
                print(f"  {'동작함' if ok else '실패!!'} {desc}  ({detail})")
                if not ok:
                    failures.append(f"[받은투표] {desc}")

            recv = ctx["received"]
            cur.execute("SAVEPOINT received")
            try:
                # 아무것도 사지 않은 상태 — 투표자에 대한 어떤 단서도 없어야 한다
                as_user(cur, B_AUTH)
                cur.execute("SELECT voter_id, voter_nickname, voter_initial, voter_gender, "
                            "voter_class_id, hint_steps, is_read "
                            "FROM my_vote_received WHERE id=%s", (recv,))
                row = cur.fetchone()
                cur.execute("SET LOCAL ROLE postgres")
                rcheck("사기 전에는 투표자 단서가 하나도 없음",
                       row is not None and all(x is None for x in row[:5]) and row[5] == 0,
                       str(row))

                rpc(cur, B_AUTH, "SELECT mark_received_read(%s)", (recv,))
                cur.execute("SELECT is_read, read_at IS NOT NULL FROM vote_received WHERE id=%s",
                            (recv,))
                rcheck("읽음 처리", cur.fetchone() == (True, True))

                cur.execute("SELECT heart_balance FROM app_user WHERE id=%s", (B,))
                start_balance = cur.fetchone()[0]

                # 1단계 — 초성
                step = rpc(cur, B_AUTH, "SELECT buy_hint(%s)", (recv,))
                as_user(cur, B_AUTH)
                cur.execute("SELECT voter_initial, voter_gender, voter_class_id, voter_id "
                            "FROM my_vote_received WHERE id=%s", (recv,))
                initial, gender, cls, vid = cur.fetchone()
                cur.execute("SET LOCAL ROLE postgres")
                rcheck("1단계: 초성만 열림",
                       step == 1 and initial is not None
                       and gender is None and cls is None and vid is None,
                       f"초성={initial!r}")

                cur.execute("SELECT heart_balance FROM app_user WHERE id=%s", (B,))
                rcheck("하트가 200 차감됨",
                       cur.fetchone()[0] == start_balance - 200, "200")

                cur.execute("""
                    SELECT count(*) FROM hint_purchase p
                     WHERE p.vote_received_id = %s
                       AND NOT EXISTS (SELECT 1 FROM heart_transaction t
                                        WHERE t.hint_purchase_id = p.id)
                """, (recv,))
                rcheck("힌트 구매마다 원장이 남음", cur.fetchone()[0] == 0, "원장 없는 구매 0건")

                # 2단계 — 성별
                rpc(cur, B_AUTH, "SELECT buy_hint(%s)", (recv,))
                as_user(cur, B_AUTH)
                cur.execute("SELECT voter_gender, voter_class_id, voter_id "
                            "FROM my_vote_received WHERE id=%s", (recv,))
                gender, cls, vid = cur.fetchone()
                cur.execute("SET LOCAL ROLE postgres")
                rcheck("2단계: 성별까지 열림",
                       gender == "F" and cls is None and vid is None, f"성별={gender}")

                # 3단계 — 반
                rpc(cur, B_AUTH, "SELECT buy_hint(%s)", (recv,))
                as_user(cur, B_AUTH)
                cur.execute("SELECT voter_class_id, voter_id FROM my_vote_received WHERE id=%s",
                            (recv,))
                cls, vid = cur.fetchone()
                cur.execute("SET LOCAL ROLE postgres")
                rcheck("3단계: 반까지 열리지만 투표자는 아직 비공개",
                       cls is not None and vid is None, f"반={cls}")

                # 4단계 — 전체 공개
                step = rpc(cur, B_AUTH, "SELECT buy_hint(%s)", (recv,))
                as_user(cur, B_AUTH)
                cur.execute("SELECT voter_id, voter_nickname, reveal_status "
                            "FROM my_vote_received WHERE id=%s", (recv,))
                vid, nick, reveal = cur.fetchone()
                cur.execute("SET LOCAL ROLE postgres")
                rcheck("4단계: 투표자가 공개됨",
                       step == 4 and vid == A and nick == "시험유저A" and reveal == "REVEALED",
                       f"{nick}")

                cur.execute("SELECT heart_balance FROM app_user WHERE id=%s", (B,))
                rcheck("누진 요금 합계 2000 차감",
                       cur.fetchone()[0] == start_balance - 2000, "200+300+500+1000")

                rcheck("더 살 힌트가 없으면 막힘",
                       expect_error(cur, B_AUTH, "SELECT buy_hint(%s)", (recv,)), "예외 기대")

                # 남의 받은 투표는 건드릴 수 없다
                rcheck("남이 받은 투표에는 힌트를 못 삼",
                       expect_error(cur, A_AUTH, "SELECT buy_hint(%s)", (recv,)), "예외 기대")

                cur.execute("ROLLBACK TO SAVEPOINT received")

                # 하트가 모자라면 구매가 막힌다
                cur.execute("UPDATE app_user SET heart_balance = 100 WHERE id=%s", (B,))
                rcheck("하트가 모자라면 구매가 막힘",
                       expect_error(cur, B_AUTH, "SELECT buy_hint(%s)", (recv,)),
                       "보유 100 < 200")
                cur.execute("SELECT count(*) FROM hint_purchase WHERE vote_received_id=%s", (recv,))
                rcheck("막힌 구매는 흔적을 남기지 않음", cur.fetchone()[0] == 0, "0건")

                # 답변 공개
                rpc(cur, B_AUTH, "SELECT set_answer_status(%s,'PUBLIC')", (recv,))
                cur.execute("SELECT answer_status, answered_at IS NOT NULL "
                            "FROM vote_received WHERE id=%s", (recv,))
                rcheck("답변 공개 상태가 기록됨", cur.fetchone() == ("PUBLIC", True))
            except Exception as e:
                print(f"  실패!! 받은 투표 RPC  ({type(e).__name__}: {e})")
                failures.append("[받은투표] RPC 호출 실패")
            finally:
                cur.execute("ROLLBACK TO SAVEPOINT received")
                cur.execute("SET LOCAL ROLE postgres")

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

            # 부분공개일 때 초성은 보이고 투표자 id 는 안 보여야 한다
            cur.execute("SAVEPOINT sp")
            as_user(cur, B_AUTH)
            cur.execute("SELECT voter_id, voter_initial FROM my_vote_received")
            row = cur.fetchone()
            cur.execute("ROLLBACK TO SAVEPOINT sp")
            cur.execute("SET LOCAL ROLE postgres")
            ok = bool(row) and row[0] is None and row[1] is not None
            shown_id = row[0] if row else "?"
            shown_initial = repr(row[1]) if row else "?"
            print(f"  {'동작함' if ok else '실패!!'} 부분공개는 초성만 노출 "
                  f"(voter_id={shown_id}, 초성={shown_initial})")
            if not ok:
                failures.append("[정상동작] 부분공개 힌트")

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
