---
title: DB 를 처음부터 다시 만들기
group: 운영
tags: [운영, 참조]
---

# DB 를 처음부터 다시 만들기

> `CLAUDE.md` 에서 뺀 참조 문서다. 요약과 경고는 거기 남아 있고,
> 여기에는 **실제로 그 작업을 할 때 필요한 값과 절차**가 있다.


`db/rls/` 의 SQL 은 **순서가 있다.** 뒤의 파일이 앞의 정책을 갈아끼우기 때문이다.

```
python db/apply.py --target supabase          # DDL + migrations
python db/run_sql.py db/rls/policies.sql      # 기본 RLS
python db/run_sql.py db/rls/onboarding.sql    # 가입 RPC (insert_own_user 를 대체)
python db/run_sql.py db/rls/friends.sql       # 친구 RPC (친구요청 정책을 대체)
python db/run_sql.py db/rls/voting.sql        # 투표 RPC
python db/run_sql.py db/rls/received.sql      # 힌트·받은 투표 뷰
python db/run_sql.py db/rls/session_log.sql   # 접속 로그 (insert_own_session 을 대체)
python db/run_sql.py db/rls/school_picker.sql # selectable_school 뷰
python db/run_sql.py db/rls/school_info.sql   # 급식·학사일정 정책 + my_school_source 뷰
python db/run_sql.py db/rls/board.sql         # 자유게시판 뷰 + RPC
python db/run_sql.py db/rls/recommend.sql     # 친구 추천 뷰 + RPC
python db/run_sql.py db/rls/profile.sql       # 프로필 수정 RPC (직접 UPDATE 를 회수)
python db/run_sql.py db/rls/withdraw.sql      # 계정 삭제 RPC
python db/run_sql.py db/rls/topup.sql         # 하트 충전 RPC (스텁)
python db/run_sql.py db/rls/hangul.sql        # 한글 자모 분해·조합
python db/run_sql.py db/rls/hints.sql         # 선택형 힌트 (received.sql 의 buy_hint 를 대체)
python db/run_sql.py db/rls/replies.sql       # 1회성 답장 + 신고 (my_vote_history 를 갈아끼운다)
python db/run_sql.py db/seed_org.sql          # 테스트 조직
python db/run_sql.py db/seed_questions.sql    # 질문 24개
python db/rls/verify.py                       # 통과해야 끝
```

---

[[CLAUDE|CLAUDE.md]] 로 돌아가기
