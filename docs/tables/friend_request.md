---
title: friend_request
domain: 친구
kind: activity
rows: 220
tags: [테이블, 친구]
---

# friend_request · 친구 요청

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**친구** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **220행**

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `sender_id` | bigint | NOT NULL | → [[app_user]] |
| `receiver_id` | bigint | NOT NULL | → [[app_user]] |
| `status` | friend_req_status | NOT NULL |  |
| `source` | relation_source | NOT NULL |  |
| `created_at` | timestamptz | NOT NULL |  |
| `responded_at` | timestamptz |  |  |
| `updated_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `sender_id, receiver_id · 단, (status = 'PENDING'::friend_req_status)`

## 얽힌 결정 3개

- [[friend-invite-code-two-step|친구 맺기는 초대 코드로만, 요청·수락 2단계로]]
- [[friend-recommend-same-school|친구 추천 — "초대 코드로만"을 같은 학교 범위에서 연다]]
- [[friendship-ended-at|친구를 끊어도 행을 지우지 않는다]]

## 이 표를 다루는 정책·RPC

`db/rls/friends.sql` · `db/rls/policies.sql` · `db/rls/recommend.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
