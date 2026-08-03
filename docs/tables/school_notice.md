---
title: school_notice
domain: 학교 정보
kind: reference
rows: 0
tags: [테이블, 학교 정보]
---

# school_notice · 공지사항

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**학교 정보** · 참조 — 외부(NEIS)에서 받아 채운다 · 실데이터 **0행**

> **비어 있다 — 화면이나 실행 코드가 없다.** 수집기 없음. W8 에서 미뤄둔 것

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `school_id` | bigint | NOT NULL | → [[school]] |
| `title` | varchar(200) | NOT NULL |  |
| `body` | text | NOT NULL |  |
| `source` | data_source | NOT NULL |  |
| `external_id` | varchar(80) |  |  |
| `is_manually_overridden` | boolean | NOT NULL |  |
| `created_by_admin_id` | bigint |  | → [[app_user]] |
| `published_at` | timestamptz | NOT NULL |  |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `school_id, external_id · 단, (external_id IS NOT NULL)`

**이 표를 참조하는 표** — [[school_notice_read]]

## 얽힌 결정 2개

- [[drop-admin-user|admin_user 를 없애고 app_user.is_admin 하나로 접는다]]
- [[school-info-write-revoked|학사일정·공지의 쓰기 권한이 열려 있었다]]

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql` · `db/rls/school_info.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
