---
title: user_withdrawal
domain: 유저
kind: activity
rows: 0
tags: [테이블, 유저]
---

# user_withdrawal · 탈퇴 기록

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**유저** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **0행**

> **비어 있다 — 기능은 살아 있는데 아직 아무도 안 했다.** 탈퇴 0명. 전원 ACTIVE. W12 기능은 검증까지 끝났다

## 왜 이렇게 생겼나

구 스키마 최대 결함의 해소 지점. accounts_userwithdraw 는 70,764건(가입자의 10.5%)이었지만 유저 식별자가 없어 이탈 원인 분석이 원천 불가능했다. user_id 를 NOT NULL 로 두고 자유 서술까지 받아 "기타 57%" 블랙박스를 연다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `user_id` | bigint | NOT NULL | → [[app_user]] |
| `reason_code` | varchar(30) | NOT NULL | → [[withdrawal_reason]] |
| `reason_text` | varchar(500) |  |  |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `user_id`

## 얽힌 결정 2개

- [[withdraw-keeps-rows|계정 삭제는 행을 지우지 않는다]]
- [[withdrawal-user-id|탈퇴 기록에 유저 식별자를 넣는다]]

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql` · `db/rls/withdraw.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
