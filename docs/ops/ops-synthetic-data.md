---
title: 합성 데이터 만들기
group: 운영
tags: [운영, 참조, 합성데이터]
---

# 합성 데이터 만들기

> `CLAUDE.md` 에서 뺀 참조 문서다. 요약과 경고는 거기 남아 있고,
> 여기에는 **실제로 그 작업을 할 때 필요한 값과 절차**가 있다.

---

## ⚠️ 먼저 — `--config` 를 빼면 안 된다

```bash
python generator/generate.py --config synthetic-v2.yaml ...
```

빼면 옛 `distribution.yaml` 이 돈다. **오류 없이 옛 서비스를 그린다.**

| | `distribution.yaml` (옛것) | `synthetic-v2.yaml` (지금) |
|---|---|---|
| 만드는 표 | 26개 | **40개 전부** |
| 힌트 요금 | 누진 200→300→500→1000 | **20 × 5종 + 이름 100** |
| 유저 성향 | 없음 — 행동이 전부 독립 추첨 | **페르소나 6유형** |
| 활동 강도 | 기간과 무관 | **잔존 구간별** |

스키마가 맞아서 그냥 들어가고, 그 데이터로 하트 경제를 분석하면 답이 전부 틀린다.

---

## 3단계로 올린다

전체 규모는 한 번 돌리는 데 **1~2시간**이다. 분포가 틀린 걸 3단계에서 발견하면
그만큼 날아간다. 그래서 작게 시작한다.

| 단계 | 규모 | 목적 | 통과 조건 |
|---|---|---|---|
| **1** | `--users 500 --months 1 --schools 6` | 생성기가 도는가 | 정합성 17종 · 40표 전부 1행 이상 |
| **2** | `--users 2000 --months 3 --schools 20` | 분포가 그럴듯한가 | 컬럼 커버리지 · 목표 지표 |
| **3** | `--users 20000 --months 12 --schools 50` | 최종 | 게이트 전부 + BigQuery 적재 |

**1단계 실측** — 생성 10초 · 약 117만 행 · CSV 55MB
**2단계 실측** — 생성 52초 · 약 601만 행 · CSV 302MB
**3단계 추정** — 생성 ~12분 · 약 8,500만 행 · CSV 4.3GB
([[row-guardrail-measured]] 에 스케일링 근거)

---

## 절차

### 1. 로컬 DB 준비

```bash
docker run -d --name pgtest -e POSTGRES_PASSWORD=test -e POSTGRES_DB=pingv2 \
  -p 5433:5432 --shm-size=1g postgres:16
python db/apply.py --target local --yes
```

⚠️ `--shm-size=1g` 를 빠뜨리면 큰 데이터에 정합성 검사를 돌릴 때
`No space left on device` 로 죽는다. 디스크가 아니라 **공유메모리** 부족이다.

⚠️ 이미 스키마가 있는 DB 에 `apply.py` 를 다시 돌리면
`type "school_type" already exists` 로 멈춘다. 마이그레이션만 넣으려면
`docker exec -i pgtest psql -U postgres -d pingv2 -f - < db/migrations/0NN_*.sql`.

### 2. 생성

```bash
python generator/generate.py --config synthetic-v2.yaml \
  --users 500 --months 1 --schools 6 --out data/sample-1m
```

`--out` 을 주면 다른 폴더에 낸다. 안 주면 `data/synthetic/`.

산출물 두 가지 —
- `<out>/*.csv` — 표마다 하나
- `data/personas.json` — **페르소나 정답지. 분석자에게 주지 않는다.**
  `.gitignore` 에 들어 있다. 저장소에 올리면 주는 것과 같다.

### 3. 적재

```bash
python generator/load.py --in data/sample-1m --truncate
```

`95_resync_sequences.sql` 과 `96_backfill_updated_at.sql` 을 자동으로 실행한다.
둘 다 빠뜨리면 조용히 틀린다 — 앞은 이후 실유저 가입이 PK 충돌로 실패하고,
뒤는 모든 행의 `updated_at` 이 "적재한 순간"이 되어 BigQuery 파티션이 무의미해진다.

### 4. 검증

```bash
docker exec -i pgtest psql -U postgres -d pingv2 -f - < qa/checks/integrity.sql
```

17종 전부 0이어야 한다. 위반이 나오면 **생성기 결함**이다.

---

## 지표 확인 — 무엇을 봐야 하는가

정합성 검사는 "말이 되는가"만 본다. **"그럴듯한가"는 사람이 본다.**

| 지표 | 목표 | 왜 보나 |
|---|---|---|
| 친구 5명 해금 | **90~95%** | 100%면 게이트 퍼널이 없다 |
| 힌트 구매 유저 | **70~80%** | 100%면 "안 사는 사람"이 없다 |
| 받은 투표 0건 | **소수 존재** | 0명이면 "인기 없음"이라는 상태가 사라진다 |
| 상위 10% 지목 점유율 | **45%** | 균등하면 인기도 분석이 성립 안 함 |
| 세션 1회 이상 | **~96%** | 미접속은 4.1%뿐이어야 한다 |
| 소비/적립 | 구간별로 본다 | **평균 하나로 보면 안 된다** — [[heart-economy-rebalance]] |

### ⚠️ 우측 절단에 주의

받은 투표는 1~72시간 뒤에 열람된다. **기간 끝 3일치는 열람 시각이 관측 창을
넘어가 미열람으로 기록된다.** 실데이터에도 똑같이 생기는 현상이다.

열람률·답장률처럼 "나중에 일어나는 행동"의 비율을 낼 때는 **창 끝 3일을 제외**한다.
1개월 샘플에서 전체 41.8% / 마지막 3일 제외 53.9% 로 12%p 차이가 났다.

### 페르소나가 너무 또렷하지 않은지

각 행동 지표의 **상위 10%에 5개 이상 유형이 섞여** 있어야 한다.
한 유형이 독점하면 그 유형이 곧 그 행동이라는 뜻이라 분석할 것이 없다.
근거는 [[user-personas]].

---

## 자주 걸리는 것

| 증상 | 원인 |
|---|---|
| 새 설정 절을 넣었는데 그 생성기가 아무것도 안 만든다 | `load_config()` 의 복사 목록에 절 이름을 안 넣었다. **에러가 안 난다** |
| 힌트 구매가 대량으로 무산된다 | 잔액 부족이다. 헤비 유저의 미충족 수요이며 **정상**이다 |
| 표는 있는데 컬럼이 전부 NULL | 생성기가 그 컬럼을 안 쓴다. 커버리지 리포트로 확인 |
| BigQuery 재적재가 아무것도 안 올린다 | `_load_state` 워터마크가 남아 "이미 최신"으로 판단한다. `--full-refresh` |

---

## BigQuery 로 올릴 때

```bash
python pipeline/extract_load.py --source local --full-refresh
python pipeline/verify_load.py  --source local
```

`--full-refresh` 는 `_source='local'` 행만 지우고 다시 넣으므로
**실유저 데이터는 건드리지 않는다.**

⚠️ 위험은 저장이 아니라 **쿼리량**이다. Looker 를 raw 에 직접 붙이지 말 것.
자세한 것은 [[row-guardrail-measured]] · [[ops-bigquery]].
