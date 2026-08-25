---
title: friendship
domain: 친구
kind: activity
rows: 179
tags: [테이블, 친구]
---

# friendship · 친구 관계(수락된 무방향 간선)

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**친구** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **179행**

## 왜 이렇게 생겼나

user_low_id < user_high_id 를 강제해 (A,B)와 (B,A)가 중복 저장되는 것을 막는다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `user_low_id` | bigint | NOT NULL | → [[app_user]] |
| `user_high_id` | bigint | NOT NULL | → [[app_user]] |
| `source` | relation_source | NOT NULL |  |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |
| `ended_at` | timestamptz |  |  |

**UNIQUE** — `user_low_id, user_high_id · 단, (ended_at IS NULL)`

## 얽힌 결정 4개

- [[friend-invite-code-two-step|친구 맺기는 초대 코드로만, 요청·수락 2단계로]]
- [[friendship-ended-at|친구를 끊어도 행을 지우지 않는다]]
- [[stg-views-for-dashboard|대시보드가 스테이징을 넷 늘린다]]
- [[withdraw-keeps-rows|계정 삭제는 행을 지우지 않는다]]

## 이 표를 지키는 정합성 검사 3종

`qa/checks/integrity.sql` · 위반 0이어야 한다.

- 게이트 위반(5명을 맺어본 적 없는데 해금)
- 친구 아닌 후보
- friend_count 불일치

## 이 표를 다루는 정책·RPC

`db/rls/friends.sql` · `db/rls/policies.sql` · `db/rls/voting.sql` · `db/rls/withdraw.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
