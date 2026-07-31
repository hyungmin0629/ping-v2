---
title: sanction_policy
domain: 신고와 제재
kind: master
rows: 5
tags: [테이블, 신고와 제재]
---

# sanction_policy · 자동 제재 정책

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**신고와 제재** · 마스터 — 선택지·코드표. 시드 SQL 이 채운다 · 실데이터 **5행**

## 왜 이렇게 생겼나

임계값을 코드가 아니라 데이터로 정의한다. 구 시스템은 피신고 10회 이상 116명 중 제재된 사람이 0명이었고, 253회 신고받은 유저도 정상 상태로 활동 중이었다. 정책이 스키마에 드러나야 감사가 가능하다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `name` | varchar(60) | NOT NULL |  |
| `target_type` | report_target | NOT NULL |  |
| `threshold_count` | integer | NOT NULL |  |
| `window_days` | smallint | NOT NULL |  |
| `action_type` | sanction_type | NOT NULL |  |
| `action_days` | smallint |  |  |
| `is_active` | boolean | NOT NULL |  |

**이 표를 참조하는 표** — `sanction`

## 얽힌 결정 1개

- [[report-sanction-fk|신고와 제재를 FK로 연결하고 정책을 데이터로 정의]]

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql`

## 합성 데이터

생성기가 만든다.

---

[[index|위키 색인]] · [[erd|ERD]] · 정의는 `db/ddl/` 이 진실이다
