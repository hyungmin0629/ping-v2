---
title: 대시보드가 스테이징을 넷 늘린다
date: 2026-08-18
group: 파이프라인
status: active
tags: [결정, 파이프라인, BigQuery, 분석]
---

# 대시보드가 스테이징을 넷 늘린다

**결정** — `stg` 에 뷰 넷을 더하고(`stg_vote_session` · `stg_vote_received` ·
`stg_friend_edge` · `stg_report`) `stg_user` 에 `region` 을 조인해 `sido`·`sigungu`
를 싣는다. 그 안에서 세 가지를 함께 정했다.

- **친구 관계는 유저 관점으로 편다.** 관계 1건 = 두 행. 이름도 `friendship` 이
  아니라 `friend_edge` 로 둔다
- **`voter_id`("누가 나를 뽑았나")는 싣지 않는다**
- **에이징(며칠째 미해결인가)은 stg 가 계산하지 않는다.** 마트가 시각을 정한다

**이유** — 루커 스튜디오 대시보드 스케치 5쪽 중 **2·3·5쪽을 기존 6개 뷰로는 그릴 수
없었다.** 수신 투표·신고·친구 관계가 stg 에 아예 없었고, 좌측 지역 필터가 기댈
`region` 조인이 `stg_user` 에 없었다. raw 에는 다섯 표 모두 이미 올라와 있어
(`pipeline/tables.yaml`) 적재는 손댈 것이 없고 뷰만 쓰면 됐다.

셋을 그렇게 정한 이유는 각각 다르다.

- **친구를 유저 관점으로 펴는 이유**는 `friendship` 이 두 사람을
  `user_low_id < user_high_id` 로 **정렬해서** 저장하기 때문이다
  (`db/ddl/20_social.sql` 의 `ck_friendship_order`). 한쪽 컬럼만 세면 **친구 수가
  정확히 절반**이 되고, id 가 작은 사람에게만 친구가 있는 것처럼 보인다.
  오류는 나지 않는다 — stg 층이 막아야 하는 전형적인 실수다
- **`voter_id` 를 빼는 이유**는 그것이 앱에서 하트를 받고 파는 유료 정보라
  `vote_received` 직접 접근을 막고 `my_vote_received` 뷰로만 노출하기 때문이다.
  `stg_user` 가 닉네임·초대코드를 뺀 것과 같은 기준이고, **대시보드가 쓰지 않는다**
- **에이징을 stg 에서 빼는 이유**는 뷰가 조회할 때마다 다시 계산되기 때문이다.
  "7일 이상 미해결 8,898건"이 조회 시각마다 달라지면 화면에 적힌 숫자의 기준 시점을
  알 수 없다. 자르는 시각은 마트가 정하고 `as_of_date` 로 함께 싣는다

**대안** — 마트에서 매번 조인하는 방법을 기각했다. 친구 양방향 explode 와
`_source` 동봉을 쿼리마다 다시 쓰게 두면 언젠가 한 곳이 빠지고, 그때 틀리는 방식이
**오류가 아니라 조용한 절반**이다. `stg_friendship`(관계 그레인)으로 두고 마트가
`UNION ALL` 하는 안도 기각했다 — 실수를 막는 자리가 층 하나 뒤로 밀릴 뿐이다.

**영향**

- `bigquery/staging/` 이 6개 → **10개**. 번호가 실행 순서라 사이에 끼워 넣었다
  (`25_` · `35_` · `70_` · `80_`)
- 확인: `stg_friend_edge` 795,656행 = `friendship` 397,828행 **× 2** ·
  `stg_user.sido` NULL 0건(local 10개 시도)
- **실측 중 결함이 하나 드러났다** — [[synthetic-reveal-status-not-updated]]

## 관련

- 왜 이 층이 필요한가 — [[ops-p5-p7]]
- 표준 필터와 갭 3건 — [[ops-analysis-conventions]]
- 끊긴 관계를 남기는 이유 — [[friendship-ended-at]]
