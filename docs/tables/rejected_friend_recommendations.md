---
title: rejected_friend_recommendations
domain: 친구
kind: activity
rows: 0
tags: [테이블, 친구]
---

# rejected_friend_recommendations · 친구 추천 거절

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**친구** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **0행**

> **비어 있다 — 기능은 살아 있는데 아직 아무도 안 했다.** ‘안 볼래’ 0회. W10 화면도 RPC 도 살아 있다

## 왜 이렇게 생겼나

★ 이름이 말하는 그대로다 — **거절만** 들어온다. 추천 자체는 저장하지 않는다. friend_suggestion 뷰가 그때그때 계산한다. 이 표에 행이 생기는 경로는 dismiss_suggestion() 하나뿐이고, 그건 "안 볼래"를 눌렀을 때다. reason : 무엇 때문에 추천됐던 사람을 거절했나. SAME_CLASS / SAME_SCHOOL / MUTUAL_FRIEND 만 쓴다. MUTUAL_CONTACT 는 연락처를 안 받아 v2로 미룬다. score  : ⚠️ 항상 0 이다. 추천 점수를 매기던 자리인데 거절만 들어오므로 채울 사람이 없다. 추천을 미리 계산해 저장하는 날 되살아날 자리다. 분석에서 쓰지 말 것.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `user_id` | bigint | NOT NULL | → [[app_user]] |
| `recommended_user_id` | bigint | NOT NULL | → [[app_user]] |
| `reason` | recommend_reason | NOT NULL |  |
| `score` | numeric(5,4) | NOT NULL |  |
| `created_at` | timestamptz | NOT NULL |  |
| `dismissed_at` | timestamptz |  |  |
| `updated_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `user_id, recommended_user_id`

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql` · `db/rls/recommend.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
