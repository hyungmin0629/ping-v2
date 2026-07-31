---
title: Airflow 는 공식 컴포즈 대신 2개 서비스로 줄인다
date: 2026-07-30
group: 인프라
status: active
tags: [결정, 인프라]
---

# Airflow 는 공식 컴포즈 대신 2개 서비스로 줄인다

**결정** — 공식 배포판 `docker-compose.yaml`(서비스 8개)을 쓰지 않고,
`standalone` + 메타DB 두 개만 띄운다 (`airflow/docker-compose.yml`).

**이유** — 공식 구성은 CeleryExecutor 를 전제한다(redis · worker · flower · triggerer).
**하루 한 번 42개 테이블을 옮기는 일**에 워커 큐는 필요 없고, 작업자가 개발
경험이 없어서 서비스가 8개면 어디가 죽었는지 판단할 수가 없다.

**대안** — SQLite 메타DB 로 더 줄인다. 기각. SequentialExecutor 로 묶여
병렬 실행이 아예 막힌다. Postgres 컨테이너 하나 더 띄우는 값이 그보다 싸다.

**영향**
- 적재 로직을 DAG 안에 두지 않고 `pipeline/` 의 스크립트를 부른다.
  Airflow 없이 같은 명령으로 돌릴 수 있어야 디버깅이 된다.
- 합성 데이터는 스케줄에 넣지 않는다. 한 번 만들어지고 변하지 않는다.
- 적재 뒤에 반드시 행 수를 대조한다(`verify_load.py`). 증분은 조용히 틀리기 때문에
  "오류가 안 났다"는 것이 성공의 증거가 되지 못한다.

## 이어지는 결정
- [[local-docker-airflow|Cloud Composer 대신 로컬 Docker Airflow]]
  — Airflow 를 이 프로젝트 크기로 줄인다

---

`2026-07-30` · [[DECISIONS|결정 이력]] 으로 돌아가기
