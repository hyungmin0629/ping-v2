---
title: grade_class
domain: 기준 정보
kind: reference
rows: 538
tags: [테이블, 기준 정보]
---

# grade_class · 학급

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**기준 정보** · 참조 — 외부(NEIS)에서 받아 채운다 · 실데이터 **538행**

## 왜 이렇게 생겼나

label: 화면에 보여줄 이름을 직접 지정하고 싶을 때만 채운다. 비어 있으면 앱이 "N학년 M반"으로 조립한다. 일반 학교는 비워두고, "1팀"처럼 학년·반 체계가 아닌 조직에만 쓴다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `school_id` | bigint | NOT NULL | → school |
| `grade` | smallint | NOT NULL |  |
| `class_num` | smallint | NOT NULL |  |
| `created_at` | timestamptz | NOT NULL |  |
| `label` | varchar(20) |  |  |

**UNIQUE** — `school_id, grade, class_num`

**이 표를 참조하는 표** — `app_user` · `timetable`

## 이 표를 지키는 정합성 검사 1종

`qa/checks/integrity.sql` · 위반 0이어야 한다.

- SCHOOL 스코프에 설명 안 되는 타교 후보

## 이 표를 다루는 정책·RPC

`db/rls/board.sql` · `db/rls/hints.sql` · `db/rls/onboarding.sql` · `db/rls/policies.sql` · `db/rls/profile.sql` · `db/rls/recommend.sql` · `db/rls/school_info.sql` · `db/rls/school_picker.sql` · `db/rls/voting.sql`

## 합성 데이터

생성기가 만든다.

---

[[index|위키 색인]] · [[erd|ERD]] · 정의는 `db/ddl/` 이 진실이다
