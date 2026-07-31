---
title: question
domain: 질문과 투표
kind: master
rows: 24
tags: [테이블, 질문과 투표]
---

# question · 질문

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**질문과 투표** · 마스터 — 선택지·코드표. 시드 SQL 이 채운다 · 실데이터 **24행**

## 왜 이렇게 생겼나

scope: CLASS / SCHOOL / GLOBAL. 세 스코프 모두 "친구" 안에서의 범위이며, GLOBAL 도 전체 가입자가 아니라 학교 무관 친구 전체를 뜻한다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `text` | varchar(200) | NOT NULL |  |
| `scope` | question_scope | NOT NULL |  |
| `category_id` | bigint | NOT NULL | → question_category |
| `status` | question_status | NOT NULL |  |
| `source` | question_source | NOT NULL |  |
| `report_count` | integer | NOT NULL |  |
| `created_by_admin_id` | bigint |  | → app_user |
| `created_at` | timestamptz | NOT NULL |  |

**이 표를 참조하는 표** — `question_request` · `report` · `vote_item` · `vote_received`

## 얽힌 결정 3개

- [[drop-admin-user|admin_user 를 없애고 app_user.is_admin 하나로 접는다]]
- [[lower-scope-when-short|후보가 4명이 안 되면 스코프를 낮추고, 그래도 안 되면 질문을 내지 않는다]]
- [[remove-circular-fk|순환 FK를 제거하는 방향으로 스키마 정리]]

## 이 표를 다루는 정책·RPC

`db/rls/hints.sql` · `db/rls/policies.sql` · `db/rls/received.sql` · `db/rls/replies.sql` · `db/rls/voting.sql`

## 합성 데이터

생성기가 만든다.

---

[[index|위키 색인]] · [[erd|ERD]] · 정의는 `db/ddl/` 이 진실이다
