---
title: 원천의 삭제는 BigQuery 로 전파하지 않는다
date: 2026-07-30
group: 파이프라인
status: active
tags: [결정, 파이프라인]
---

# 원천의 삭제는 BigQuery 로 전파하지 않는다

**결정** — 증분 MERGE 는 INSERT 와 UPDATE 만 한다. Postgres 에서 행이 지워져도
BigQuery raw 에는 남는다.

**이유** — raw 층의 일은 **원천에서 일어난 일을 잃지 않는 것**이다. 탈퇴나
`db/reset_users.py` 로 사라진 유저도 그때까지의 활동은 분석 대상이다.
삭제까지 따라가면 "왜 그만뒀는가"를 물을 데이터 자체가 없어진다.

**대안** — 원천에 없는 행을 지우는 `WHEN NOT MATCHED BY SOURCE THEN DELETE`.
기각. 증분으로 뽑은 일부 행만 들고 이 판단을 하면 멀쩡한 행을 지운다.

**영향** — `verify_load.py` 가 부족(`pg > bq`)과 잉여(`pg < bq`)를 구분해서
보고한다. 부족은 결함이고, 잉여는 삭제 이력이라 정상이다.

---

`2026-07-30` · [[DECISIONS|결정 이력]] 으로 돌아가기
