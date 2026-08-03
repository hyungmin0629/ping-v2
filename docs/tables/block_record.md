---
title: block_record
domain: 친구
kind: activity
rows: 0
tags: [테이블, 친구]
---

# block_record · 차단

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**친구** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **0행**

> **비어 있다 — 화면이나 실행 코드가 없다.** 차단 화면 없음. 1:1 텍스트를 열 때 먼저 만들기로 한 것

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `user_id` | bigint | NOT NULL | → [[app_user]] |
| `blocked_user_id` | bigint | NOT NULL | → [[app_user]] |
| `reason` | block_reason | NOT NULL |  |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `user_id, blocked_user_id`

## 얽힌 결정 2개

- [[friendship-ended-at|친구를 끊어도 행을 지우지 않는다]]
- [[report-first-block-later|신고는 게시판과 함께, 차단은 뒤로]]

## 이 표를 다루는 정책·RPC

`db/rls/friends.sql` · `db/rls/policies.sql` · `db/rls/recommend.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
