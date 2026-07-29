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
    for label, auth_id, nick, code in [("A", A_AUTH, "시험유저A", "TESTAA"),
                                       ("B", B_AUTH, "시험유저B", "TESTBB")]:
        cur.execute(
            "INSERT INTO app_user (auth_user_id, nickname, invite_code, class_id, heart_balance) "
            "VALUES (%s, %s, %s, %s, 5000) RETURNING id",
            (auth_id, nick, code, cid))
        ids[label] = cur.fetchone()[0]

    for n, (auth_id, nick, code) in enumerate(D_USERS, start=1):
        cur.execute(
            "INSERT INTO app_user (auth_user_id, nickname, invite_code, class_id) "
            "VALUES (%s, %s, %s, %s) RETURNING id", (auth_id, nick, code, cid))
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
                            "FROM complete_onboarding('새로온사람', %s)", (cid,))
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
                cur.execute("SELECT id FROM complete_onboarding('다른이름', %s)", (cid,))
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
