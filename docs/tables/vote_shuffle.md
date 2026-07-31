---
title: vote_shuffle
domain: 질문과 투표
kind: activity
rows: 17
tags: [테이블, 질문과 투표]
---

# vote_shuffle · 셔플

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**질문과 투표** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **17행**

## 왜 이렇게 생겼나

vote_item_id 에 UNIQUE → DB 차원에서 1회 제한을 강제한다. ad_impression_id 가 NOT NULL → 광고 없이 셔플한 기록은 존재할 수 없다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `vote_item_id` | bigint | NOT NULL | → vote_item |
| `ad_impression_id` | bigint | NOT NULL | → ad_impression |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `vote_item_id` · `ad_impression_id`

## 얽힌 결정 1개

- [[shuffle-once-constraint|셔플은 DB 제약으로 1회를 강제한다]]

## 이 표를 지키는 정합성 검사 1종

`qa/checks/integrity.sql` · 위반 0이어야 한다.

- 광고 미완료 셔플

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql` · `db/rls/voting.sql`

## 합성 데이터

생성기가 만든다.

---

[[index|위키 색인]] · [[erd|ERD]] · 정의는 `db/ddl/` 이 진실이다
