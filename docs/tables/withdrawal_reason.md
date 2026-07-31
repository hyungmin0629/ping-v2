---
title: withdrawal_reason
domain: 유저
kind: master
rows: 6
tags: [테이블, 유저]
---

# withdrawal_reason · 탈퇴 사유 마스터

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**유저** · 마스터 — 선택지·코드표. 시드 SQL 이 채운다 · 실데이터 **6행**

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `code` | varchar(30) | NOT NULL | **PK** |
| `label` | varchar(60) | NOT NULL |  |
| `sort_order` | smallint | NOT NULL |  |
| `is_active` | boolean | NOT NULL |  |

**이 표를 참조하는 표** — `user_withdrawal`

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql` · `db/rls/withdraw.sql`

## 합성 데이터

생성기가 만든다.

---

[[index|위키 색인]] · [[erd|ERD]] · 정의는 `db/ddl/` 이 진실이다
