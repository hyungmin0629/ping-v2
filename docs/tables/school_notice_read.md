---
title: school_notice_read
domain: 학교 정보
kind: activity
rows: 0
tags: [테이블, 학교 정보]
---

# school_notice_read · 공지 열람 기록

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**학교 정보** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **0행**

> **비어 있다 — 화면이나 실행 코드가 없다.** 공지가 없으니 따라서 빈다

## 왜 이렇게 생겼나

어떤 공지가 실제로 읽히는지 측정해 알림 정책을 조정한다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `notice_id` | bigint | NOT NULL | → [[school_notice]] |
| `user_id` | bigint | NOT NULL | → [[app_user]] |
| `read_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `notice_id, user_id`

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql`

## 합성 데이터

⚠️ **생성기가 아직 만들지 않는다.** 합성 데이터를 채우려면 새로 써야 한다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
