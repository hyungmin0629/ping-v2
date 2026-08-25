---
title: vote_item
domain: 질문과 투표
kind: activity
rows: 800
tags: [테이블, 질문과 투표]
---

# vote_item · 투표 아이템(출제된 질문 1건)

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**질문과 투표** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **800행**

## 왜 이렇게 생겼나

스킵 컬럼이 없다. 스킵 기능을 폐지했기 때문이다. candidate_scope 는 출제 시점의 스코프 스냅샷이다. 질문의 scope 가 나중에 바뀌어도 과거 투표의 해석이 흔들리지 않도록 복사해 둔다. ⚠️ padded_count 를 마이그레이션 003 이 붙인다 — 아래 정의에는 없다. 후보가 4명이 안 될 때 스코프를 낮추지 않고 **친구 중 다른 사람으로 채우기** 때문에, CLASS 질문에 타반 후보가 섞일 수 있다. 그 수를 남긴 값이다. ⚠️ 분석에서 이 값을 안 보면 규칙 위반과 구분되지 않는다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `session_id` | bigint | NOT NULL | → [[vote_session]] |
| `user_id` | bigint | NOT NULL | → [[app_user]] |
| `question_id` | bigint | NOT NULL | → [[question]] |
| `candidate_scope` | question_scope | NOT NULL |  |
| `position` | smallint | NOT NULL |  |
| `shuffle_count` | smallint | NOT NULL |  |
| `served_at` | timestamptz | NOT NULL |  |
| `voted_at` | timestamptz |  |  |
| `padded_count` | smallint | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `session_id, position`

**이 표를 참조하는 표** — [[heart_transaction]] · [[vote_candidate]] · [[vote_received]] · [[vote_shuffle]]

## 얽힌 결정 12개

- [[backfill-updated-at|대량 적재 후 `updated_at` 을 각 행의 원래 시각으로 되돌린다]]
- [[ddl-comments-rot-with-migrations|DDL 주석은 마이그레이션 뒤에 낡는다 — 파일이 아니라 순서가 진실이다]]
- [[expired-session-status|중도 이탈 세션은 EXPIRED 로 적는다 — 완료율이 98.6%로 보이던 이유]]
- [[generator-emits-updated-at|`updated_at` 을 생성기가 직접 싣는다 — 백필 UPDATE 가 3시간을 먹었다]]
- [[join-requires-source|두 원천의 id 가 겹친다 — 조인에 `_source` 를 강제한다]]
- [[local-db-via-apply|로컬 DB 는 `apply.py` 로만 만든다]]
- [[lower-scope-when-short|후보가 4명이 안 되면 스코프를 낮추고, 그래도 안 되면 질문을 내지 않는다]]
- [[pad-candidates-keep-scope|후보가 모자라면 스코프를 낮추지 않고 다른 친구로 채운다]]
- [[partition-ordered-extract|파티션 테이블로 부을 때는 파티션 컬럼 순서로 꺼낸다]]
- [[purge-synthetic-data|합성 데이터를 전부 지운다 — 낡아서]]
- [[remove-circular-fk|순환 FK를 제거하는 방향으로 스키마 정리]]
- [[session-bounded-actions|유저의 직접 행동은 접속 세션 안에서만 일어난다 — v5]]

## 이 표를 지키는 정합성 검사 7종

`qa/checks/integrity.sql` · 위반 0이어야 한다.

- 가입 이전 활동
- 출제 이전 투표
- 선택 없는 완료 투표
- 친구 아닌 후보
- CLASS 스코프에 설명 안 되는 타반 후보
- SCHOOL 스코프에 설명 안 되는 타교 후보
- 자기 자신이 후보

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql` · `db/rls/profile.sql` · `db/rls/received.sql` · `db/rls/replies.sql` · `db/rls/voting.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
