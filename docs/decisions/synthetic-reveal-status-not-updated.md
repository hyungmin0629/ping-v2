---
title: 이름 공개는 reveal_status 가 아니라 hint_type 으로 센다
date: 2026-08-18
group: 투표
status: active
tags: [결정, 투표, 합성데이터, 분석]
---

# 이름 공개는 reveal_status 가 아니라 hint_type 으로 센다

**결정** — 힌트 퍼널의 마지막 단계("이름 공개")를 셀 때
`vote_received.reveal_status = 'REVEALED'` 를 쓰지 않는다.
**`hint_purchase.hint_type = 'FULL_NAME'`** 이 진실이다.
`stg_vote_received.is_name_revealed` 는 사실 그대로 싣되 퍼널에 쓰지 않는다.

**이유** — 2026-08-18 stg 를 세우고 실측하다 드러났다.

| | `reveal_status = 'REVEALED'` | `hint_type = 'FULL_NAME'` |
|---|---|---|
| 합성 v5 (`local`) | **0건** | 8,411건 · 4,921명 |
| 실유저 (`supabase`) | 10건 | 10건 |

**생성기가 이름 공개 힌트를 팔면서 `vote_received.reveal_status` 를 갱신하지 않는다.**
앱은 갱신한다 — 실유저 쪽이 10 대 10 으로 정확히 맞는 것이 그 증거다.
합성 쪽만 어긋나 있고, 두 원천을 함께 보지 않으면 드러나지 않는다.

`reveal_status` 로 퍼널을 세면 **합성 데이터에서 마지막 단계가 0 이 된다.**
차트는 멀쩡히 그려지고 "아무도 이름을 안 산다"는 틀린 결론만 남는다.

**대안** — 생성기를 고쳐 `reveal_status` 를 채우는 안은 **지금 하지 않는다.**
합성 v5 는 이미 BigQuery 에 1억 2,370만 행으로 올라가 있고, 이 컬럼 하나 때문에
재생성하면 다른 지표의 기준값이 전부 흔들린다. 다음 판본에서 [[app-follows-generator]]
의 다른 어긋남 둘과 **함께** 고친다.

**영향**

- `bigquery/staging/35_stg_vote_received.sql` 머리말에 경고를 남겼다
- `mart_funnel_step` 의 `vote_received` 퍼널 마지막 단계는 `stg_hint_purchase` 를 읽는다
- 앱과 생성기가 어긋난 곳이 **둘에서 셋으로** 늘었다 (투표 보상 · 일일 적립 상한 · 이 건)

## 관련

- 어긋난 것을 한 번에 고치기로 한 결정 — [[app-follows-generator]]
- 힌트 요금이 W14 로 바뀐 경위 — [[ddl-comments-rot-with-migrations]]
- 스테이징 뷰를 넷 늘린 결정 — [[stg-views-for-dashboard]]
