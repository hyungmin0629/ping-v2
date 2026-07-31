---
title: heart_purchase
domain: 하트
kind: activity
rows: 6
tags: [테이블, 하트]
---

# heart_purchase · 충전 결제

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**하트** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **6행**

## 왜 이렇게 생겼나

성공/실패를 한 테이블에 status 로 통합한다. 구 스키마는 별도 테이블이었고 실패 로깅이 2023-09에 조용히 끊겨 그 이후로는 실패율 자체를 계산할 수 없었다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `user_id` | bigint | NOT NULL | → app_user |
| `product_id` | bigint | NOT NULL | → heart_product |
| `platform` | platform_type | NOT NULL |  |
| `store_transaction_id` | varchar(120) |  |  |
| `status` | purchase_status | NOT NULL |  |
| `failure_reason` | varchar(120) |  |  |
| `price_krw` | integer | NOT NULL |  |
| `heart_amount` | integer | NOT NULL |  |
| `created_at` | timestamptz | NOT NULL |  |
| `completed_at` | timestamptz |  |  |
| `updated_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `store_transaction_id`

**이 표를 참조하는 표** — `heart_transaction`

## 얽힌 결정 2개

- [[ads-payments-stub|MVP에서 광고와 결제를 스텁으로 처리]]
- [[topup-stub-daily-limit|하트 충전은 결제 없는 스텁 — 대신 하루 한 번]]

## 이 표를 지키는 정합성 검사 1종

`qa/checks/integrity.sql` · 위반 0이어야 한다.

- 원장 없는 충전

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql` · `db/rls/topup.sql`

## 합성 데이터

생성기가 만든다.

---

[[index|위키 색인]] · [[erd|ERD]] · 정의는 `db/ddl/` 이 진실이다
