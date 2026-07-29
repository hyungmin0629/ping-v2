"""
Supabase 의 유저 데이터를 비운다. (조직·질문 같은 마스터 데이터는 남긴다)

언제 쓰나:
    테스트하다 쌓인 익명 계정과 프로필을 치우고 깨끗한 상태에서 다시 시작할 때.
    브라우저의 세션도 함께 지워야 완전히 초기화된다(아래 안내 참고).

지우는 것:
    app_user 와 거기 딸린 모든 활동 기록, 그리고 auth.users 의 익명 계정.

남기는 것:
    region / school / grade_class / question / 각종 마스터 테이블.

⚠️ Supabase 전용이다. 로컬 합성 데이터는 건드리지 않는다.

사용법:
    python db/reset_users.py            # 확인 후 삭제
    python db/reset_users.py --yes      # 묻지 않고 삭제
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent

# 자식 → 부모 순서. FK 때문에 이 순서로 지워야 한다.
USER_DATA_TABLES = [
    "heart_transaction",
    "hint_purchase",
    "heart_purchase",
    "vote_shuffle",
    "vote_candidate",
    "vote_received",
    "vote_item",
    "vote_session",
    "ad_impression",
    "comment_like",
    "post_like",
    "post_comment",
    "post",
    "report",
    "sanction",
    "school_notice_read",
    "friend_recommendation",
    "friendship",
    "friend_request",
    "block_record",
    "user_withdrawal",
    "user_session",
    "question_request",
    "app_user",
]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    url = dotenv_values(ROOT / ".env")["SUPABASE_DB_URL"].strip()

    with psycopg.connect(url, connect_timeout=30) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM app_user")
            users = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM auth.users")
            auths = cur.fetchone()[0]

            print(f"현재 상태 — 프로필 {users}개 / 인증계정 {auths}개")
            if users == 0 and auths == 0:
                print("이미 비어 있습니다.")
                return 0

            if not args.yes:
                answer = input("모두 삭제할까요? (yes 입력): ").strip().lower()
                if answer != "yes":
                    print("취소했습니다.")
                    return 1

            for t in USER_DATA_TABLES:
                cur.execute(f"DELETE FROM {t}")

            # 인증 계정도 지운다. app_user.auth_user_id 는 ON DELETE SET NULL 이라
            # 순서에 관계없이 안전하다.
            cur.execute("DELETE FROM auth.users")

            cur.execute("SELECT count(*) FROM app_user")
            left_u = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM auth.users")
            left_a = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM school")
            schools = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM grade_class")
            classes = cur.fetchone()[0]

        conn.commit()

    print(f"\n삭제 완료 — 프로필 {left_u}개 / 인증계정 {left_a}개")
    print(f"보존됨    — 학교 {schools}개 / 학급 {classes}개")
    print("\n브라우저에서도 세션을 지워야 완전히 초기화됩니다:")
    print("  개발자도구(F12) → Application → Storage → Clear site data")
    print("  또는 시크릿 창으로 접속")
    return 0


if __name__ == "__main__":
    sys.exit(main())
