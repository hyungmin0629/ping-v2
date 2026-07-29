# 처음 온 사람을 위한 안내

`git clone` 하고 나서 이 문서 하나만 따라오면 됩니다.
명령어는 **한 줄씩** 실행하고, 각 단계 끝의 "확인" 을 통과했는지 보고 다음으로 갑니다.

---

## 0. 먼저 알아둘 것 — 두 갈래가 있습니다

이 저장소에는 클라우드 계정 정보(Supabase·Google Cloud)가 **들어 있지 않습니다.**
`.env` 와 `credentials.json` 은 커밋되지 않기 때문입니다. 그래서 두 갈래가 있어요.

| | A. 로컬만 | B. 전체 |
|---|---|---|
| 필요한 계정 | **없음** | Supabase + Google Cloud (본인 것) |
| 할 수 있는 것 | 스키마 · 합성 786만 행 · 정합성 검사 | 위 + 웹앱 + BigQuery 적재 + Airflow |
| 걸리는 시간 | 20분 | 1~2시간 |

**처음이면 A 만 하세요.** 이 프로젝트의 핵심(스키마 설계와 데이터 품질)은
A 만으로 다 볼 수 있습니다. B 는 웹앱을 띄우거나 파이프라인을 직접 돌려볼 때
필요합니다.

프로젝트가 무엇인지는 [README.md](../README.md), 왜 그렇게 만들었는지는
[DECISIONS.md](../DECISIONS.md) 에 있습니다. 지금은 안 읽어도 됩니다.

---

## 1. 미리 깔려 있어야 하는 것

| | 버전 | 확인 명령 |
|---|---|---|
| Python | 3.11 이상 (3.12 로 개발) | `python --version` |
| Docker Desktop | 실행 중이어야 함 | `docker ps` |
| Node.js | 20 이상 (B 갈래만) | `node --version` |

`docker ps` 가 오류를 내면 Docker Desktop 이 안 켜진 겁니다. 켜고 다시 하세요.

---

# A 갈래 — 로컬만 (계정 불필요)

## A-1. 파이썬 환경

```bash
python -m venv .venv
```

가상환경을 켭니다. **터미널 종류에 따라 다릅니다.**

```bash
.venv\Scripts\activate          # Windows PowerShell / cmd
source .venv/Scripts/activate   # Windows Git Bash
source .venv/bin/activate       # macOS / Linux
```

```bash
pip install -r requirements.txt
```

**확인** — 프롬프트 앞에 `(.venv)` 가 붙어 있으면 됩니다.

## A-2. 로컬 Postgres 띄우기

```bash
docker run -d --name pgtest -e POSTGRES_PASSWORD=test -e POSTGRES_DB=pingv2 -p 5433:5432 --shm-size=1g postgres:16
```

> `--shm-size=1g` 를 빠뜨리지 마세요. 도커 기본값은 64MB 인데, 그 상태로
> 786만 행에 정합성 검사를 돌리면 `No space left on device` 로 죽습니다.
> 디스크가 아니라 **공유메모리** 부족입니다. 실제로 겪은 문제입니다.

**확인**

```bash
docker ps --filter name=pgtest
```

`Up ...` 이 보이면 됩니다.

## A-3. 환경변수 파일

```bash
copy .env.example .env          # Windows
cp .env.example .env            # macOS / Linux
```

A 갈래는 **아무것도 채우지 않아도 됩니다.** 로컬 Postgres 설정은 기본값이
이미 맞게 들어 있습니다(`PGPORT=5433` 등).

## A-4. 스키마 만들기

```bash
python db/apply.py --target local
```

**확인** — `테이블 42개 / FK ...개` 가 나오면 성공입니다.

> ⚠️ **`cat db/ddl/*.sql | psql` 같은 방식으로 만들지 마세요.**
> 그 경로에는 `db/migrations/` 가 빠져서 컬럼 3개가 없는 반쪽 스키마가 됩니다.
> 실제로 이 프로젝트가 그 상태로 몇 주를 돌았고, 정합성 검사가 통째로
> 실행되지 않고 있었는데 아무도 몰랐습니다. `apply.py` 를 쓰세요.

> `70_deferred_v2.sql` 은 일부러 적용하지 않습니다. MVP 에서 안 쓰는
> 테이블이라 `apply.py` 가 목록에서 빼둡니다.

## A-5. 합성 데이터 만들기 + 넣기

```bash
python generator/generate.py
```

유저 5,000명 / 3개월치를 만듭니다. **25초쯤** 걸리고 `data/synthetic/` 에
CSV 가 쌓입니다. 작게 시험하려면 `--users 500 --months 1` 을 붙이세요.

```bash
python generator/load.py --truncate
```

**90초쯤** 걸립니다. 끝나면 시퀀스 재동기화와 워터마크 되돌리기가
자동으로 이어서 돕니다.

**확인** — `적재 완료 — 총 7,8xx,xxx 행` 이 나오면 성공입니다.

## A-6. 데이터가 제대로 만들어졌는지 검사

이게 이 프로젝트에서 제일 볼 만한 부분입니다.

```bash
docker exec -i pgtest psql -U postgres -d pingv2 -c "SET max_parallel_workers_per_gather = 0;" -f - < qa/checks/integrity.sql
```

**확인** — 17줄이 나오고 **오른쪽 숫자가 전부 0** 이어야 합니다.
하나라도 0이 아니면 데이터에 문제가 있는 겁니다.

이 17종은 FK·NOT NULL 처럼 DB가 이미 막아주는 것이 아니라, **제약으로는
표현할 수 없는 규칙**을 봅니다. 예를 들면:

- 하트 원장의 잔액이 유저 잔액과 맞는가 (구 서비스에서 20억 원 차이가 났던 항목)
- 친구가 아닌 사람이 투표 후보로 나왔는가
- 광고를 안 보고 셔플한 기록이 있는가

**여기까지가 A 갈래 끝입니다.** 스키마와 데이터를 둘러보세요:

```bash
docker exec -it pgtest psql -U postgres -d pingv2
```

```sql
\dt                                    -- 테이블 42개
\d app_user                            -- 컬럼 보기
SELECT count(*) FROM heart_transaction;
\q                                     -- 나가기
```

---

# B 갈래 — 전체 (본인 계정 필요)

A 를 끝낸 상태에서 이어집니다. 여기부터는 **본인 계정**을 만들어야 합니다.
저장소의 Supabase·Google Cloud 프로젝트에는 접근할 수 없습니다.

## B-1. Supabase 프로젝트 만들기

1. https://supabase.com 에서 무료 프로젝트 생성 (리전은 서울 권장)
2. **Authentication → Sign In / Providers → Allow anonymous sign-ins 켜기**
   — 기본값이 꺼짐이고, 토글 후 **저장 버튼을 눌러야** 반영됩니다.
   이걸 안 하면 앱에 접속해도 계정이 안 만들어집니다.
3. `.env` 에 값 채우기 (Project Settings → API / Database)

```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_KEY=...
SUPABASE_DB_URL=postgresql://...
```

> ⚠️ `SUPABASE_DB_URL` 은 **Session pooler** 주소를 쓰세요.
> 직접 연결(`db.<ref>.supabase.co`)은 무료 플랜에서 IPv6 전용이라 IPv4
> 환경에서는 호스트 이름조차 해석되지 않습니다.
>
> ⚠️ 비밀번호에 `@` `#` 같은 문자가 있으면 **퍼센트 인코딩**해서 넣으세요
> (`@` → `%40`). 안 그러면 주소 파싱이 깨집니다.

## B-2. Supabase 에 스키마 + 보안 정책 올리기

**순서가 중요합니다.** 뒤 파일이 앞의 정책을 갈아끼우기 때문에 순서를 바꾸면 깨집니다.

```bash
python db/apply.py --target supabase
python db/run_sql.py db/rls/policies.sql
python db/run_sql.py db/rls/onboarding.sql
python db/run_sql.py db/rls/friends.sql
python db/run_sql.py db/rls/voting.sql
python db/run_sql.py db/rls/received.sql
python db/run_sql.py db/rls/session_log.sql
python db/run_sql.py db/rls/school_picker.sql
python db/run_sql.py db/rls/school_info.sql
python db/run_sql.py db/seed_org.sql
python db/run_sql.py db/seed_questions.sql
```

**확인 — 이게 이 프로젝트의 보안 관문입니다.**

```bash
python db/rls/verify.py
```

**86항목이 전부 통과해야 합니다.** 하나라도 실패하면 남의 데이터가 보인다는
뜻이니 다음으로 넘어가지 마세요.

이 시험은 정책을 선언만 하고 끝내지 않습니다. **실제로 다른 사람의 토큰으로
남의 투표·하트·친구 목록을 훔쳐보려 시도**하고, 막히는지 봅니다. 동시에
"열려 있어야 할 것"도 함께 시험합니다 — 전부 막아버려도 침투 시험은
통과하기 때문입니다.

## B-3. 웹앱 띄우기

```bash
cd web
npm install
```

`web/.env.local` 파일을 새로 만들고 **두 줄만** 넣습니다:

```
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

> ⚠️ `SUPABASE_SERVICE_KEY` 는 **절대 넣지 마세요.** 그 키는 RLS 를 통째로
> 무시합니다. `NEXT_PUBLIC_` 이 붙은 값은 브라우저로 그대로 나갑니다.

```bash
npm run dev
```

http://localhost:3000 을 엽니다.

**확인** — 접속하면 계정이 자동으로 만들어지고 온보딩 화면이 뜹니다.
새로고침해도 유지되면 성공입니다.

> ⚠️ **개발 서버에서 동적 라우트(`/[param]`)가 열리지 않는 문제가 있습니다.**
> 최소한의 `/probe/[x]` 로도 재현됩니다. 프로덕션 빌드는 정상이지만 로컬
> 확인이 불가능해서, 이 프로젝트는 **동적 라우트 대신 쿼리스트링**을 씁니다
> (초대 링크가 `/add?code=...` 인 이유).

## B-4. 혼자서 투표까지 해보기

투표는 **친구 5명**이 있어야 열리고, 질문마다 후보 4명이 필요합니다.
창을 다섯 개 띄울 수는 없으니 더미 친구를 붙입니다.

화면에서 본인 초대 코드를 확인한 뒤:

```bash
python db/seed_test_friends.py --for <초대코드>
```

같은 반 5명 + 다른 반 3명이 친구로 붙습니다. 로그인 계정 없이 프로필 행만
만드는 것이라 실제 사용자와 섞이지 않습니다(`is_synthetic = true`).

지울 때는 `python db/seed_test_friends.py --clean` 입니다.

## B-5. BigQuery 적재 (선택)

1. https://console.cloud.google.com 에서 프로젝트 생성
2. **IAM 및 관리자 → 서비스 계정 → 만들기**, 역할 **BigQuery 관리자**
   (데이터셋을 직접 만들어야 해서 "데이터 편집자"만으로는 부족합니다)
3. 키 → 새 키 만들기 → **JSON** → 받은 파일을 저장소 루트에 `credentials.json` 로 저장
4. `.env` 의 `GCP_PROJECT_ID` 에 **프로젝트 ID** 를 넣습니다
   (표시 이름이 아니라 `my-project-503916` 같은 형태입니다)

```bash
python pipeline/extract_load.py --source supabase --dry-run   # 대상만 확인
python pipeline/extract_load.py --source supabase             # 실제 적재
python pipeline/verify_load.py  --source supabase             # 행 수 대조
```

합성 데이터도 올리려면 `--source local` 로 한 번 더 돌립니다
(786만 행이라 **30분쯤** 걸립니다).

**확인** — `빠진 행 없음` 이 나오면 성공입니다.

> 저장 10GiB · 쿼리 1TiB/월 까지 무료입니다. 이 데이터 전체가 576MB 라
> 한도의 6% 정도입니다. 그래도 **예산 알림**은 걸어두세요
> (결제 → 예산 및 알림 → 월 1,000원 정도).

## B-6. Airflow (선택)

```bash
docker compose -f airflow/docker-compose.yml up -d
```

http://localhost:8080 · 아이디 `admin`, 비밀번호는:

```bash
docker exec ping-airflow cat /opt/airflow/standalone_admin_password.txt
```

`ping_raw_load` DAG 이 하나 있습니다. 처음엔 꺼져 있으니 토글을 켜야
스케줄(매일 새벽 4시)이 돕니다.

---

## 자주 걸리는 오류

| 오류 메시지 | 원인과 해결 |
|---|---|
| `could not translate host name ... db.xxx.supabase.co` | 직접 연결을 쓰고 있습니다. **Session pooler** 주소로 바꾸세요 |
| `password authentication failed` | 비밀번호에 특수문자가 있는데 퍼센트 인코딩을 안 했습니다 (`@` → `%40`) |
| `No space left on device` (정합성 검사 중) | 디스크가 아니라 공유메모리입니다. 컨테이너를 `--shm-size=1g` 로 다시 만드세요 |
| `column v.padded_count does not exist` | 스키마가 반쪽입니다. `python db/apply.py --target local` 로 다시 만드세요 |
| 앱에 접속해도 계정이 안 생김 | Supabase 에서 **Allow anonymous sign-ins** 를 켜고 **저장** 눌렀는지 확인 |
| `Jest worker ... exceeding retry limit` (웹) | 개발 서버의 동적 라우트 문제입니다. 쿼리스트링을 쓰세요 |
| BigQuery `403 Permission denied` | 서비스 계정 역할이 **BigQuery 관리자**인지 확인 |

## 자주 쓰는 초기화

```bash
python db/reset_users.py --yes          # 실유저 데이터 전체 삭제 (마스터는 보존)
python db/seed_test_friends.py --clean  # 더미 친구만 삭제
```

브라우저 세션도 지워야 완전히 초기화됩니다 —
개발자도구(F12) → Application → Storage → Clear site data, 또는 시크릿 창.

---

## 다음에 읽을 것

| 문서 | 언제 |
|---|---|
| [README.md](../README.md) | 명령어를 다시 찾을 때 |
| [CLAUDE.md](../CLAUDE.md) | 현재 진행 상황과 함정 목록 |
| [DECISIONS.md](../DECISIONS.md) | **"왜 이렇게 만들었지?"** 가 궁금할 때. 여기가 제일 재미있습니다 |
| [design-spec.md](design-spec.md) | 전체 설계와 단계별 정의 |

코드를 고치기 전에 알아둘 규칙 하나 — **스키마 구조는 DDL 이 진실입니다.**
문서에 테이블 정의를 복사해두지 않습니다. 문서에는 코드가 말해주지 못하는 것
(결정과 이유, 제약, 실패한 시도)만 남깁니다.
