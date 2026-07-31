---
title: BigQuery 적재
group: 운영
tags: [운영, 참조]
---

# BigQuery 적재

> `CLAUDE.md` 에서 뺀 참조 문서다. 요약과 경고는 거기 남아 있고,
> 여기에는 **실제로 그 작업을 할 때 필요한 값과 절차**가 있다.


| 항목 | 값 |
|---|---|
| 프로젝트 | `ping-v2-503916` · 리전 `asia-northeast3` |
| 데이터셋 | `raw` (원본 보존) · `stg`·`mart` 는 P6 |
| 인증 | 서비스 계정 `airflow-loader` · 키는 `credentials.json` (커밋 금지) |
| 결제 | **연결돼 있다.** 데이터셋·테이블에 만료 설정이 없는 것으로 확인(2026-07-30) |

- 저장 10GiB · 쿼리 1TiB/월 까지 무료다. 현재 raw 전체가 **450MB** 라 한도의 5% 미만.
  다만 결제가 붙어 있으면 한도를 넘을 때 막히지 않고 **과금된다.** 예산 알림을 걸어둔다.
- GCS 를 경유하지 않는다. 파이썬이 행을 JSON 으로 만들어 BigQuery API 에 직접 올린다.
  `.env` 의 `GCS_BUCKET` 은 비어 있어도 된다. 이 규모에서 버킷은 설정만 늘린다.
- 실유저와 합성 데이터가 **같은 테이블**에 들어간다. 둘 다 id 가 1부터라
  `_source` 컬럼으로 키를 나눈다 — 실유저만 보려면 `WHERE _source = 'supabase'`.
- 적재 방식(full / incremental)은 `pipeline/tables.yaml` 이 정한다.
- **원천의 삭제는 행을 지우지 않고 `_deleted_at` 으로 표시한다.**
  raw 는 이력을 잃지 않는다. 대신 **분석 쿼리에는 `_deleted_at IS NULL` 을 반드시 넣는다** —
  안 넣으면 지운 계정과 그 활동이 오늘 것으로 셈해진다(2026-07-30 에 실제로 물렸다).
  실유저 원천에서만 표시한다. 합성은 재생성이 `--full-refresh` 라 유령이 안 생긴다.
- 정기 적재: `docker compose -f airflow/docker-compose.yml up -d` → http://localhost:8080

### 증분 적재의 함정 (2026-07-30 점검에서 실제로 걸린 것들)

- ⚠️ **분석 조인에는 `_source` 를 반드시 넣는다.** 두 원천의 id 가 실제로 겹친다
  — `app_user` 16개, `vote_item` 26개. `JOIN ... USING(id)` 만 쓰면 실유저와
  합성이 조용히 섞인다. P6 stg 층에서 대리키를 만들어 이 실수를 막아야 한다.
- ⚠️ **스키마를 바꿔도 워터마크는 움직이지 않는다.** `ALTER TABLE ADD COLUMN` 은
  트리거를 발동시키지 않아 `updated_at` 이 그대로다. 증분은 아무것도 못 잡고
  새 컬럼이 NULL 로 남는다. 실제로 `vote_item.padded_count` 가 합성 803,187행
  전부 NULL 이었다. **컬럼을 추가한 뒤에는 그 테이블을 `--full-refresh` 한다.**
- ⚠️ **값을 과거 시각으로 되돌리는 변경도 증분이 못 잡는다.**
  `96_backfill_updated_at.sql` 이 그렇다. 돌린 뒤에는 `--full-refresh` 한다.
- 워터마크는 스냅샷 시각보다 **5분 뒤로 물려** 저장한다. 그래야 적재 중에
  커밋된 트랜잭션이 영영 누락되지 않는다. 경위는 [[watermark-lag-5min]].

---

[[CLAUDE|CLAUDE.md]] 로 돌아가기
