---
title: region
domain: 기준 정보
kind: reference
rows: 266
tags: [테이블, 기준 정보]
---

# region · 지역

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**기준 정보** · 참조 — 외부(NEIS)에서 받아 채운다 · 실데이터 **266행**

## 왜 이렇게 생겼나

구 스키마는 accounts_school.address 가 varchar(100) 한 덩어리라 시/군 단위 집계가 불가능했다. 시도·시군구를 정규화한다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `sido` | varchar(20) | NOT NULL |  |
| `sigungu` | varchar(30) | NOT NULL |  |
| `created_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `sido, sigungu`

**이 표를 참조하는 표** — [[school]]

## 얽힌 결정 1개

- [[stg-views-for-dashboard|대시보드가 스테이징을 넷 늘린다]]

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql` · `db/rls/school_picker.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
