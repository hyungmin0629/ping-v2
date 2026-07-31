---
title: Cloud Composer 대신 로컬 Docker Airflow
date: 2026-07-29
group: 인프라
status: active
tags: [결정, 인프라]
---

# Cloud Composer 대신 로컬 Docker Airflow

**결정** — 관리형 Airflow를 쓰지 않는다.

**이유** — Cloud Composer는 최소 구성도 월 40만원대다. 학습·포트폴리오 목적에 비해 비용이 과하다.
로컬 Docker면 0원이고, 나중에 필요하면 작은 VM(월 3~4만원)으로 옮기면 된다.

**영향** — 스케줄이 PC가 켜져 있을 때만 돈다. 실서비스 운영에는 부적합하지만 현재 범위에서는 문제없다.

---

`2026-07-29` · [[DECISIONS|결정 이력]] 으로 돌아가기
