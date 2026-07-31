---
title: report
domain: 신고와 제재
kind: activity
rows: 3
tags: [테이블, 신고와 제재]
---

# report · 신고

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**신고와 제재** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **3행**

## 왜 이렇게 생겼나

유저·질문·게시글·댓글 신고를 한 테이블로 통합하되, 대상별 FK를 명시 컬럼으로 두어 참조 무결성을 지킨다. (다형 참조 방식은 FK를 걸 수 없어 채택하지 않았다.) post / post_comment 참조는 90_board.sql 에서 추가한다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `reporter_id` | bigint | NOT NULL | → [[app_user]] |
| `target_type` | report_target | NOT NULL |  |
| `target_user_id` | bigint |  | → [[app_user]] |
| `target_question_id` | bigint |  | → [[question]] |
| `target_post_id` | bigint |  | → [[post]] |
| `target_comment_id` | bigint |  | → [[post_comment]] |
| `reason_code` | varchar(30) | NOT NULL | → [[report_reason]] |
| `detail_text` | varchar(500) |  |  |
| `status` | report_status | NOT NULL |  |
| `reviewed_by_admin_id` | bigint |  | → [[app_user]] |
| `reviewed_at` | timestamptz |  |  |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |

**이 표를 참조하는 표** — [[sanction]]

## 얽힌 결정 3개

- [[drop-admin-user|admin_user 를 없애고 app_user.is_admin 하나로 접는다]]
- [[one-time-reply|1회성 답장을 연다 — 차단 화면 없이]]
- [[report-first-block-later|신고는 게시판과 함께, 차단은 뒤로]]

## 이 표를 다루는 정책·RPC

`db/rls/board.sql` · `db/rls/policies.sql` · `db/rls/replies.sql`

## 합성 데이터

⚠️ **생성기가 아직 만들지 않는다.** 합성 데이터를 채우려면 새로 써야 한다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
