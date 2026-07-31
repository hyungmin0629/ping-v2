---
title: question_request
domain: 질문과 투표
kind: activity
rows: 0
tags: [테이블, 질문과 투표]
---

# question_request · 질문 요청(유저 제안 → 검수)

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**질문과 투표** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **0행**

> **비어 있다 — 화면이나 실행 코드가 없다.** 유저가 질문을 제안하는 화면이 없다

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `user_id` | bigint | NOT NULL | → app_user |
| `text` | varchar(200) | NOT NULL |  |
| `proposed_scope` | question_scope | NOT NULL |  |
| `proposed_category_id` | bigint |  | → question_category |
| `status` | request_status | NOT NULL |  |
| `reject_reason` | varchar(200) |  |  |
| `reviewed_by_admin_id` | bigint |  | → app_user |
| `reviewed_at` | timestamptz |  |  |
| `published_question_id` | bigint |  | → question |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `published_question_id · 단, (published_question_id IS NOT NULL)`

## 얽힌 결정 2개

- [[drop-admin-user|admin_user 를 없애고 app_user.is_admin 하나로 접는다]]
- [[remove-circular-fk|순환 FK를 제거하는 방향으로 스키마 정리]]

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql`

## 합성 데이터

생성기가 만든다.

---

[[index|위키 색인]] · [[erd|ERD]] · 정의는 `db/ddl/` 이 진실이다
