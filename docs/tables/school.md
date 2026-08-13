---
title: school
domain: 기준 정보
kind: reference
rows: 5725
tags: [테이블, 기준 정보]
---

# school · 학교

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**기준 정보** · 참조 — 외부(NEIS)에서 받아 채운다 · 실데이터 **5,725행**

## 왜 이렇게 생겼나

구 스키마에는 학교 이름 컬럼이 아예 없었다. 마스킹된 이름을 저장한다. neis_school_code 는 NEIS 공개 API 연동 키. ⚠️ **이 컬럼 하나로는 API 를 부를 수 없다.** 급식·시간표·학사일정 API 는 시도교육청코드 + 표준학교코드를 **한 쌍**으로 요구한다. 짝이 되는 neis_office_code 를 마이그레이션 001 이 붙인다 — 아래 정의에는 없다. 지역명으로 유추하면 안 된다. 소재지와 관할 교육청이 다른 학교가 있고, 틀린 값으로 부르면 오류가 아니라 **조용히 빈 결과**가 온다. ⚠️ info_school_id 도 마이그레이션 002 가 붙인다. 실제 학교가 아닌 조직 (클로즈드 테스트의 "코드잇 DA 14기")이 다른 학교의 급식·학사일정을 빌려 쓰게 하는 자리다. 부를 때는 coalesce(info_school_id, id) 를 쓴다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `name_masked` | varchar(50) | NOT NULL |  |
| `region_id` | bigint | NOT NULL | → [[region]] |
| `school_type` | school_type | NOT NULL |  |
| `neis_school_code` | varchar(20) |  |  |
| `student_count` | integer | NOT NULL |  |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |
| `neis_office_code` | varchar(10) |  |  |
| `info_school_id` | bigint |  | → [[school]] |

**UNIQUE** — `neis_school_code`

**이 표를 참조하는 표** — [[grade_class]] · [[meal_plan]] · [[post]] · [[school]] · [[school_event]] · [[school_notice]]

## 얽힌 결정 4개

- [[backfill-updated-at|대량 적재 후 `updated_at` 을 각 행의 원래 시각으로 되돌린다]]
- [[ddl-comments-rot-with-migrations|DDL 주석은 마이그레이션 뒤에 낡는다 — 파일이 아니라 순서가 진실이다]]
- [[org-borrows-school-info|테스트 조직은 이름을 유지하고 실제 학교의 정보를 빌려 쓴다]]
- [[watermark-updated-at|증분 워터마크를 `updated_at` 하나로 통일한다]]

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql` · `db/rls/school_info.sql` · `db/rls/school_picker.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
