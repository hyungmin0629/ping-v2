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

사용법:
    python db/seed_test_friends.py --for 6RSH96F8        # 내 초대 코드
    python db/seed_test_friends.py --for 6RSH96F8 --same-class 5 --other-class 3
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

# 더미가 남길 수 있는 흔적을 자식 → 부모 순으로 지운다.
# 더미는 투표하지 않지만, 내가 더미를 후보로 뽑은 기록은 남는다.
CLEAN_STEPS = [
    ("heart_transaction", """
        DELETE FROM heart_transaction
         WHERE user_id IN (SELECT id FROM app_user WHERE is_synthetic)
            OR vote_item_id IN (SELECT vote_item_id FROM vote_candidate
                                 WHERE candidate_user_id IN
                                       (SELECT id FROM app_user WHERE is_synthetic))"""),
    ("hint_purchase", """
        DELETE FROM hint_purchase
         WHERE user_id IN (SELECT id FROM app_user WHERE is_synthetic)
            OR vote_received_id IN (SELECT id FROM vote_received
                                     WHERE receiver_id IN (SELECT id FROM app_user WHERE is_synthetic)
                                        OR voter_id IN (SELECT id FROM app_user WHERE is_synthetic))"""),
    ("vote_received", """
        DELETE FROM vote_received
         WHERE voter_id IN (SELECT id FROM app_user WHERE is_synthetic)
            OR receiver_id IN (SELECT id FROM app_user WHERE is_synthetic)"""),
    ("vote_shuffle", """
        DELETE FROM vote_shuffle
         WHERE vote_item_id IN (SELECT vote_item_id FROM vote_candidate
                                 WHERE candidate_user_id IN
                                       (SELECT id FROM app_user WHERE is_synthetic))"""),
    ("vote_candidate", """
        DELETE FROM vote_candidate
         WHERE candidate_user_id IN (SELECT id FROM app_user WHERE is_synthetic)
            OR vote_item_id IN (SELECT vote_item_id FROM vote_candidate
                                 WHERE candidate_user_id IN
                                       (SELECT id FROM app_user WHERE is_synthetic))"""),
    # 후보가 사라져 4명이 되지 않는 아이템은 통째로 지운다. 반쪽짜리 투표
    # 기록을 남기면 정합성 검사가 그걸 결함으로 잡는다.
    ("vote_item", """
        DELETE FROM vote_item v
         WHERE v.user_id IN (SELECT id FROM app_user WHERE is_synthetic)
            OR (SELECT count(*) FROM vote_candidate c
                 WHERE c.vote_item_id = v.id AND c.shuffle_round = 0) < 4"""),
    ("vote_session", """
        DELETE FROM vote_session s
         WHERE s.user_id IN (SELECT id FROM app_user WHERE is_synthetic)
            OR NOT EXISTS (SELECT 1 FROM vote_item v WHERE v.session_id = s.id)"""),
    ("ad_impression", """
        DELETE FROM ad_impression
         WHERE user_id IN (SELECT id FROM app_user WHERE is_synthetic)"""),
    ("friendship", """
        DELETE FROM friendship
         WHERE user_low_id IN (SELECT id FROM app_user WHERE is_synthetic)
            OR user_high_id IN (SELECT id FROM app_user WHERE is_synthetic)"""),
    ("friend_request", """
        DELETE FROM friend_request
         WHERE sender_id IN (SELECT id FROM app_user WHERE is_synthetic)
            OR receiver_id IN (SELECT id FROM app_user WHERE is_synthetic)"""),
    ("friend_recommendation", """
        DELETE FROM friend_recommendation
         WHERE user_id IN (SELECT id FROM app_user WHERE is_synthetic)
            OR recommended_user_id IN (SELECT id FROM app_user WHERE is_synthetic)"""),
    ("block_record", """
        DELETE FROM block_record
         WHERE user_id IN (SELECT id FROM app_user WHERE is_synthetic)
            OR blocked_user_id IN (SELECT id FROM app_user WHERE is_synthetic)"""),
    ("user_session", """
        DELETE FROM user_session
         WHERE user_id IN (SELECT id FROM app_user WHERE is_synthetic)"""),
    ("school_notice_read", """
        DELETE FROM school_notice_read
         WHERE user_id IN (SELECT id FROM app_user WHERE is_synthetic)"""),
    ("app_user", "DELETE FROM app_user WHERE is_synthetic"),
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

    for name, sql in CLEAN_STEPS:
        cur.execute(sql)
        if cur.rowcount:
            print(f"  {name}: {cur.rowcount}행 삭제")

    # 친구가 줄었으므로 남은 실유저의 친구 수를 다시 센다.
    cur.execute("SELECT id FROM app_user")
    for (uid,) in cur.fetchall():
        cur.execute("SELECT refresh_friend_state(%s)", (uid,))

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
    cur.execute("SELECT coalesce(max(id), 0) FROM app_user WHERE is_synthetic")
    start = cur.fetchone()[0]

    made = 0
    for i, (class_id, code) in enumerate(zip(placements, codes), start=1):
        cur.execute(
            "INSERT INTO app_user (nickname, invite_code, class_id, is_synthetic) "
            "VALUES (%s, %s, %s, true) RETURNING id",
            (f"시험친구{i:02d}", code, class_id))
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
            else:
                seed(cur, args.invite_code, args.same_class, args.other_class)
        conn.commit()

    return 0


if __name__ == "__main__":
    sys.exit(main())
