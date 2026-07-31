---
title: meal_plan
domain: 학교 정보
kind: reference
rows: 2938
tags: [테이블, 학교 정보]
---

# meal_plan · 급식표

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**학교 정보** · 참조 — 외부(NEIS)에서 받아 채운다 · 실데이터 **2,938행**

## 왜 이렇게 생겼나

학교·날짜·끼니에 UNIQUE. 같은 날 중복 급식이 들어오는 것을 DB가 막는다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `school_id` | bigint | NOT NULL | → [[school]] |
| `serve_date` | date | NOT NULL |  |
| `meal_type` | meal_type | NOT NULL |  |
| `calorie_kcal` | numeric(6,1) |  |  |
| `source` | data_source | NOT NULL |  |
| `external_id` | varchar(80) |  |  |
| `is_manually_overridden` | boolean | NOT NULL |  |
| `synced_at` | timestamptz |  |  |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `school_id, serve_date, meal_type`

**이 표를 참조하는 표** — [[meal_menu_item]]

## 얽힌 결정 1개

- [[school-info-write-revoked|학사일정·공지의 쓰기 권한이 열려 있었다]]

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql` · `db/rls/school_info.sql`

## 합성 데이터

⚠️ **생성기가 아직 만들지 않는다.** 합성 데이터를 채우려면 새로 써야 한다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
