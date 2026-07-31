---
title: vote_received
domain: 질문과 투표
kind: activity
rows: 587
tags: [테이블, 질문과 투표]
---

# vote_received · 지목받은 기록(수신자 관점)

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**질문과 투표** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **587행**

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `vote_item_id` | bigint | NOT NULL | → vote_item |
| `voter_id` | bigint | NOT NULL | → app_user |
| `receiver_id` | bigint | NOT NULL | → app_user |
| `question_id` | bigint | NOT NULL | → question |
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

**이 표를 참조하는 표** — `hint_purchase`

## 얽힌 결정 3개

- [[one-time-reply|1회성 답장을 연다 — 차단 화면 없이]]
- [[voter-identity-view-only|투표자 신원은 뷰로만 노출한다]]
- [[watermark-updated-at|증분 워터마크를 `updated_at` 하나로 통일한다]]

## 이 표를 다루는 정책·RPC

`db/rls/hints.sql` · `db/rls/policies.sql` · `db/rls/received.sql` · `db/rls/replies.sql` · `db/rls/voting.sql`

## 합성 데이터

생성기가 만든다.

---

[[index|위키 색인]] · [[erd|ERD]] · 정의는 `db/ddl/` 이 진실이다
