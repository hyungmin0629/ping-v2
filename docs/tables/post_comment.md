---
title: post_comment
domain: 게시판
kind: activity
rows: 18
tags: [테이블, 게시판]
---

# post_comment · 댓글

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**게시판** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **18행**

## 왜 이렇게 생겼나

⚠️ **anonymous_seq 는 마이그레이션 005 가 nullable 로 바꿨고, 지금은 안 쓴다.** 닉네임 게시판이라 익명 번호를 채울 사람이 없다. 아래 NOT NULL 을 그대로 읽지 말 것. 왜 컬럼을 지우지 않았나 — 익명 게시판은 보류이지 폐기가 아니다. 지웠다 다시 만들면 그 사이 댓글에는 번호를 소급할 수 없다. ⚠️ 아래 uq_comment_anon 도 005 가 걷어낸다. 그대로 두면 **한 사람이 한 글에 댓글을 두 번 달 수 없다** — 대화가 성립하지 않는다. anonymous_seq(익명으로 열 때의 원안): 글 안에서만 유효한 익명 번호(익명1, 익명2 ...). 같은 사람은 같은 글에서 같은 번호를 유지해 대화 맥락이 읽히게 한다. 글이 다르면 번호도 달라져 글 사이의 동일인 추적은 불가능하다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `post_id` | bigint | NOT NULL | → [[post]] |
| `parent_comment_id` | bigint |  | → [[post_comment]] |
| `author_id` | bigint | NOT NULL | → [[app_user]] |
| `anonymous_seq` | smallint |  |  |
| `body` | varchar(1000) | NOT NULL |  |
| `like_count` | integer | NOT NULL |  |
| `status` | content_status | NOT NULL |  |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `post_id, author_id, anonymous_seq`

**이 표를 참조하는 표** — [[comment_like]] · [[post_comment]] · [[report]]

## 얽힌 결정 4개

- [[backfill-updated-at|대량 적재 후 `updated_at` 을 각 행의 원래 시각으로 되돌린다]]
- [[no-anonymous-board|익명 게시판을 v1에서 제외]]
- [[open-named-board|자유게시판을 연다 — 글도 댓글도 닉네임으로]]
- [[school-boundary-self-reported|학교 경계는 기술로 막지만, 소속은 자기신고다]]

## 이 표를 다루는 정책·RPC

`db/rls/board.sql` · `db/rls/policies.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
