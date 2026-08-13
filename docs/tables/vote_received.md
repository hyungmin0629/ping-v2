---
title: vote_received
domain: 질문과 투표
kind: activity
rows: 618
tags: [테이블, 질문과 투표]
---

# vote_received · 지목받은 기록(수신자 관점)

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**질문과 투표** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **618행**

## 왜 이렇게 생겼나

⚠️ 아래 정의에 없는 컬럼이 마이그레이션으로 셋 붙었다: reply_text · replied_at   008. 나를 뽑은 사람에게 보내는 1회성 답장 (20하트·30자). answer_status = PRIVATE 로 표시된다 updated_at                004. 증분 적재 워터마크. **이 표에 특히 중요하다** — reveal_status 는 힌트를 살 때마다 바뀌는데 created_at 으로 증분을 뜨면 그 변경이 BigQuery 에 영영 도달하지 않는다 반대로 hint_char_index 는 **찾지 말 것.** 006 이 여기 넣었다가 007 이 hint_purchase.char_index 로 옮겼다. 자모 힌트마다 다른 글자를 가리키게 바뀌었기 때문이다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `vote_item_id` | bigint | NOT NULL | → [[vote_item]] |
| `voter_id` | bigint | NOT NULL | → [[app_user]] |
| `receiver_id` | bigint | NOT NULL | → [[app_user]] |
| `question_id` | bigint | NOT NULL | → [[question]] |
| `is_read` | boolean | NOT NULL |  |
| `read_at` | timestamptz |  |  |
| `reveal_status` | reveal_status | NOT NULL |  |
| `answer_status` | answer_status | NOT NULL |  |
| `answered_at` | timestamptz |  |  |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |
| `reply_text` | varchar(30) |  |  |
| `replied_at` | timestamptz |  |  |

**UNIQUE** — `vote_item_id`

**이 표를 참조하는 표** — [[hint_purchase]]

## 얽힌 결정 5개

- [[ddl-comments-rot-with-migrations|DDL 주석은 마이그레이션 뒤에 낡는다 — 파일이 아니라 순서가 진실이다]]
- [[one-time-reply|1회성 답장을 연다 — 차단 화면 없이]]
- [[partition-ordered-extract|파티션 테이블로 부을 때는 파티션 컬럼 순서로 꺼낸다]]
- [[voter-identity-view-only|투표자 신원은 뷰로만 노출한다]]
- [[watermark-updated-at|증분 워터마크를 `updated_at` 하나로 통일한다]]

## 이 표를 다루는 정책·RPC

`db/rls/hints.sql` · `db/rls/policies.sql` · `db/rls/received.sql` · `db/rls/replies.sql` · `db/rls/voting.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
