---
title: user_session
domain: 유저
kind: activity
rows: 81
tags: [테이블, 유저]
---

# user_session · 세션

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**유저** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **81행**

## 왜 이렇게 생겼나

리텐션을 추정이 아니라 실측하기 위한 테이블.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `user_id` | bigint | NOT NULL | → [[app_user]] |
| `platform` | platform_type | NOT NULL |  |
| `app_version` | varchar(20) | NOT NULL |  |
| `device_id` | varchar(64) |  |  |
| `started_at` | timestamptz | NOT NULL |  |
| `ended_at` | timestamptz |  |  |
| `updated_at` | timestamptz | NOT NULL |  |

## 얽힌 결정 4개

- [[bulk-load-batch-rows|합성 대량 적재는 배치를 20만 행으로 키운다]]
- [[daily-rhythm-night-peak|하루 리듬을 붙인다 — 최대 봉우리는 점심이 아니라 밤 22시다]]
- [[generator-emits-updated-at|`updated_at` 을 생성기가 직접 싣는다 — 백필 UPDATE 가 3시간을 먹었다]]
- [[session-bounded-actions|유저의 직접 행동은 접속 세션 안에서만 일어난다 — v5]]

## 이 표를 지키는 정합성 검사 1종

`qa/checks/integrity.sql` · 위반 0이어야 한다.

- 가입 이전 세션

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql` · `db/rls/session_log.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
