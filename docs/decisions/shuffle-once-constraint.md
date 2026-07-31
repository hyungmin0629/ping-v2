---
title: 셔플은 DB 제약으로 1회를 강제한다
date: 2026-07-29
group: 투표
status: active
tags: [결정, 투표]
---

# 셔플은 DB 제약으로 1회를 강제한다

**결정** — `vote_shuffle.vote_item_id`에 UNIQUE, `ad_impression_id`는 NOT NULL FK.

**이유** — "셔플 1회, 광고 시청 필수"를 애플리케이션 코드로만 막으면 우회 경로가 생긴다.
스키마로 막으면 코드에 버그가 있어도 데이터가 오염되지 않는다.

**영향** — 광고를 보지 않고 셔플한 기록은 구조적으로 존재할 수 없다.

---

`2026-07-29` · [[DECISIONS|결정 이력]] 으로 돌아가기
