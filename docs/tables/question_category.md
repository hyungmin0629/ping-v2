---
title: question_category
domain: 질문과 투표
kind: master
rows: 8
tags: [테이블, 질문과 투표]
---

# question_category · 질문 카테고리

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**질문과 투표** · 마스터 — 선택지·코드표. 시드 SQL 이 채운다 · 실데이터 **8행**

## 왜 이렇게 생겼나

구 스키마에는 카테고리가 없어 "외모/신체 질문이 신고 상위 5개를 독점"한다는 사실을 사후 수동 분류로만 확인할 수 있었다. is_sensitive 로 위험 카테고리를 사전에 표시한다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `code` | varchar(30) | NOT NULL |  |
| `name` | varchar(40) | NOT NULL |  |
| `is_sensitive` | boolean | NOT NULL |  |
| `sort_order` | smallint | NOT NULL |  |
| `is_active` | boolean | NOT NULL |  |

**UNIQUE** — `code`

**이 표를 참조하는 표** — [[question]] · [[question_request]]

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
