---
title: timetable
domain: 학교 정보
kind: reference
rows: 0
tags: [테이블, 학교 정보]
---

# timetable · 시간표

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**학교 정보** · 참조 — 외부(NEIS)에서 받아 채운다 · 실데이터 **0행**

> **비어 있다 — 화면이나 실행 코드가 없다.** 수집기 없음. 빌려 쓰는 조직의 학급 매핑이 미해결

## 왜 이렇게 생겼나

학급·학기·요일·교시에 UNIQUE → 한 칸에 두 과목이 들어갈 수 없다. 교사명은 마스킹해서 저장한다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `class_id` | bigint | NOT NULL | → [[grade_class]] |
| `semester` | varchar(10) | NOT NULL |  |
| `day_of_week` | smallint | NOT NULL |  |
| `period` | smallint | NOT NULL |  |
| `subject_name` | varchar(40) | NOT NULL |  |
| `teacher_name_masked` | varchar(20) |  |  |
| `room` | varchar(30) |  |  |
| `source` | data_source | NOT NULL |  |
| `is_manually_overridden` | boolean | NOT NULL |  |
| `synced_at` | timestamptz |  |  |
| `updated_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `class_id, semester, day_of_week, period`

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql`

## 합성 데이터

⚠️ **생성기가 아직 만들지 않는다.** 합성 데이터를 채우려면 새로 써야 한다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
