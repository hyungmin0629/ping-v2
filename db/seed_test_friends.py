"""
혼자서 투표를 시험하기 위한 더미 친구를 만든다. (W5)

왜 필요한가:
    투표가 열리려면 친구가 5명이어야 하고, 질문 하나마다 후보가 4명 뽑힌다.
    스코프가 CLASS / SCHOOL / GLOBAL 세 가지라 같은 반에도 4명이 필요하다.
    브라우저 창을 다섯 개 띄워 계정을 만들 수는 없으므로 DB에 직접 넣는다.

어떻게 만드나:
    - 로그인 계정(auth.users)은 만들지 않는다. app_user.auth_user_id 가
      nullable 이라 프로필 행만으로 충분하다. 더미로 로그인할 일은 없다
      — 친구 맺기 흐름 자체는 시크릿 창으로 진짜 계정끼리 시험한다(W4에서 했다).
    - is_synthetic = true 로 찍는다. Supabase 는 원래 실유저 전용이고,
      이건 그 원칙의 의도적 예외다. 플래그가 있어야 나중에 걸러낼 수 있다.
    - 하트는 0으로 둔다. 원장도 비어 있으므로 잔액=원장이 유지된다.
    - 친구 관계는 friendship 에 직접 넣고 refresh_friend_state 로
      친구 수와 게이트를 다시 계산한다(RPC 를 우회하므로 저절로 맞지 않는다).

⚠️ 클로즈드 테스트를 시작하기 전에 반드시 --clean 으로 지운다.
   남겨두면 실유저가 존재하지 않는 사람에게 투표하게 되고,
   그 사람은 받은 투표를 영영 열어볼 수 없다.

더미가 나를 뽑은 기록도 만들 수 있다(--votes). 더미는 로그인할 수 없어서
스스로 투표하지 못하는데, "받은 투표" 화면(W6)을 보려면 누군가 나를 뽑아야 한다.
힌트 누진 요금은 한 건에 여러 단계를 사야 확인되므로 몇 건은 있어야 한다.

사용법:
    python db/seed_test_friends.py --for 6RSH96F8        # 내 초대 코드
    python db/seed_test_friends.py --for 6RSH96F8 --same-class 5 --other-class 3
    python db/seed_test_friends.py --for 6RSH96F8 --votes 6   # 나를 뽑은 기록 6건
    python db/seed_test_friends.py --clean               # 더미 전부 삭제
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import psycopg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent

# ck_invite_code 와 같은 문자 집합 (헷갈리는 0·O·1·I·L 제외)
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

# 더미가 남길 수 있는 흔적을 지운다.
#
# 삭제 순서를 짜다 세 번 걸렸다. 셋 다 같은 뿌리에서 나왔다 — 지울 대상을
# 단계마다 다시 계산하면, 앞 단계가 지운 행 때문에 뒤 단계의 계산 결과가 달라진다.
#   1. 힌트를 산 것은 나(실유저)라 heart_transaction 이 남고 hint_purchase 삭제가 막혔다
#   2. 더미가 후보인 문항을 지우려는데 vote_received 가 붙잡았다
#   3. 후보를 먼저 지우자 "더미가 후보인 문항"이 조회되지 않아 문항 90개가 고아로 남았다
#
# 그래서 지울 대상을 **임시 테이블에 먼저 고정**하고, 모든 단계가 그것만 본다.
SYN = "(SELECT id FROM app_user WHERE is_synthetic)"

# 지울 문항: 더미가 투표했거나, 더미가 후보로 들어갔거나, 이미 부서진 것.
# 부서진 것까지 넣는 이유는 예전 실행이 남긴 고아 문항을 여기서 함께 정리하기 위해서다.
DOOMED_ITEMS = f"""
    SELECT v.id FROM vote_item v
     WHERE v.user_id IN {SYN}
        OR EXISTS (SELECT 1 FROM vote_candidate c
                    WHERE c.vote_item_id = v.id AND c.candidate_user_id IN {SYN})
        OR (SELECT count(*) FROM vote_candidate c
             WHERE c.vote_item_id = v.id AND c.shuffle_round = 0) < 4
        OR (v.voted_at IS NOT NULL
            AND NOT EXISTS (SELECT 1 FROM vote_candidate c
                             WHERE c.vote_item_id = v.id AND c.is_chosen))"""

DOOMED_RECV = f"""
    SELECT r.id FROM vote_received r
     WHERE r.voter_id IN {SYN}
        OR r.receiver_id IN {SYN}
        OR r.vote_item_id IN (SELECT id FROM doomed_items)"""

DOOMED_HINTS = f"""
    SELECT p.id FROM hint_purchase p
     WHERE p.user_id IN {SYN}
        OR p.vote_received_id IN (SELECT id FROM doomed_recv)"""

CLEAN_STEPS = [
    ("heart_transaction", f"""
        DELETE FROM heart_transaction
         WHERE user_id IN {SYN}
            OR vote_item_id IN (SELECT id FROM doomed_items)
            OR hint_purchase_id IN (SELECT id FROM doomed_hints)"""),
    ("hint_purchase",  "DELETE FROM hint_purchase WHERE id IN (SELECT id FROM doomed_hints)"),
    ("vote_received",  "DELETE FROM vote_received WHERE id IN (SELECT id FROM doomed_recv)"),
    ("vote_shuffle",   "DELETE FROM vote_shuffle WHERE vote_item_id IN (SELECT id FROM doomed_items)"),
    ("vote_candidate", f"""
        DELETE FROM vote_candidate
         WHERE vote_item_id IN (SELECT id FROM doomed_items)
            OR candidate_user_id IN {SYN}"""),
    ("vote_item",      "DELETE FROM vote_item WHERE id IN (SELECT id FROM doomed_items)"),
    ("vote_session", f"""
        DELETE FROM vote_session s
         WHERE s.user_id IN {SYN}
            OR NOT EXISTS (SELECT 1 FROM vote_item v WHERE v.session_id = s.id)"""),
    ("ad_impression", f"DELETE FROM ad_impression WHERE user_id IN {SYN}"),
    ("friendship", f"DELETE FROM friendship WHERE user_low_id IN {SYN} OR user_high_id IN {SYN}"),
    ("friend_request", f"DELETE FROM friend_request WHERE sender_id IN {SYN} OR receiver_id IN {SYN}"),
    ("friend_recommendation", f"""
        DELETE FROM friend_recommendation
         WHERE user_id IN {SYN} OR recommended_user_id IN {SYN}"""),
    ("block_record", f"DELETE FROM block_record WHERE user_id IN {SYN} OR blocked_user_id IN {SYN}"),
    ("user_session", f"DELETE FROM user_session WHERE user_id IN {SYN}"),
    ("school_notice_read", f"DELETE FROM school_notice_read WHERE user_id IN {SYN}"),
    ("app_user", "DELETE FROM app_user WHERE is_synthetic"),
]

# 원장에서 행을 빼면 잔액과 누적합이 어긋난다. 지운 뒤 남은 기록만으로 다시 맞춘다.
# 실서비스에서는 원장을 지우지 않는다 — 이건 시험 데이터를 되감는 도구다.
REPAIR_STEPS = [
    ("원장 누적합 재계산", """
        WITH running AS (
            SELECT id, sum(delta) OVER (PARTITION BY user_id ORDER BY id, created_at) AS bal
              FROM heart_transaction)
        UPDATE heart_transaction t SET balance_after = r.bal
          FROM running r WHERE r.id = t.id AND t.balance_after <> r.bal"""),
    ("잔액 재계산", """
        UPDATE app_user u
           SET heart_balance = coalesce((SELECT sum(t.delta) FROM heart_transaction t
                                          WHERE t.user_id = u.id), 0),
               updated_at = now()
         WHERE u.heart_balance <> coalesce((SELECT sum(t.delta) FROM heart_transaction t
                                             WHERE t.user_id = u.id), 0)"""),
    # 게이트는 한 번 열리면 유지하는 것이 서비스 규칙이지만(refresh_friend_state),
    # 여기서는 친구를 인위적으로 걷어낸 것이라 상태를 되감는 쪽이 맞다.
    ("게이트 되감기", """
        UPDATE app_user SET service_unlocked_at = NULL
         WHERE service_unlocked_at IS NOT NULL AND friend_count < 5"""),
]


def make_codes(cur, count: int) -> list[str]:
    """이미 쓰이는 코드를 피해 새 초대 코드를 만든다."""
    cur.execute("SELECT invite_code FROM app_user")
    taken = {r[0] for r in cur.fetchall()}
    rng = random.Random()
    codes: list[str] = []
    while len(codes) < count:
        code = "".join(rng.choice(CODE_ALPHABET) for _ in range(8))
        if code not in taken:
            taken.add(code)
            codes.append(code)
    return codes


def clean(cur) -> int:
    cur.execute("SELECT count(*) FROM app_user WHERE is_synthetic")
    before = cur.fetchone()[0]
    if before == 0:
        print("지울 더미가 없습니다.")
        return 0

    # 지울 대상을 먼저 고정한다. 삭제가 진행되면 조건이 달라지기 때문이다.
    cur.execute(f"CREATE TEMP TABLE doomed_items ON COMMIT DROP AS {DOOMED_ITEMS}")
    cur.execute(f"CREATE TEMP TABLE doomed_recv  ON COMMIT DROP AS {DOOMED_RECV}")
    cur.execute(f"CREATE TEMP TABLE doomed_hints ON COMMIT DROP AS {DOOMED_HINTS}")

    for name, sql in CLEAN_STEPS:
        cur.execute(sql)
        if cur.rowcount:
            print(f"  {name}: {cur.rowcount}행 삭제")

    # 친구가 줄었으므로 남은 실유저의 친구 수를 다시 센다.
    cur.execute("SELECT id FROM app_user")
    for (uid,) in cur.fetchall():
        cur.execute("SELECT refresh_friend_state(%s)", (uid,))

    for name, sql in REPAIR_STEPS:
        cur.execute(sql)
        if cur.rowcount:
            print(f"  {name}: {cur.rowcount}행")

    print(f"\n더미 {before}명을 지웠습니다.")
    return before


def seed(cur, invite_code: str, same_class: int, other_class: int) -> int:
    cur.execute(
        "SELECT u.id, u.nickname, u.class_id, g.school_id "
        "  FROM app_user u JOIN grade_class g ON g.id = u.class_id "
        " WHERE u.invite_code = %s", (invite_code.upper(),))
    row = cur.fetchone()
    if row is None:
        sys.exit(f"초대 코드 {invite_code} 인 계정이 없습니다. 앱 화면의 코드를 확인하세요.")
    me, my_nick, my_class, my_school = row

    cur.execute("SELECT id FROM grade_class WHERE school_id = %s AND id <> %s ORDER BY id",
                (my_school, my_class))
    other_classes = [r[0] for r in cur.fetchall()]
    if not other_classes and other_class > 0:
        print("⚠️ 같은 학교에 다른 반이 없습니다. 전부 같은 반에 만듭니다.")
        same_class, other_class = same_class + other_class, 0

    # 같은 반 → CLASS 스코프 후보. 다른 반 → SCHOOL·GLOBAL 스코프에서만 후보.
    placements = [my_class] * same_class
    placements += [other_classes[i % len(other_classes)] for i in range(other_class)]

    codes = make_codes(cur, len(placements))
    # 성별은 온보딩 필수 항목이고 힌트로 파는 정보다. 비워두면 GENDER 힌트를
    # 산 사람에게 빈 값이 나간다.
    genders = random.Random().choices(["F", "M", "X"], weights=[45, 45, 10],
                                      k=len(placements))
    cur.execute("SELECT coalesce(max(id), 0) FROM app_user WHERE is_synthetic")
    start = cur.fetchone()[0]

    made = 0
    for i, (class_id, code, gender) in enumerate(zip(placements, codes, genders), start=1):
        cur.execute(
            "INSERT INTO app_user (nickname, invite_code, class_id, gender, is_synthetic) "
            "VALUES (%s, %s, %s, %s, true) RETURNING id",
            (f"시험친구{i:02d}", code, class_id, gender))
        friend_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO friendship (user_low_id, user_high_id, source) "
            "VALUES (LEAST(%s,%s), GREATEST(%s,%s), 'INVITE_CODE') "
            "ON CONFLICT DO NOTHING", (me, friend_id, me, friend_id))
        cur.execute("SELECT refresh_friend_state(%s)", (friend_id,))
        made += 1

    cur.execute("SELECT refresh_friend_state(%s)", (me,))
    cur.execute("SELECT friend_count, service_unlocked_at FROM app_user WHERE id = %s", (me,))
    count, unlocked = cur.fetchone()

    print(f"{my_nick} 님에게 더미 친구 {made}명을 붙였습니다.")
    print(f"  같은 반 {same_class}명 (CLASS 스코프 후보)")
    print(f"  다른 반 {other_class}명 (SCHOOL·GLOBAL 스코프에서만 후보)")
    print(f"\n친구 {count}명 · 투표 {'열림' if unlocked else '잠김'}")
    if start:
        print("\n⚠️ 이전에 만든 더미가 남아 있었습니다. 겹쳐서 만들었습니다.")
    return made


def fill_missing_genders(cur) -> None:
    """성별을 받기 전에 만든 더미를 채운다.

    성별은 힌트 2단계로 파는 정보다. 비어 있으면 하트를 받고 빈 값을 넘기게 된다.
    """
    cur.execute("""
        UPDATE app_user
           SET gender = (ARRAY['F','M','X']::gender_type[])[1 + floor(random()*3)::int]
         WHERE is_synthetic AND gender IS NULL
    """)
    if cur.rowcount:
        print(f"  성별이 비어 있던 더미 {cur.rowcount}명을 채웠습니다.")


def seed_votes(cur, invite_code: str, count: int) -> int:
    """더미들이 나를 뽑은 기록을 만든다.

    후보 규칙은 앱과 똑같이 DB 함수(pick_candidates)로 뽑는다. 손으로 넣으면
    "후보는 투표자의 친구여야 한다" 같은 정합성 규칙을 어기기 쉽다.

    CLASS 스코프 질문은 쓰지 않는다. 다른 반 더미가 CLASS 질문으로 나를 뽑으면
    'CLASS 스코프에 타반 후보' 정합성 검사에 걸린다.
    """
    cur.execute("SELECT id FROM app_user WHERE invite_code = %s", (invite_code.upper(),))
    row = cur.fetchone()
    if row is None:
        sys.exit(f"초대 코드 {invite_code} 인 계정이 없습니다.")
    me = row[0]

    fill_missing_genders(cur)

    cur.execute("SELECT id FROM app_user WHERE is_synthetic ORDER BY id")
    dummies = [r[0] for r in cur.fetchall()]
    if len(dummies) < 4:
        sys.exit("더미가 4명 미만입니다. 먼저 --for 로 친구를 만들어 주세요.")

    # 더미끼리도 친구로 묶는다. 후보는 투표자의 친구 중에서만 나오는데,
    # 더미의 친구가 나 하나뿐이면 4명을 채울 수 없다.
    for i, a in enumerate(dummies):
        for b in dummies[i + 1:]:
            cur.execute("INSERT INTO friendship (user_low_id,user_high_id,source) "
                        "VALUES (LEAST(%s,%s),GREATEST(%s,%s),'INVITE_CODE') "
                        "ON CONFLICT DO NOTHING", (a, b, a, b))
    for d in dummies:
        cur.execute("SELECT refresh_friend_state(%s)", (d,))

    cur.execute("SELECT id, scope FROM question "
                "WHERE status='ACTIVE' AND scope <> 'CLASS' ORDER BY random() LIMIT %s",
                (count,))
    questions = cur.fetchall()
    if not questions:
        sys.exit("ACTIVE 질문이 없습니다. db/seed_questions.sql 을 먼저 적용하세요.")

    rng = random.Random()
    made = 0
    for i, (qid, scope) in enumerate(questions):
        voter = dummies[i % len(dummies)]

        cur.execute("SELECT public.effective_scope(%s, %s)", (voter, scope))
        eff = cur.fetchone()[0]
        if eff is None:
            continue

        cur.execute("SELECT candidate_user_id FROM public.pick_candidates(%s, %s)", (voter, eff))
        picks = [r[0] for r in cur.fetchall()]
        if len(picks) < 4:
            continue
        # 나를 반드시 후보에 넣는다 — 나를 뽑은 기록을 만드는 것이 목적이다
        if me not in picks:
            picks[-1] = me

        cur.execute("INSERT INTO vote_session (user_id, item_count, status, completed_at) "
                    "VALUES (%s, 1, 'COMPLETED', now()) RETURNING id", (voter,))
        session = cur.fetchone()[0]
        cur.execute("INSERT INTO vote_item "
                    "(session_id,user_id,question_id,candidate_scope,position,voted_at) "
                    "VALUES (%s,%s,%s,%s,1,now()) RETURNING id", (session, voter, qid, eff))
        item = cur.fetchone()[0]

        rng.shuffle(picks)
        for slot, uid in enumerate(picks, start=1):
            cur.execute("INSERT INTO vote_candidate "
                        "(vote_item_id,candidate_user_id,shuffle_round,slot,is_chosen) "
                        "VALUES (%s,%s,0,%s,%s)", (item, uid, slot, uid == me))

        cur.execute("INSERT INTO vote_received (vote_item_id,voter_id,receiver_id,question_id) "
                    "VALUES (%s,%s,%s,%s)", (item, voter, me, qid))

        # 하트는 앱과 같은 함수로 준다. 잔액과 원장이 함께 움직여야 한다.
        cur.execute("SELECT public.grant_hearts(%s,%s,'VOTE_REWARD',%s)",
                    (voter, rng.randint(5, 15), item))
        cur.execute("SELECT public.grant_hearts(%s,%s,'VOTE_REWARD',%s)",
                    (me, rng.randint(5, 15), item))
        made += 1

    cur.execute("SELECT heart_balance FROM app_user WHERE id=%s", (me,))
    print(f"나를 뽑은 기록 {made}건을 만들었습니다. (하트 {cur.fetchone()[0]}개)")
    if made < count:
        print(f"⚠️ {count - made}건은 후보가 모자라 건너뛰었습니다.")
    return made


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--for", dest="invite_code", help="더미를 붙일 계정의 초대 코드")
    ap.add_argument("--same-class", type=int, default=5,
                    help="같은 반에 만들 수 (CLASS 스코프에 4명 이상 필요)")
    ap.add_argument("--other-class", type=int, default=3, help="다른 반에 만들 수")
    ap.add_argument("--votes", type=int, default=0,
                    help="더미가 나를 뽑은 기록을 이만큼 만든다 (W6 시험용)")
    ap.add_argument("--clean", action="store_true", help="더미를 전부 지운다")
    args = ap.parse_args()

    if not args.clean and not args.invite_code:
        ap.error("--for 초대코드 또는 --clean 중 하나가 필요합니다")

    url = dotenv_values(ROOT / ".env")["SUPABASE_DB_URL"].strip()
    with psycopg.connect(url, connect_timeout=30) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            if args.clean:
                clean(cur)
            elif args.votes:
                seed_votes(cur, args.invite_code, args.votes)
            else:
                seed(cur, args.invite_code, args.same_class, args.other_class)
        conn.commit()

    return 0


if __name__ == "__main__":
    sys.exit(main())
