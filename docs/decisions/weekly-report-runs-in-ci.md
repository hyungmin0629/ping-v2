---
title: 주간 보고서는 로컬 Airflow 가 아니라 GitHub Actions 에서 돌린다
date: 2026-08-25
group: 인프라
status: active
tags: [결정, 인프라, 파이프라인, 보고서]
---

# 주간 보고서는 로컬 Airflow 가 아니라 GitHub Actions 에서 돌린다

**결정** — 매주 나가는 PDF 보고서는 `.github/workflows/weekly-report.yml` 이
만든다. 월요일 05:30 KST(일 20:30 UTC)에 **적재 → 대조 → 품질 → 마트 →
수집 → 렌더 → Drive 업로드**를 한 번에 돈다. 로컬 Airflow 에는 DAG 을
추가하지 **않는다.**

**이유** — 요구가 "손대지 않아도 계속 유지되는 발송"이다. 로컬 Airflow 는
이 PC 와 Docker Desktop 이 켜져 있을 때만 돈다. 실제로 2026-08-25 에
확인했을 때 Docker 가 꺼져 있었고 raw 워터마크가 **5일 밀려 있었다.**
같은 상태로 월요일 새벽을 맞으면 보고서는 나오지 않거나, 더 나쁘게는
**며칠 전 숫자로 나온다.** 실행 주체가 PC 밖에 있어야 한다.

비용은 0 이다. 프라이빗 저장소 무료 실행 시간 안이고 주 1회 몇 분이다.
BigQuery 스캔도 보고서 쿼리 0.18 GiB + 마트 빌드뿐이라 무료 한도에 닿지 않는다.

**적재까지 CI 가 하는 이유** — 보고서만 CI 로 옮기면 마트가 언제 것인지
모르는 채로 그림만 최신이 된다. 대시보드는 숫자가 틀려도 예쁘게 나온다.
Supabase 도 BigQuery 도 클라우드라 러너에서 그대로 닿는다.

**대안**

| 기각 | 왜 |
|---|---|
| 로컬 Airflow DAG | PC 의존. 지금 요구를 못 채운다 |
| Windows 작업 스케줄러 | 같은 PC 의존 + 실패가 눈에 안 띈다 |
| Cloud Composer | 월 40만원대. 이미 기각된 선택지다 |
| Cloud Run Jobs + Scheduler | 무료 한도 안이지만 배포 파이프라인이 하나 더 생긴다. 저장소에 이미 있는 CI 로 충분하다 |
| 두 곳에서 다 돌리기 | 마트를 동시에 구우면 서로 덮는다. 굽는 곳은 하나여야 한다 |

**영향**

- 비밀 세 가지가 GitHub Secrets 로 간다 — `SUPABASE_DB_URL` · `GCP_SA_KEY` ·
  `GDRIVE_TOKEN_JSON`. **저장소가 프라이빗이라는 전제 위에 있다.**
- 로컬 `ping_raw_load` · `ping_mart_build` DAG 은 그대로 둔다. PC 가 켜져 있는
  날은 매일 돌아 대시보드가 더 자주 갱신된다. 마트는 `CREATE OR REPLACE` 라
  두 곳에서 구워도 결과가 같다.
- ⚠️ **스케줄 워크플로는 저장소가 60일간 조용하면 GitHub 이 끈다.** 끄기 전에
  메일이 온다. 커밋이 이어지는 동안은 걸리지 않는다.
- 실패하면 GitHub 이 저장소 소유자에게 메일을 보낸다. 별도 알림 장치를
  만들지 않은 이유다.

절차는 [[ops-weekly-report]], 숫자를 어떻게 다루는지는
[[weekly-report-suppresses-small-denominators]].
