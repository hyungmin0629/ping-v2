# ping-v2

학교 기반 소셜 투표 서비스의 **데이터 파이프라인 프로젝트**.
합성 데이터와 NEIS 실데이터를 Airflow로 BigQuery에 적재한다.

- 프로젝트 컨텍스트 → [CLAUDE.md](CLAUDE.md)
- 설계서 → [docs/design-spec.md](docs/design-spec.md)
- 결정 이력 → [DECISIONS.md](DECISIONS.md)

---

## 처음 시작할 때

### 1. 로컬 DB 띄우기

```bash
docker run -d --name pgtest \
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=pingv2 \
  -p 5433:5432 postgres:16
```

### 2. 스키마 만들기

```bash
cd db/ddl
cat 00_enums.sql 10_reference_user.sql 20_social.sql 30_question_vote.sql \
    40_heart_report.sql 50_school_service.sql 60_board.sql 90_seed_master.sql \
  | docker exec -i pgtest psql -U postgres -d pingv2 -v ON_ERROR_STOP=1
```

확인:

```bash
docker exec -i pgtest psql -U postgres -d pingv2 -c \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"
```

`42`가 나오면 정상.

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
├── airflow/               # P4 에서 채운다 (지금은 빈 스캐폴딩)
│   ├── dags/
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
```

그 다음 위의 `2. 스키마 만들기`를 다시 실행.

**대량 적재 후 (필수)**

```bash
docker exec -i pgtest psql -U postgres -d pingv2 < db/ddl/95_resync_sequences.sql
```

id를 직접 지정해서 넣으면 시퀀스가 전진하지 않는다. 이걸 안 돌리면
나중에 새 행을 넣을 때 PK 충돌이 난다.

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
| W7 | 배포 · 클로즈드 테스트 | 다음 |
| W8 | 학교 정보 (급식·시간표·공지) | P3 이후 |

**파이프라인 트랙**

| 단계 | 내용 | 상태 |
|---|---|---|
| P0 | 스키마·DDL | **완료** |
| P1 | 합성 데이터 생성 | **완료** |
| P2 | Postgres 적재 | **완료** |
| P3 | NEIS 수집 DAG | W7 이후 |
| P4 | BigQuery 적재 DAG | |
| P5 | 품질 검증 | |
| P6 | stg / mart | |
| P7 | 대시보드 | |
