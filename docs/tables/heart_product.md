---
title: heart_product
domain: 하트
kind: master
rows: 4
tags: [테이블, 하트]
---

# heart_product · 충전 상품

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**하트** · 마스터 — 선택지·코드표. 시드 SQL 이 채운다 · 실데이터 **4행**

## 왜 이렇게 생겼나

구 스키마는 productId 문자열만 있고 가격·수량이 코드에만 있어 매출 계산 시 값을 하드코딩해야 했다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `product_code` | varchar(40) | NOT NULL |  |
| `heart_amount` | integer | NOT NULL |  |
| `price_krw` | integer | NOT NULL |  |
| `label` | varchar(30) |  |  |
| `is_active` | boolean | NOT NULL |  |

**UNIQUE** — `product_code`

**이 표를 참조하는 표** — `heart_purchase`

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql` · `db/rls/topup.sql`

## 합성 데이터

생성기가 만든다.

---

[[index|위키 색인]] · [[erd|ERD]] · 정의는 `db/ddl/` 이 진실이다
