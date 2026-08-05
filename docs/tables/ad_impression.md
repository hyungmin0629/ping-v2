---
title: ad_impression
domain: 질문과 투표
kind: activity
rows: 24
tags: [테이블, 질문과 투표]
---

# ad_impression · 광고 시청

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**질문과 투표** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **24행**

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `user_id` | bigint | NOT NULL | → [[app_user]] |
| `placement` | ad_placement | NOT NULL |  |
| `ad_network` | varchar(30) | NOT NULL |  |
| `ad_unit_id` | varchar(60) | NOT NULL |  |
| `status` | ad_status | NOT NULL |  |
| `started_at` | timestamptz | NOT NULL |  |
| `completed_at` | timestamptz |  |  |
| `updated_at` | timestamptz | NOT NULL |  |

**이 표를 참조하는 표** — [[heart_transaction]] · [[hint_purchase]] · [[vote_shuffle]]

## 얽힌 결정 3개

- [[ads-payments-stub|MVP에서 광고와 결제를 스텁으로 처리]]
- [[heart-economy-rebalance|하트 경제를 다시 잡는다 — v1 실측을 버린다]]
- [[lognormal-not-uniform|시간 간격을 균등분포에서 로그정규로 바꾼다 — v5]]

## 이 표를 지키는 정합성 검사 1종

`qa/checks/integrity.sql` · 위반 0이어야 한다.

- 광고 미완료 셔플

## 이 표를 다루는 정책·RPC

`db/rls/hints.sql` · `db/rls/policies.sql` · `db/rls/voting.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
