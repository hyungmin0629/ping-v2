---
title: 분석 쿼리 표준 — 노트북 4개에서 굳어진 규칙
date: 2026-08-13
group: 파이프라인
status: active
tags: [운영, 분석, BigQuery]
---

# 분석 쿼리 표준

`notebooks/` 의 acquisition · activation · retention · revenue 네 개에서
**이미 일관되게 쓰이고 있는 규칙**을 뽑아 적는다. 새로 정한 것이 아니라
**있는 것을 드러낸 것**이다. 마트(P6)는 이 규칙을 표에 구워 넣어, 쿼리마다
다시 쓰지 않아도 되게 만든다.

## 표준 필터 — 빠지면 조용히 틀린다

네 노트북 전부가 이렇게 쓴다. 넷 다 **오류가 안 나고 숫자만 틀리는** 종류다.

| 필터 | 왜 |
|---|---|
| `_source = 'local'` | **합성 v5 만 본다.** `'supabase'` 는 실유저(지인 20~50명)라 비율 지표가 노이즈다. 섞으면 둘 다 못 쓴다 |
| `_deleted_at IS NULL` | 지운 행의 유령. 증분 적재는 삭제를 소프트로 표시한다 ([[ops-bigquery]]) |
| 탈퇴자 제외 | `user_withdrawal` 에 `NOT EXISTS`. 네 노트북의 "유효 가입자" 정의가 사실상 이것 하나로 통일돼 있다 |
| `DATE(ts, 'Asia/Seoul')` | 저장은 UTC 다. 안 바꾸면 날짜 경계가 **9시간 밀린다** |
| 기간 고정 | `params` CTE 에 `2025-09-01` ~ `2026-07-23`. 관찰기간이 모자란 꼬리를 잘라낸다 |

## 실측 — 어디가 지켜지고 어디가 비었나

```
                _source  _deleted_at  Asia/Seoul  params  탈퇴제외
acquisition        7          15           1        -        4
activation        18          27           0        -        8
retention         35          40          44       21       11
revenue           32          32          14       17        6
```

**`_source`·`_deleted_at`·탈퇴 제외는 네 곳 다 완비**다. 아래 셋이 비어 있다.

### ⚠️ 1. activation 에 시간대 변환이 하나도 없다

`Asia/Seoul` 0회. 지금 쓰는 지표가 대부분 **일수 차이**(가입→해금 며칠)라
UTC 로 빼도 결과가 같아 드러나지 않는다. 하지만 **날짜로 자르는 순간**
— 코호트를 일 단위로 묶거나 "가입 당일 해금"을 세는 순간 — 9시간이 밀린다.
지금 틀린 게 아니라 **다음 한 줄에서 틀린다.**

### ⚠️ 2. 제재(BAN) 유저를 아무 데서도 안 거른다

`sanction` 참조 0회. 네 노트북 다 **탈퇴만** 걸렀다. 그런데 v5 에는
**제재 뒤에도 투표하는 유저가 34명** 있다([결정 이력](../synthetic-data-decision-history.pdf)).
탈퇴는 종점이라 그 뒤 로그가 안 남지만([[withdrawal-is-terminal]]),
**제재는 종점이 아니다.**

그래서 제재는 유저 단위가 아니라 **시각으로 잘라야 한다** —
"이 사람을 빼기"가 아니라 "`sanction.starts_at` 이후 행을 빼기"다.

### ⚠️ 3. 광고로 연 무료 힌트가 '구매'로 세어진다

`revenue.ipynb` 의 `hint_purchase_count` 는 `COUNT(DISTINCT hp.id)` 라
**`heart_cost = 0` 인 행까지 센다.** 그 행은 W14 의 광고 무료 힌트고,
생성 설정상 성별 힌트의 **30%** 가 이 경로다(`hint_gender_by_ad_ratio: 0.30`).

같은 셀의 `SUM(heart_cost)` 는 0 이 더해질 뿐이라 **멀쩡하다.** 즉 소비량은
맞고 **횟수만 부풀어 있다.** 정합성 검사 4번이 같은 이유로 고쳐졌다
([[integrity-checks-aged]]).

- 하트를 **낸** 힌트만: `heart_cost > 0`
- 광고로 **연** 힌트만: `ad_impression_id IS NOT NULL`

## 마트에 무엇을 굽나

위 규칙을 쿼리마다 다시 쓰게 두면 언젠가 한 곳이 빠진다. 마트에서 해결한다.

- **표준 필터 셋(`_source`·`_deleted_at`·탈퇴)은 마트 적재 시점에 적용**한다.
  마트에 들어온 행은 이미 걸러진 것으로 본다.
- **날짜 컬럼은 KST 로 미리 계산해 싣는다**(`activity_date`). 조회하는 쪽이
  시간대를 의식하지 않게 만드는 것이 목적이다. 원본 UTC 타임스탬프도 함께 둔다.
- **제재 시각을 유저 차원에 싣는다**(`sanctioned_at`). 없으면 매번 조인해야 하고,
  매번 조인해야 하면 언젠가 안 한다.
- **`heart_cost > 0` 여부를 힌트 팩트의 컬럼으로 둔다**(`is_paid_hint`).

## 관련

- 증분 적재의 함정 넷 — [[ops-bigquery]]
- 이 데이터로 할 수 없는 7가지 — 리포트 13장 ([[reports]])
- 지표 정의 — [[core-metrics-v1]]
