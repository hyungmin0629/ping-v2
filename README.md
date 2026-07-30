# ping-v2

학교 기반 소셜 투표 **웹서비스 MVP**와 그 위의 데이터 파이프라인.
구 서비스 DB의 구조적 결함을 닫은 스키마 위에 개인정보를 받지 않는 웹앱을 올리고,
거기서 나온 실데이터와 합성 데이터를 Airflow로 BigQuery까지 적재한다.

- 배포: https://ping-v2-lac.vercel.app (지인 대상 비공개 시험)

- **처음 clone 했다면 → [docs/ONBOARDING.md](docs/ONBOARDING.md)** (계정 없이 되는 데까지 20분)
- 프로젝트 컨텍스트 → [CLAUDE.md](CLAUDE.md)
- **팀 작업 계획 → [docs/TEAM-PLAN.md](docs/TEAM-PLAN.md)** (스키마를 바꿀 때 무엇이 깨지는가)
- 설계서 → [docs/design-spec.md](docs/design-spec.md)
- ERD → [docs/erd.md](docs/erd.md) · [docs/erd.json](docs/erd.json)
  (**생성물** — `python db/erd.py` 로 다시 뽑는다. json 은 카드형 ERD 가 읽는다)
- 결정 이력 → [DECISIONS.md](DECISIONS.md)

---

## 처음 시작할 때

> 아래는 요약이다. **처음이라면 [docs/ONBOARDING.md](docs/ONBOARDING.md) 를 보라**
> — 계정이 없어도 어디까지 되는지, 막히면 무슨 뜻인지가 함께 적혀 있다.

### 1. 로컬 DB 띄우기

```bash
docker run -d --name pgtest \
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=pingv2 \
  -p 5433:5432 --shm-size=1g postgres:16
```

> `--shm-size=1g` 를 빠뜨리지 말 것. 도커 기본값은 64MB 이고, 그 상태로 합성
> 786만 행에 정합성 검사를 돌리면 병렬 워커가
> `could not resize shared memory segment ... No space left on device` 로 죽는다.
> 디스크가 아니라 공유메모리 문제다.

### 2. 스키마 만들기

```bash
python db/apply.py --target local
```

`42`개 테이블이 나오면 정상이다.

> **`cat db/ddl/*.sql | psql` 로 만들지 말 것.** 그 경로에는 `db/migrations/` 가
> 빠져서 `neis_office_code` · `info_school_id` · `padded_count` 가 없는 반쪽
> 스키마가 나온다. 실제로 로컬 DB 가 이 상태로 3개 마이그레이션 뒤처져 있었고,
> 정합성 검사가 `padded_count` 를 못 찾아 통째로 실패했다(2026-07-30).
> `apply.py` 는 DDL 과 마이그레이션을 순서대로 다 적용한다.

> `70_deferred_v2.sql`은 **일부러 빼놓았다.** MVP에서 만들지 않는 테이블이다
> (연락처 동기화 — 전화번호를 받지 않기로 했다). 자세한 이유는 파일 안 주석 참조.

### 3. 환경변수 파일 만들기

```bash
copy .env.example .env
```

`.env`를 열어 값을 채운다. **`.env`는 커밋되지 않는다** (`.gitignore`에 등록됨).

### 4. 파이썬 환경

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 5. 웹앱 띄우기

```bash
cd web
npm install
npm run dev          # http://localhost:3000
```

`web/.env.local` 이 필요하다. 루트 `.env` 의 Supabase URL 과 **anon 키**만 옮겨 적는다
— service_role 키는 넣지 않는다.

---

## 폴더 구조

```
ping-v2/
├── CLAUDE.md              # 세션마다 로드되는 프로젝트 컨텍스트
├── DECISIONS.md           # 결정 이력 (왜 그렇게 했는가)
├── README.md              # 이 파일
├── .gitignore
├── .env.example           # 환경변수 서식 (실제 값은 .env 에)
├── requirements.txt       # 로컬 스크립트용 패키지
├── docs/
│   └── design-spec.md     # 통합 설계서
├── db/
│   ├── ddl/               # 테이블 생성 SQL (번호 순서대로 실행)
│   ├── rls/               # RLS 정책·가입 RPC + 침투 시험(verify.py)
│   └── migrations/        # 스키마 변경 이력
├── web/                   # Next.js 웹앱 (실유저가 쓰는 화면)
├── generator/             # 합성 데이터 생성
│   ├── config/            # 분포 파라미터 (yaml)
│   └── output/            # 생성 결과 (git 제외)
├── pipeline/              # Postgres → BigQuery 적재 (P4)
│   ├── tables.yaml        # 테이블별 적재 방식 (full / incremental)
│   ├── extract_load.py    # 추출·적재
│   └── verify_load.py     # 행 수 대조
├── airflow/
│   ├── docker-compose.yml # 로컬 Airflow (standalone + 메타DB)
│   ├── dags/              # ping_raw_load
│   ├── plugins/
│   └── requirements.txt   # Airflow 컨테이너 추가 패키지
├── bigquery/
│   ├── staging/           # stg 변환 SQL
│   └── mart/              # mart 집계 SQL
├── qa/
│   ├── checks/            # 품질 검사 정의
│   └── reports/           # 검사 결과 (git 제외)
└── data/
    └── synthetic/         # 생성 CSV (git 제외)
```

---

## 자주 쓰는 명령

**스키마 다시 만들기 (전부 지우고)**

```bash
docker exec pgtest psql -U postgres -c "DROP DATABASE IF EXISTS pingv2;" -c "CREATE DATABASE pingv2;"
python db/apply.py --target local
```

**대량 적재 후 (필수 · 두 개 다)**

```bash
docker exec -i pgtest psql -U postgres -d pingv2 < db/ddl/95_resync_sequences.sql
docker exec -i pgtest psql -U postgres -d pingv2 < db/ddl/96_backfill_updated_at.sql
```

`95` — id를 직접 지정해서 넣으면 시퀀스가 전진하지 않는다. 이걸 안 돌리면
나중에 새 행을 넣을 때 PK 충돌이 난다.

`96` — 증분 워터마크(`updated_at`)의 기본값이 `now()` 라, COPY 로 부어 넣으면
786만 행이 전부 "적재한 순간"이 된다. 3개월치가 하루에 뭉치고 BigQuery
파티션이 무의미해진다. 각 행의 원래 시각으로 되돌린다.

---

## BigQuery 적재 (P4)

```bash
python pipeline/extract_load.py --source supabase     # 실유저 (증분)
python pipeline/extract_load.py --source local        # 합성 786만 행
python pipeline/verify_load.py  --source supabase     # 행 수 대조
```

두 원천이 **같은 BigQuery 테이블**로 흐른다. 둘 다 id 가 1부터라 그대로
섞으면 서로를 덮어쓰므로, 적재 시 `_source` 컬럼을 붙이고 키를
`(_source, id)` 로 쓴다. 분석에서 실유저만 보려면 `WHERE _source = 'supabase'`.

원천에서 지워진 행은 **삭제하지 않고 `_deleted_at` 을 찍는다.** raw 는 이력을
잃지 않는다. 그래서 분석 쿼리에는 `AND _deleted_at IS NULL` 이 거의 항상 필요하다.

정기 적재는 Airflow 가 한다:

```bash
docker compose -f airflow/docker-compose.yml up -d    # http://localhost:8080
```

### 합성 데이터를 다시 만들 때

생성기를 고쳐 데이터를 새로 만들어도 **실유저 데이터는 건드리지 않는다.**
BigQuery 에서 지우는 범위가 `WHERE _source = 'local'` 로 걸려 있다.

```bash
python generator/generate.py                                    # CSV 생성
python generator/load.py --truncate                             # 로컬 DB 재적재
                                                                #  (95·96 은 자동 실행)
python pipeline/extract_load.py --source local --full-refresh   # BigQuery 재적재
python pipeline/verify_load.py  --source local                  # 행 수 대조
```

`--full-refresh` 는 워터마크를 무시하고 `_source='local'` 행을 지운 뒤 새로 넣는다.
행 수가 줄어도, 컬럼이 늘어도 따라간다 — 원천에 새 컬럼이 생기면 BigQuery
테이블에도 자동으로 추가한다.

**따라가지 못하는 변경 하나** — 기존 컬럼의 **타입**이 바뀌면(예: `int` → `text`)
적재가 거부된다. 그때는 해당 테이블을 BigQuery 에서 지우고 다시 적재한다.
원천에서 컬럼이 **사라지는** 것은 문제없다. BigQuery 에는 남고 이후 행은 NULL 이 된다
— raw 는 과거를 지우지 않는다.

---

## 진행 상태

두 트랙으로 나뉘어 있고, **웹앱이 우선**이다. 파이프라인은 실유저 데이터가 생긴 뒤 잇는다.
왜 이 순서인지는 [DECISIONS.md](DECISIONS.md)의 "웹앱을 최우선 트랙으로 재편" 참조.

**웹앱 트랙**

| 단계 | 내용 | 상태 |
|---|---|---|
| W0 | 익명 인증 대응 스키마 | **완료** |
| W1 | Supabase + RLS (보안 게이트) | **완료** |
| W2 | 앱 뼈대 · 익명 로그인 | **완료** |
| W3 | 온보딩 · 초대 코드 발급 | **완료** |
| W4 | 친구 (코드 교환, 5명 게이트) | **완료** |
| W5 | 투표 | **완료** |
| W6 | 받은 투표 · 힌트 구매 | **완료** |
| W7 | 배포 · 클로즈드 테스트 | **완료** (초대는 남음) |
| W8 | 학교 정보 — 급식표 | **완료** · 시간표·공지는 남음 |
| W9 | 자유게시판 (닉네임 노출) | **완료** — 글·댓글·좋아요·신고 |
| W10 | 친구 추천 (같은 학교) | **완료** — 요청 / 안 볼래 |

**파이프라인 트랙**

| 단계 | 내용 | 상태 |
|---|---|---|
| P0 | 스키마·DDL | **완료** |
| P1 | 합성 데이터 생성 | **완료** |
| P2 | Postgres 적재 | **완료** |
| P3 | NEIS 수집 | 학교·학급·급식 **완료** · DAG 화는 남음 |
| P4 | BigQuery 적재 DAG | **완료** — 42테이블 789만 행 · 행 수 대조 통과 |
| P5 | 품질 검증 | |
| P6 | stg / mart | |
| P7 | 대시보드 | |
