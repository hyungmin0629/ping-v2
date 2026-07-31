---
title: heart_transaction_type
domain: 하트
kind: master
rows: 9
tags: [테이블, 하트]
---

# heart_transaction_type · 거래 유형 마스터

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**하트** · 마스터 — 선택지·코드표. 시드 SQL 이 채운다 · 실데이터 **9행**

## 왜 이렇게 생겼나

구 스키마는 delta_point 값만 보고 의미를 역추론해야 했다 (5~15 = 투표 적립, -300 = 힌트 구매 ... 전부 추측이었다).

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `code` | varchar(30) | NOT NULL | **PK** |
| `label` | varchar(50) | NOT NULL |  |
| `is_credit` | boolean | NOT NULL |  |
| `is_active` | boolean | NOT NULL |  |

**이 표를 참조하는 표** — [[heart_transaction]]

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
