---
title: vote_candidate
domain: 질문과 투표
kind: activity
rows: 3000
tags: [테이블, 질문과 투표]
---

# vote_candidate · 후보 (아이템당 4명)

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**질문과 투표** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **3,000행**

## 왜 이렇게 생겼나

구 스키마는 세트↔피스 관계를 JSON 배열로만 들고 있었다. 행으로 저장한다. shuffle_round: 0 = 최초 후보, 1 = 셔플 후 후보. 둘 다 보존해 "어떤 후보였을 때 셔플했는가"를 분석할 수 있게 한다. is_chosen: 선택된 후보 표시. 아이템당 1명만 true (부분 유니크 인덱스로 강제).

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `vote_item_id` | bigint | NOT NULL | → [[vote_item]] |
| `candidate_user_id` | bigint | NOT NULL | → [[app_user]] |
| `shuffle_round` | smallint | NOT NULL |  |
| `slot` | smallint | NOT NULL |  |
| `is_chosen` | boolean | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `vote_item_id, shuffle_round, slot` · `vote_item_id · 단, is_chosen`

## 얽힌 결정 8개

- [[backfill-updated-at|대량 적재 후 `updated_at` 을 각 행의 원래 시각으로 되돌린다]]
- [[bulk-load-batch-rows|합성 대량 적재는 배치를 20만 행으로 키운다]]
- [[candidate-rows-kept|후보 4명을 행으로 저장하고 셔플 전후를 모두 남긴다]]
- [[generator-emits-updated-at|`updated_at` 을 생성기가 직접 싣는다 — 백필 UPDATE 가 3시간을 먹었다]]
- [[partition-ordered-extract|파티션 테이블로 부을 때는 파티션 컬럼 순서로 꺼낸다]]
- [[remove-circular-fk|순환 FK를 제거하는 방향으로 스키마 정리]]
- [[row-cap-to-query-cap|행수 상한을 버리고 쿼리 하드캡으로 바꾼다]]
- [[watermark-updated-at|증분 워터마크를 `updated_at` 하나로 통일한다]]

## 이 표를 지키는 정합성 검사 6종

`qa/checks/integrity.sql` · 위반 0이어야 한다.

- 선택 없는 완료 투표
- 후보 4명이 아닌 라운드
- 친구 아닌 후보
- CLASS 스코프에 설명 안 되는 타반 후보
- SCHOOL 스코프에 설명 안 되는 타교 후보
- 자기 자신이 후보

## 이 표를 다루는 정책·RPC

`db/rls/policies.sql` · `db/rls/received.sql` · `db/rls/replies.sql` · `db/rls/voting.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
