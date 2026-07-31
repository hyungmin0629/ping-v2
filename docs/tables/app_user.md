---
title: app_user
domain: 유저
kind: activity
rows: 23
tags: [테이블, 유저]
---

# app_user · 유저

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**유저** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **23행**

## 왜 이렇게 생겼나

"user" 는 Postgres 예약어라 app_user 로 명명한다. ★ 개인정보를 받지 않는다. 이메일·전화번호·실명·비밀번호 컬럼이 없다. 이건 누락이 아니라 설계다. 유저가 입력하는 것은 nickname 과 소속(class_id) 둘뿐이다. auth_user_id : Supabase 익명 계정(auth.users)의 uuid. 이메일·비번 없이 접속만으로 발급된다. 합성 유저는 NULL이므로 실유저/합성 구분에도 쓰인다. nickname     : 유저가 직접 정하는 별명. 실명이 아니다. invite_code  : 친구 추가의 유일한 수단. 이 코드를 주고받아 관계를 맺는다. 전화번호·이메일을 받지 않으므로 서로를 찾을 다른 방법이 없다. heart_balance: 구 스키마에서 point/heart 로 이원화돼 보이던 것을 하나로 통합. service_unlocked_at: 친구 5명 게이트를 넘긴 시점. 온보딩 퍼널 측정용. last_active_at: 구 스키마에 로그인 기록이 없어 리텐션을 친구요청으로 추정해야 했던 문제를 해소. is_admin     : 운영자 표시. 원래는 admin_user 테이블이 따로 있었으나, 운영 화면을 만들 계획이 없어 플래그 하나로 접었다. 운영 행위의 주체(질문 검수·신고 처리)는 여전히 남는다 — 그 FK 들이 이제 이 테이블을 가리킨다. ★ 이 값을 바꾸는 경로는 앱에 없다. DB 에서 직접 켠다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `auth_user_id` | uuid |  | → auth.users |
| `nickname` | varchar(20) | NOT NULL |  |
| `invite_code` | varchar(8) | NOT NULL |  |
| `gender` | gender_type |  |  |
| `class_id` | bigint | NOT NULL | → grade_class |
| `heart_balance` | bigint | NOT NULL |  |
| `friend_count` | integer | NOT NULL |  |
| `service_unlocked_at` | timestamptz |  |  |
| `status` | user_status | NOT NULL |  |
| `is_synthetic` | boolean | NOT NULL |  |
| `last_active_at` | timestamptz |  |  |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |
| `is_admin` | boolean | NOT NULL |  |

**UNIQUE** — `auth_user_id` · `invite_code`

**이 표를 참조하는 표** — `ad_impression` · `block_record` · `comment_like` · `friend_request` · `friendship` · `heart_purchase` · `heart_transaction` · `hint_purchase` · `post` · `post_comment` · `post_like` · `question` · `question_request` · `rejected_friend_recommendations` · `report` · `sanction` · `school_notice` · `school_notice_read` · `user_session` · `user_withdrawal` · `vote_candidate` · `vote_item` · `vote_received` · `vote_session`

## 얽힌 결정 11개

- [[anonymous-auth-no-pii|개인정보를 일절 받지 않는 익명 인증]]
- [[backfill-updated-at|대량 적재 후 `updated_at` 을 각 행의 원래 시각으로 되돌린다]]
- [[bigquery-source-column|실유저와 합성 데이터를 같은 BigQuery 테이블에 `_source` 로 섞는다]]
- [[client-write-minimal|클라이언트에 쓰기 권한을 거의 주지 않는다]]
- [[drop-admin-user|admin_user 를 없애고 app_user.is_admin 하나로 접는다]]
- [[friend-invite-code-two-step|친구 맺기는 초대 코드로만, 요청·수락 2단계로]]
- [[gender-at-onboarding|성별을 온보딩에서 받는다]]
- [[join-requires-source|두 원천의 id 가 겹친다 — 조인에 `_source` 를 강제한다]]
- [[open-named-board|자유게시판을 연다 — 글도 댓글도 닉네임으로]]
- [[profile-edit-rpc|프로필 수정도 RPC 하나로 — 직접 UPDATE 권한 회수]]
- [[signup-single-rpc|가입은 RPC 하나로만 한다]]

## 이 표를 지키는 정합성 검사 7종

`qa/checks/integrity.sql` · 위반 0이어야 한다.

- 하트 원장 vs 잔액 불일치
- 가입 이전 활동
- 가입 이전 세션
- 게이트 위반(5명을 맺어본 적 없는데 해금)
- CLASS 스코프에 설명 안 되는 타반 후보
- SCHOOL 스코프에 설명 안 되는 타교 후보
- friend_count 불일치

## 이 표를 다루는 정책·RPC

`db/rls/board.sql` · `db/rls/friends.sql` · `db/rls/hints.sql` · `db/rls/onboarding.sql` · `db/rls/policies.sql` · `db/rls/profile.sql` · `db/rls/received.sql` · `db/rls/recommend.sql` · `db/rls/replies.sql` · `db/rls/school_info.sql` · `db/rls/session_log.sql` · `db/rls/topup.sql` · `db/rls/voting.sql` · `db/rls/withdraw.sql`

## 합성 데이터

생성기가 만든다.

---

[[index|위키 색인]] · [[erd|ERD]] · 정의는 `db/ddl/` 이 진실이다
