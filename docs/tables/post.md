---
title: post
domain: 게시판
kind: activity
rows: 20
tags: [테이블, 게시판]
---

# post · 게시글

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**게시판** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **20행**

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `school_id` | bigint | NOT NULL | → school |
| `category_id` | bigint | NOT NULL | → board_category |
| `author_id` | bigint | NOT NULL | → app_user |
| `title` | varchar(120) | NOT NULL |  |
| `body` | text | NOT NULL |  |
| `view_count` | integer | NOT NULL |  |
| `like_count` | integer | NOT NULL |  |
| `comment_count` | integer | NOT NULL |  |
| `report_count` | integer | NOT NULL |  |
| `status` | content_status | NOT NULL |  |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |

**이 표를 참조하는 표** — `post_comment` · `post_like` · `report`

## 얽힌 결정 4개

- [[backfill-updated-at|대량 적재 후 `updated_at` 을 각 행의 원래 시각으로 되돌린다]]
- [[board-school-scope|게시판 범위는 학교, 카테고리는 하나]]
- [[no-anonymous-board|익명 게시판을 v1에서 제외]]
- [[school-boundary-self-reported|학교 경계는 기술로 막지만, 소속은 자기신고다]]

## 이 표를 다루는 정책·RPC

`db/rls/board.sql` · `db/rls/policies.sql` · `db/rls/profile.sql`

## 합성 데이터

⚠️ **생성기가 아직 만들지 않는다.** 합성 데이터를 채우려면 새로 써야 한다.

---

[[index|위키 색인]] · [[erd|ERD]] · 정의는 `db/ddl/` 이 진실이다
