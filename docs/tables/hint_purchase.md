---
title: hint_purchase
domain: 질문과 투표
kind: activity
rows: 144
tags: [테이블, 질문과 투표]
---

# hint_purchase · 힌트 구매

> 생성물이다. `python db/wiki_tables.py` 가 DDL·결정·검사·정책에서 모아 만든다.
> **손으로 고치지 않는다** — 고칠 것이 있으면 원본을 고친다.

**질문과 투표** · 활동 — 사람이 쓰면 쌓인다 · 실데이터 **144행**

## 왜 이렇게 생겼나

⚠️ **아래 정의는 최초 설계이고, W14(마이그레이션 006·007)가 갈아치웠다.** 이 파일만 읽으면 죽은 요금제를 현행으로 오해한다. 현행은 이렇다: 기본 5종 (GENDER·INITIAL·MEDIAL·FINAL·CLASS) · 각 20하트 · 순서 없음 FULL_NAME  이름 공개 · 100하트 · 기본 5종 중 3개 이상을 연 뒤에만 GENDER 는 광고로도 열 수 있다(하루 1회) → heart_cost = 0 인 행이 생긴다 값이 흩어지면 어긋나므로 요금은 db/rls/hints.sql 의 hint_cost() 하나가 정한다. 해금 기준은 같은 파일의 hint_unlock_min(). 무엇이 바뀌었나 — 아래 컬럼 정의를 그대로 읽으면 안 되는 이유: step        누진 단계(1~4)가 아니라 **몇 번째로 열었나**(1~6)로 뜻이 바뀌었다 heart_cost  > 0 이 아니라 >= 0 이다 (광고로 연 힌트가 0) uq_hint_step  (vote_received_id, step) → uq_hint_kind (vote_received_id, hint_type) 순서가 자유로워졌으니 "같은 단계 두 번"이 아니라 **같은 유형 두 번**을 막아야 한다 char_index  007 이 붙인다. 자모 힌트가 가리키는 글자 위치이며, 006 과 달리 **힌트 한 건마다 따로** 뽑는다 ad_impression_id  006 이 붙인다. 광고로 열었으면 그 광고, 하트로 샀으면 NULL ⚠️ 분석에서 매출·소비를 셀 때 heart_cost = 0 행(광고 무료 힌트)을 거를 것. 정합성 검사 4번이 이걸 전제로 고쳐져 있다. 구 서비스의 누진 요금(200 → 300 → 500 → 1000)은 **벤치마크로도 쓰지 않는다.** 단가가 10배 달라 하트 경제 전체가 다른 체제다 — 생성기가 투표 적립을 실측 5~15 에서 2~7 로 낮춘 것도 같은 이유다(synthetic-v2.yaml). 하트 차감은 heart_transaction 이 이 행을 참조하는 단방향 구조.

## 컬럼

| 이름 | 타입 | NULL | 키 |
|---|---|---|---|
| `id` | bigint | NOT NULL | **PK** |
| `vote_received_id` | bigint | NOT NULL | → [[vote_received]] |
| `user_id` | bigint | NOT NULL | → [[app_user]] |
| `hint_type` | hint_type | NOT NULL |  |
| `step` | smallint | NOT NULL |  |
| `heart_cost` | integer | NOT NULL |  |
| `created_at` | timestamptz | NOT NULL |  |
| `updated_at` | timestamptz | NOT NULL |  |
| `ad_impression_id` | bigint |  | → [[ad_impression]] |
| `char_index` | smallint |  |  |

**UNIQUE** — `vote_received_id, hint_type` · `ad_impression_id · 단, (ad_impression_id IS NOT NULL)`

**이 표를 참조하는 표** — [[heart_transaction]]

## 얽힌 결정 3개

- [[ddl-comments-rot-with-migrations|DDL 주석은 마이그레이션 뒤에 낡는다 — 파일이 아니라 순서가 진실이다]]
- [[remove-circular-fk|순환 FK를 제거하는 방향으로 스키마 정리]]
- [[synthetic-reveal-status-not-updated|이름 공개는 reveal_status 가 아니라 hint_type 으로 센다]]

## 이 표를 지키는 정합성 검사 1종

`qa/checks/integrity.sql` · 위반 0이어야 한다.

- 원장 없는 유료 힌트 구매

## 이 표를 다루는 정책·RPC

`db/rls/hints.sql` · `db/rls/policies.sql` · `db/rls/received.sql`

## 합성 데이터

생성기가 만든다.

---

정의는 `db/ddl/` 이 진실이다 · [[index|위키 색인]]
