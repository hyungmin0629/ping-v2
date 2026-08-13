---
title: heart_transaction
domain: 하트
kind: activity
rows: 1400
tags: [테이블, 하트]
---

# heart_transaction · 하트 원장

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**하트** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **1,400행**

## 왜 이렇게 생겼나

이 프로젝트에서 가장 중요한 테이블. 구 스키마의 원장은 순합계가 201만인데 유저 잔액 총합은 20억이었다. 가입 지급과 충전이 원장에 남지 않았기 때문이다(heart.777이 57,873건 팔렸는데 원장의 +777 행은 21건뿐이었다). 잔액을 원장으로 재구성하는 것이 불가능했고, 누락을 탐지할 방법조차 없었다. 규칙: 모든 하트 증감은 예외 없이 이 테이블을 거친다. balance_after 로 거래 직후 잔액을 남겨 app_user.heart_balance 와 대조하면 정합성이 즉시 검증된다. source_* 컬럼은 이 거래의 원인을 가리키는 단방향 참조다. 유형에 따라 하나만 채워지며, 나머지는 NULL이다.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `user_id` | bigint | NOT NULL | → [[app_user]] |
| `type_code` | varchar(30) | NOT NULL | → [[heart_transaction_type]] |
| `delta` | integer | NOT NULL |  |
| `balance_after` | bigint | NOT NULL |  |
| `vote_item_id` | bigint |  | → [[vote_item]] |
| `hint_purchase_id` | bigint |  | → [[hint_purchase]] |
| `purchase_id` | bigint |  | → [[heart_purchase]] |
| `ad_impression_id` | bigint |  | → [[ad_impression]] |
| `admin_id` | bigint |  | → [[app_user]] |
| `memo` | varchar(200) |  |  |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |

**UNIQUE** — `hint_purchase_id · 단, (hint_purchase_id IS NOT NULL)` · `purchase_id · 단, (purchase_id IS NOT NULL)` · `ad_impression_id · 단, (ad_impression_id IS NOT NULL)`

## 얽힌 결정 10개

- [[client-write-minimal|클라이언트에 쓰기 권한을 거의 주지 않는다]]
- [[core-metrics-v1|핵심 지표를 10개로 고정하고, 마트를 거기서 역산한다]]
- [[drop-admin-user|admin_user 를 없애고 app_user.is_admin 하나로 접는다]]
- [[generator-emits-updated-at|`updated_at` 을 생성기가 직접 싣는다 — 백필 UPDATE 가 3시간을 먹었다]]
- [[heart-balance-after|모든 하트 증감에 `balance_after`를 기록]]
- [[heart-economy-rebalance|하트 경제를 다시 잡는다 — v1 실측을 버린다]]
- [[heart-unify-point|하트와 포인트를 하나로 통합]]
- [[partition-ordered-extract|파티션 테이블로 부을 때는 파티션 컬럼 순서로 꺼낸다]]
- [[remove-circular-fk|순환 FK를 제거하는 방향으로 스키마 정리]]
- [[signup-single-rpc|가입은 RPC 하나로만 한다]]

## 이 표를 지키는 정합성 검사 5종

`qa/checks/integrity.sql` · 위반 0이어야 한다.

- 하트 원장 vs 잔액 불일치
- 원장 누적합 오류
- 음수 잔액 발생
- 원장 없는 유료 힌트 구매
- 원장 없는 충전

## 이 표를 다루는 정책·RPC

`db/rls/hints.sql` · `db/rls/onboarding.sql` · `db/rls/policies.sql` · `db/rls/received.sql` · `db/rls/replies.sql` · `db/rls/topup.sql` · `db/rls/voting.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
