---
title: vote_session
domain: 질문과 투표
kind: activity
rows: 73
tags: [테이블, 질문과 투표]
---

# vote_session · 투표 세션

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**질문과 투표** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **73행**

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `user_id` | bigint | NOT NULL | → [[app_user]] |
| `status` | session_status | NOT NULL |  |
| `item_count` | smallint | NOT NULL |  |
| `started_at` | timestamptz | NOT NULL |  |
| `completed_at` | timestamptz |  |  |
| `updated_at` | timestamptz | NOT NULL |  |

**이 표를 참조하는 표** — [[vote_item]]

## 얽힌 결정 4개

- [[daily-rhythm-night-peak|하루 리듬을 붙인다 — 최대 봉우리는 점심이 아니라 밤 22시다]]
- [[expired-session-status|중도 이탈 세션은 EXPIRED 로 적는다 — 완료율이 98.6%로 보이던 이유]]
- [[lower-scope-when-short|후보가 4명이 안 되면 스코프를 낮추고, 그래도 안 되면 질문을 내지 않는다]]
- [[session-bounded-actions|유저의 직접 행동은 접속 세션 안에서만 일어난다 — v5]]

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql` · `db/rls/voting.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
