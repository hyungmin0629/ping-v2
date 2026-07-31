---
title: board_category
domain: 게시판
kind: master
rows: 5
tags: [테이블, 게시판]
---

# board_category

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**게시판** · 마스터 — 선택지·코드표. 시드 SQL 이 채운다 · 실데이터 **5행**

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `code` | varchar(20) | NOT NULL |  |
| `name` | varchar(30) | NOT NULL |  |
| `description` | varchar(100) |  |  |
| `sort_order` | smallint | NOT NULL |  |
| `is_active` | boolean | NOT NULL |  |

**UNIQUE** — `code`

**이 표를 참조하는 표** — [[post]]

## 이 표를 다루는 정책·RPC

`db/rls/board.sql` · `db/rls/policies.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
