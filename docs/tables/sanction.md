---
title: sanction
domain: 신고와 제재
kind: activity
rows: 0
tags: [테이블, 신고와 제재]
---

# sanction · 제재

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**신고와 제재** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **0행**

> **비어 있다 — 화면이나 실행 코드가 없다.** 제재를 내리는 경로가 없다. 신고가 PENDING 으로 고인다

## 왜 이렇게 생겼나

triggered_by_report_id 로 근거 신고를 명시한다. 이 연결이 구 시스템에는 아예 없었다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `user_id` | bigint | NOT NULL | → app_user |
| `type` | sanction_type | NOT NULL |  |
| `triggered_by_report_id` | bigint |  | → report |
| `policy_id` | bigint |  | → sanction_policy |
| `issued_by_admin_id` | bigint |  | → app_user |
| `reason` | varchar(200) | NOT NULL |  |
| `starts_at` | timestamptz | NOT NULL |  |
| `ends_at` | timestamptz |  |  |
| `is_active` | boolean | NOT NULL |  |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |

## 얽힌 결정 2개

- [[drop-admin-user|admin_user 를 없애고 app_user.is_admin 하나로 접는다]]
- [[report-sanction-fk|신고와 제재를 FK로 연결하고 정책을 데이터로 정의]]

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql`

## 합성 데이터

⚠️ **생성기가 아직 만들지 않는다.** 합성 데이터를 채우려면 새로 써야 한다.

---

[[index|위키 색인]] · [[erd|ERD]] · 정의는 `db/ddl/` 이 진실이다
