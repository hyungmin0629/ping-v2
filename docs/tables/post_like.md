---
title: post_like
domain: 게시판
kind: activity
rows: 18
tags: [테이블, 게시판]
---

# post_like · 좋아요

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**게시판** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **18행**

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `post_id` | bigint | NOT NULL | → [[post]] |
| `user_id` | bigint | NOT NULL | → [[app_user]] |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `post_id, user_id`

## 얽힌 결정 2개

- [[no-anonymous-board|익명 게시판을 v1에서 제외]]
- [[school-boundary-self-reported|학교 경계는 기술로 막지만, 소속은 자기신고다]]

## 이 표를 다루는 정책·RPC

`db/rls/board.sql` · `db/rls/policies.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
