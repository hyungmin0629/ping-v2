---
title: school_event
domain: 학교 정보
kind: reference
rows: 139
tags: [테이블, 학교 정보]
---

# school_event · 학사일정

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**학교 정보** · 참조 — 외부(NEIS)에서 받아 채운다 · 실데이터 **139행**

## 왜 이렇게 생겼나

시작·종료일을 분리해 기간 일정을 지원한다. grade_scope 가 NULL 이면 전교 대상, 값이 있으면 해당 학년만 해당한다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `school_id` | bigint | NOT NULL | → [[school]] |
| `title` | varchar(120) | NOT NULL |  |
| `event_type` | school_event_type | NOT NULL |  |
| `start_date` | date | NOT NULL |  |
| `end_date` | date | NOT NULL |  |
| `is_all_day` | boolean | NOT NULL |  |
| `grade_scope` | smallint |  |  |
| `source` | data_source | NOT NULL |  |
| `external_id` | varchar(80) |  |  |
| `is_manually_overridden` | boolean | NOT NULL |  |
| `synced_at` | timestamptz |  |  |
| `updated_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `school_id, external_id · 단, (external_id IS NOT NULL)`

## 얽힌 결정 2개

- [[neis-merge-spans|NEIS 가 하루씩 주는 것을 기간으로 묶는다]]
- [[school-info-write-revoked|학사일정·공지의 쓰기 권한이 열려 있었다]]

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql` · `db/rls/school_info.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
