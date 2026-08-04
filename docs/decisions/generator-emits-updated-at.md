---
title: `updated_at` 을 생성기가 직접 싣는다 — 백필 UPDATE 가 3시간을 먹었다
date: 2026-08-04
group: 파이프라인
status: active
tags: [결정, 합성데이터, 파이프라인]
---

# `updated_at` 을 생성기가 직접 싣는다 — 백필 UPDATE 가 3시간을 먹었다

**결정** — 생성기가 CSV 에 `updated_at` 을 **직접 실어 넣는다.**
적재 후 `96_backfill_updated_at.sql` 이 고칠 것이 없어진다.
**96번은 지우지 않고 안전망으로 남긴다.**

**이유** — [[backfill-updated-at]] 이 정한 대로 적재 후 UPDATE 로 되돌려
왔는데, 1억 4,126만 행 규모에서 그 작업 하나가 **3시간**을 넘겼다.

원인은 행 수가 아니라 **인덱스**였다.

| `vote_candidate` 인덱스 | 크기 |
|---|---|
| `uq_vcandidate` | 4,739 MB |
| `vote_candidate_pkey` | 3,376 MB |
| **`idx_vote_candidate_updated`** | **1,282 MB** |
| `idx_vcandidate_user` | 935 MB |
| `uq_vcandidate_chosen` | 655 MB |

**갱신하는 컬럼(`updated_at`) 위에 인덱스가 걸려 있는데 그 컬럼을 7,881만 번
고치고 있었다.** 값이 바뀌니 인덱스에서 옛 자리를 지우고 새 자리에 넣는 일이
매 행 발생하고, 나머지 인덱스 4개에도 새 항목이 들어간다 —
**본체 1번 쓸 때 인덱스 5번**이다. WAL 이 초당 88MB 로 나갔다.

## 왜 이 방법이 되는가

`updated_at` 트리거는 **`BEFORE UPDATE`** 에만 걸려 있다
(`004_updated_at_watermark.sql`). INSERT 로 들어온 값은 덮이지 않는다.
따라서 COPY 로 실어 넣으면 그대로 살아남는다.

`vote_candidate` 와 `meal_menu_item` 은 자기 시각 컬럼이 없어 **부모의 시각을
물려받는다**(각각 `vote_item.served_at` · `meal_plan.created_at`).

**대안** — 백필 동안 인덱스를 지웠다 다시 만드는 안도 검토했다. PK·UNIQUE 는
FK 가 참조해 지울 수 없어 **11GB 중 2.2GB(20%)만** 지울 수 있다. 효과가 작다.

**영향**

- 백필이 사실상 0초가 된다 — 조건이 `WHERE updated_at <> src` 라 고칠 행이 없다.
- 실측: `vote_item` · `user_session` · `heart_transaction` 세 표에서
  **원본 시각과 불일치 0건**.
- 96번을 남긴 이유 — 나중에 `updated_at` 이 있는 표가 새로 생겼는데 생성기
  목록에 안 넣으면 **조용히 메워준다.** 이미 맞는 행은 건너뛰므로 비용이 0이다.
- CSV 가 커진다(행당 약 26바이트). 1억 8,826만 행에서 **7.4GB → 15GB.**

## 적재 최적화도 함께

- **COPY 전에 제약을 안 받치는 인덱스 80개를 지우고** 백필 뒤 다시 만든다.
  실패해도 되살릴 수 있게 **복구 DDL 을 먼저 출력**한다.
- **CSV 를 바이너리 모드로 읽는다.** 텍스트 모드는 파이썬이 UTF-8 을 문자열로
  디코딩하고 psycopg 가 다시 인코딩해 **15GB 를 두 번 변환**한다 — 적재 중
  Postgres 는 `Client/ClientRead` 로 놀고 파이썬만 코어의 69%를 쓰고 있었다.

실측: 행이 33% 늘었는데 적재 시간은 **2시간 57분 → 2시간 38분**으로 줄었다.

## 이어지는 결정
- [[backfill-updated-at|대량 적재 후 `updated_at` 을 각 행의 원래 시각으로 되돌린다]]
  — 같은 문제의 두 해법 — 적재 뒤 고치기(옛것) vs 처음부터 맞게 넣기(새것)
- [[row-cap-to-query-cap|행수 상한을 버리고 쿼리 하드캡으로 바꾼다]]
  — 둘 다 **규모가 커지자 드러난** 문제다. 작은 샘플에서는 보이지 않았다

## 이어지는 결정
- [[backfill-updated-at|대량 적재 후 `updated_at` 을 각 행의 원래 시각으로 되돌린다]]
  — 같은 문제의 두 해법 — 적재 뒤 고치기(옛것) vs 처음부터 맞게 넣기(새것)
- [[row-cap-to-query-cap|행수 상한을 버리고 쿼리 하드캡으로 바꾼다]]
  — 둘 다 **규모가 커지자 드러난** 문제다. 작은 샘플에서는 보이지 않았다
