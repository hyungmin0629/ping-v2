---
title: meal_menu_item
domain: 학교 정보
kind: reference
rows: 19929
tags: [테이블, 학교 정보]
---

# meal_menu_item · 급식 메뉴 항목

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**학교 정보** · 참조 — 외부(NEIS)에서 받아 채운다 · 실데이터 **19,929행**

## 왜 이렇게 생겼나

메뉴를 한 덩어리 텍스트가 아니라 요리 단위로 분리한다. "인기 급식 메뉴" 분석과 알레르기 필터가 가능해진다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `meal_plan_id` | bigint | NOT NULL | → [[meal_plan]] |
| `dish_name` | varchar(80) | NOT NULL |  |
| `allergy_codes` | varchar(60) |  |  |
| `sort_order` | smallint | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |

## 얽힌 결정 2개

- [[backfill-updated-at|대량 적재 후 `updated_at` 을 각 행의 원래 시각으로 되돌린다]]
- [[watermark-updated-at|증분 워터마크를 `updated_at` 하나로 통일한다]]

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql` · `db/rls/school_info.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
