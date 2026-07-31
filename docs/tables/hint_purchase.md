---
title: hint_purchase
domain: 질문과 투표
kind: activity
rows: 120
tags: [테이블, 질문과 투표]
---

# hint_purchase · 힌트 구매

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**질문과 투표** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **120행**

## 왜 이렇게 생겼나

구 데이터에서 확인된 누진 요금(200 → 300 → 500 → 1000)을 step 으로 명시화한다. 하트 차감은 heart_transaction 이 이 행을 참조하는 단방향 구조.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `vote_received_id` | bigint | NOT NULL | → vote_received |
| `user_id` | bigint | NOT NULL | → app_user |
| `hint_type` | hint_type | NOT NULL |  |
| `step` | smallint | NOT NULL |  |
| `heart_cost` | integer | NOT NULL |  |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |
| `ad_impression_id` | bigint |  | → ad_impression |
| `char_index` | smallint |  |  |

**UNIQUE** — `vote_received_id, hint_type` · `ad_impression_id · 단, (ad_impression_id IS NOT NULL)`

**이 표를 참조하는 표** — `heart_transaction`

## 얽힌 결정 1개

- [[remove-circular-fk|순환 FK를 제거하는 방향으로 스키마 정리]]

## 이 표를 지키는 정합성 검사 1종

`qa/checks/integrity.sql` · 위반 0이어야 한다.

- 원장 없는 유료 힌트 구매

## 이 표를 다루는 정책·RPC

`db/rls/hints.sql` · `db/rls/policies.sql` · `db/rls/received.sql`

## 합성 데이터

생성기가 만든다.

---

[[index|위키 색인]] · [[erd|ERD]] · 정의는 `db/ddl/` 이 진실이다
