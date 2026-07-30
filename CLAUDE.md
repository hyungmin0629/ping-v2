# ping-v2

학교 기반 소셜 투표 **웹서비스 MVP**와 그 위의 데이터 파이프라인.
기존 서비스(`../final`)의 DB를 분석해 발견한 구조적 결함을 닫은 새 스키마 위에,
**개인정보를 받지 않는** 웹앱을 올리고 실유저 데이터를 BigQuery까지 적재한다.

상세 계획은 [[design-spec]], 결정 이력은 [[DECISIONS]] 참조.
팀 작업 절차와 스키마 변경의 영향 범위는 [[TEAM-PLAN]].
저장소를 처음 받은 사람에게는 [[ONBOARDING]] 을 가리킨다 — 계정 없이 되는
A 갈래(로컬 합성 데이터)와 계정이 필요한 B 갈래를 나눠 적어 두었다.

---

## 최우선 목표

**지인이 링크로 접속해 실제로 투표할 수 있는 웹앱을 만든다.**
파이프라인(P3~P7)은 웹앱 배포 후로 미뤘다.

## 개인정보를 받지 않는다

이 프로젝트의 핵심 제약이다.

| 받지 않는 것 | 대신 |
|---|---|
| 이메일 · 비밀번호 | Supabase 익명 계정 (접속 즉시 자동 생성) |
| 전화번호 | 친구 추가는 **초대 코드**로 |
| 실명 | 유저가 정하는 닉네임 |

유저가 입력하는 것은 **닉네임·성별·소속(학교·반)**이다.
성별은 받은 투표의 힌트로 파는 정보라 온보딩 필수 항목이다([[DECISIONS]]).
⚠️ 이 조합은 소규모 집단에서 개인 특정이 가능하다. 비개인정보라고 단정하지 않고,
개인정보처리방침에 수집 항목으로 명시한다.

## 이 프로젝트가 아닌 것

- **상용 서비스 출시가 목표가 아니다.** 앱스토어 배포, 인앱결제, 사업자등록은 범위 밖.
- **불특정 다수 공개가 아니다.** 성인 지인 20~50명 대상 클로즈드 테스트만.
- MVP에서 **광고는 스텁**(3초 대기), **하트 충전은 제외**. 스키마는 준비돼 있다.
- **익명 게시판은 열지 않는다.** 신고 검토 인력이 없기 때문.
  단 **자유게시판**(닉네임이 드러나는 형태)은 열었다(W9). 글쓴이가 붙으면
  "사고가 나도 책임을 물을 수 없다"는 전제가 바뀌기 때문이다.

## 작업자 컨텍스트

작업자는 **개발 경험이 없다.** 기획·데이터 해석 판단은 하지만 코드는 직접 쓰지 않는다.

- 코드 작성·디버깅은 전부 에이전트가 한다.
- 작업자에게는 **실행할 명령어를 한 줄씩** 주고, 결과를 받아 판단한다.
- 여러 단계를 한 번에 시키지 않는다. 한 단계 끝나고 확인 후 다음.
- 에러 메시지를 받으면 원인을 설명하고 고친다. "이렇게 해보세요" 식으로 떠넘기지 않는다.

## 스택

| 구분 | 선택 | 비고 |
|---|---|---|
| 운영 DB | Supabase (PostgreSQL) | 인증 내장, 무료 티어 |
| 분석 DW | BigQuery | 무료 티어 내 |
| 오케스트레이션 | Airflow (로컬 Docker) | Cloud Composer는 월 40만원대라 제외 |
| 웹앱 (2트랙) | Next.js + Vercel | v1에서는 후순위 |
| 외부 데이터 | NEIS 교육정보 개방포털 | 학교·급식·시간표·학사일정 |

기존 분석 대상 MySQL은 `mysql` 컨테이너(포트 3307)에 `final` / `hackle` 스키마로 살아있다.
새 프로젝트는 이걸 **건드리지 않는다.**

## 현재 단계

**P0·P1·P2·P4·W0~W12 완료** (2026-07-30) → 다음은 **P5 품질 검증** 또는 **P6 stg/mart**

앱은 배포돼 있고, 실데이터가 BigQuery 까지 흐른다. 초대를 미룰 이유가 없어졌다
— P4 를 먼저 한 것은 초대 후에 만들면 그동안 쌓인 데이터를 소급 적재해야 했기 때문이다.
이제 초대해도 증분이 처음부터 흐른다.

| 완료 | 결과 |
|---|---|
| P0 스키마·DDL | 제약 위반 16종 차단 검증 |
| P1 합성 데이터 | 786만 행 생성 (25초) |
| P2 적재 | 로컬 Postgres 적재 (89초) |
| W0 익명 인증 대응 | 42 테이블 / 정합성 17종 / 개인정보 컬럼 0개 |
| W1 Supabase + RLS | 침투 15종 차단 + 정상동작 9종 |
| W2 앱 뼈대 | Next.js 16 + 익명 로그인. 새로고침 유지·시크릿창 분리 확인 |
| W3 온보딩 | 가입 RPC + 화면. 온보딩 시험 4종 추가, 브라우저에서 실가입 확인 |
| W4 친구 | 요청·수락·거절 RPC + 화면. 시험 42종 통과, 창 두 개로 실제 교환 확인 |
| W5 투표 | 후보 추출·투표·셔플 RPC + 화면. 질문 24개 시드, 접속 로그 추가. 시험 67종 통과 |
| W6 받은 투표 | 힌트 4단계(성별→초성→반→공개, 200·300·500·1000) + 내가 한 투표 목록 |
| W7 배포 | Vercel 배포, 개인정보처리방침, 초대 링크(`/add?code=`) |
| P3 NEIS (일부) | 전국 중·고 5,724개 · 학교 19곳의 학급과 급식(2,938건). DAG 화는 남음 |
| W8 급식표 | 메인 토글 → 월 캘린더 · 끼니 선택. **시간표·공지는 남음** |
| P4 BigQuery 적재 | 42테이블 · 789만 행 (실유저 29,761 + 합성 786만). 갱신 감지 실증, Airflow DAG 실행 확인 |
| W9 자유게시판 | 닉네임 노출 · 학교 단위. 글·댓글·좋아요·신고 |
| W10 친구 추천 | 같은 학교 사람 목록 → 요청 / 안 볼래. **더미는 제외** |
| W11 프로필 수정 | 닉네임·성별·소속 변경. 온보딩 폼 재사용 |
| W12 계정 삭제·뒤로가기 | 탈퇴(사유 기록·행 보존) + 휴대폰 뒤로가기. 시험 144종 통과 |

## 스크립트

| 명령 | 하는 일 |
|---|---|
| `python db/apply.py --target supabase` | DDL + 마이그레이션 적용. **확인 절차가 있다**(`--yes` 로 생략) |
| `python db/run_sql.py <파일>` | SQL 파일 하나를 Supabase 에 적용 |
| `python db/erd.py` | 살아 있는 스키마에서 ERD 를 뽑아 `docs/erd.md`·`erd.json` 갱신 |
| `python db/rls/verify.py` | **침투·동작 시험 144항목. 배포 전 반드시 통과** |
| `python db/neis_schools.py --schools` | 전국 중·고 목록 |
| `python db/neis_schools.py --classes <코드> [--into <조직>]` | 학급 |
| `python db/neis_meals.py --school <코드>` | 급식 |
| `python db/seed_test_friends.py --for <초대코드> [--votes N]` | 더미 친구·받은 투표 |
| `python db/reset_users.py --yes` | 유저 데이터 전체 삭제 (마스터는 보존) |
| `python pipeline/extract_load.py --source supabase` | BigQuery raw 증분 적재 |
| `python pipeline/verify_load.py --source supabase` | **적재 후 행 수 대조. 증분은 조용히 틀린다** |

정합성 검사는 `qa/checks/integrity.sql` 을 Supabase 에 그대로 돌린다(17종, 위반 0이어야 한다).

⚠️ **정합성 검사와 설계가 한 군데서 어긋난다.** `friends.sql` 은 `service_unlocked_at` 을
"한 번 찍히면 유지"로 두는데(친구가 줄어도 이미 연 서비스를 닫지 않는다),
검사의 "게이트 위반(친구<5인데 해금)"은 그걸 모른다. 친구 수가 5 아래로 떨어지는
경로가 지금은 **관리자 삭제뿐**이라 평소에는 드러나지 않는다.
계정을 정리한 뒤 이 항목이 걸리면, 해당 유저의 `service_unlocked_at` 을 NULL 로
되돌리면 된다 — 친구가 0명이면 후보가 없어 어차피 투표가 되지 않는다.
(2026-07-30, 더미를 전부 지울 때 실제로 걸렸다)

## DB 를 처음부터 다시 만들 때

`db/rls/` 의 SQL 은 **순서가 있다.** 뒤의 파일이 앞의 정책을 갈아끼우기 때문이다.

```
python db/apply.py --target supabase          # DDL + migrations
python db/run_sql.py db/rls/policies.sql      # 기본 RLS
python db/run_sql.py db/rls/onboarding.sql    # 가입 RPC (insert_own_user 를 대체)
python db/run_sql.py db/rls/friends.sql       # 친구 RPC (친구요청 정책을 대체)
python db/run_sql.py db/rls/voting.sql        # 투표 RPC
python db/run_sql.py db/rls/received.sql      # 힌트·받은 투표 뷰
python db/run_sql.py db/rls/session_log.sql   # 접속 로그 (insert_own_session 을 대체)
python db/run_sql.py db/rls/school_picker.sql # selectable_school 뷰
python db/run_sql.py db/rls/school_info.sql   # 급식 정책 + my_school_source 뷰
python db/run_sql.py db/rls/board.sql         # 자유게시판 뷰 + RPC
python db/run_sql.py db/rls/recommend.sql     # 친구 추천 뷰 + RPC
python db/run_sql.py db/rls/profile.sql       # 프로필 수정 RPC (직접 UPDATE 를 회수)
python db/run_sql.py db/rls/withdraw.sql      # 계정 삭제 RPC
python db/run_sql.py db/seed_org.sql          # 테스트 조직
python db/run_sql.py db/seed_questions.sql    # 질문 24개
python db/rls/verify.py                       # 통과해야 끝
```

## 웹앱 (web/)

- Next.js 16.2 / React 19.2 / Turbopack / Tailwind / TypeScript
- **배포: https://ping-v2-lac.vercel.app** (Vercel · GitHub `main` push 시 자동 배포)
  - Vercel 프로젝트의 **Root Directory 는 `web`** 이다. 저장소 루트에는 package.json 이 없다.
  - 환경변수는 `NEXT_PUBLIC_` 두 개뿐. service_role 키는 넣지 않는다.
- 개발 서버: `cd web && npm run dev` → http://localhost:3000
- ⚠️ 익명 계정은 **주소마다 따로**다. localhost 계정과 배포본 계정은 서로 다른 사람이다.
- ⚠️ **이 환경의 개발 서버는 동적 라우트(`[param]`)를 열지 못한다.** 최소한의
  `/probe/[x]` 로도 재현된다 — `Jest worker ... exceeding retry limit`, HTTP 500.
  프로덕션 빌드는 정상이지만 로컬에서 확인이 불가능하므로, **동적 라우트 대신
  쿼리스트링을 쓴다**(초대 링크가 `/add?code=…` 인 이유).
- `web/.env.local` 은 루트 `.env` 에서 생성한다. **service_role 키는 절대 넣지 않는다.**
- ⚠️ **v16 부터 `middleware.ts` 가 `proxy.ts` 로 바뀌었다.** 인증 미들웨어를 붙일 때 주의.
- `web/AGENTS.md` 지시대로, 코드 작성 전 `node_modules/next/dist/docs/` 를 확인할 것.

## 조직 데이터

| 항목 | 값 |
|---|---|
| 표시명 | **코드잇 DA 14기** (테스터에게 익숙한 이름을 유지) |
| 정보 출처 | **서울고등학교** (`school.info_school_id`) |
| 학급 | 서울고 2026학년도 실제 학급 — 1~3학년 × 1~14반 |

이름은 테스트 조직이지만 **급식·시간표·학사일정은 서울고등학교의 공개 데이터**를 쓴다.
`neis_school_code` 가 UNIQUE 라 조직 행에 직접 넣을 수 없어 `info_school_id` 로 연결했다
(경위는 [[DECISIONS]]). 급식을 부를 때는 `coalesce(info_school_id, id)` 의 코드를 쓴다.

테스터에게는 **팀 번호를 반으로 바꿔 넣으라고** 안내한다(1팀 → 1학년 1반).
온보딩 화면이 그 문구를 띄운다.

전국 중·고 5,724개도 `school` 에 들어 있지만, 온보딩 목록에는 **학급이 등록된 학교만**
나온다(`selectable_school` 뷰). 학급은 학교마다 API 를 한 번씩 불러야 해서
필요한 학교만 받는다.

**2026-07-30 기준 19곳이 열려 있다** — 코드잇 DA 14기 + 서울 17개 구의 고등학교 17곳
+ 한영고(여수, 동명이교를 코드로 지정하다 잘못 들어왔으나 지역이 섞이는 편이
분석에 낫다고 보아 그대로 둠). 학급과 급식을 함께 받아두었다. 급식은 총 2,938건.

학교를 더 열 때는 **표준학교코드로 지정한다.** 이름으로 하면 동명이교에 걸린다:

```
python db/neis_schools.py --schools                                  # 전국 목록
python db/neis_schools.py --classes "서울고등학교" --into "코드잇 DA 14기"
python db/neis_meals.py --school "서울고등학교"                        # 급식 (올해)
```

급식은 **데이터를 준 학교(서울고) 아래** 저장하고, RLS 가 `info_school_id` 를
따라가 조직 소속 유저에게 보여준다. 조직마다 복사하면 같은 급식이 조직 수만큼 늘어난다.

## 초기화

테스트하다 쌓인 계정을 치우려면:

```
python db/reset_users.py --yes     # 프로필·활동·익명계정 삭제 (마스터는 보존)
```

## 혼자 시험하기

투표는 친구가 5명이어야 열리고 문항마다 후보가 4명 필요하다. 창을 다섯 개 띄울 수
없으므로 더미 친구를 붙인다. 로그인 계정 없이 프로필 행만 만든다
(`auth_user_id` 가 nullable 이라 가능하다).

```
python db/seed_test_friends.py --for <내 초대코드>   # 같은 반 5 + 다른 반 3
python db/seed_test_friends.py --clean              # 전부 삭제
```

**더미는 테스트 중에도 남겨둔다.** (2026-07-30 판단)
후보는 내 친구 중에서만 뽑히고, 친구가 되려면 초대 코드를 알아야 한다. 더미 코드는
DB 에만 있으므로 **테스터가 더미를 마주칠 경로가 없다.** 분석은 `is_synthetic` 으로 거른다.

남는 영향은 **더미를 붙인 계정 하나뿐**이다 — 그 계정의 후보 풀에 더미가 섞여
진짜 친구가 덜 나온다. 일반 이용자처럼 써보고 싶을 때 `--clean` 하면 된다.
P3(NEIS) 이후에도 화면을 시험하려면 더미가 계속 필요하다.

브라우저 세션도 지워야 완전히 초기화된다 —
개발자도구(F12) → Application → Storage → Clear site data, 또는 시크릿 창.

지우지 않아도 앱이 알아서 새 계정을 만든다(`ensureAnonymousSession` 이 서버에
토큰 유효성을 확인하고, 계정이 사라졌으면 다시 발급받는다).

## 익명 로그인 설정

Supabase 대시보드에서 **Authentication → Sign In / Providers → Allow anonymous sign-ins**
가 켜져 있어야 한다. 기본값은 꺼짐이고, 토글 후 **저장 버튼을 눌러야** 반영된다.
확인: `/auth/v1/settings` 의 `external.anonymous_users` 가 `true`.

웹앱 단계(W0~W7)와 파이프라인 단계(P3~P7)는 [[design-spec]] 4장 참조.

## Supabase 접속

- **Session pooler 로만 접속한다.** 직접 연결(`db.<ref>.supabase.co`)은 IPv6 전용이라
  IPv4 환경에서 호스트 해석이 실패한다. 자세한 경위는 [[DECISIONS]].
- `.env` 의 `SUPABASE_DB_URL` 안 비밀번호는 **퍼센트 인코딩된 상태**로 보관한다.
- 스키마 적용: `python db/apply.py --target supabase`
- RLS 검증: `python db/rls/verify.py` — **배포 전 반드시 통과해야 한다**

## ⚠️ verify.py 가 못 잡는 것 — safeupdate

**시험 128항목이 전부 통과해도 실제 앱이 죽을 수 있다.** 2026-07-30 에 실제로 그랬다.

브라우저는 PostgREST 를 거쳐 **`authenticator`** 역할로 접속하고, 그 역할에는
`session_preload_libraries = supautils, safeupdate` 가 걸려 있다.
safeupdate 는 **WHERE 없는 DELETE/UPDATE 를 임시 테이블에서도 막는다.**

그런데 `verify.py` 는 `postgres` 로 붙어 `SET LOCAL ROLE authenticated` 만 한다.
preload 는 **세션이 열릴 때** 적용되므로 역할만 바꿔서는 안 걸린다.
postgres 는 `LOAD 'safeupdate'` 권한도 없어 흉내낼 수도 없다.

그래서 `verify.py` 가 **소스를 직접 검사한다** — `db/rls/*.sql` 에 WHERE 없는
DELETE/UPDATE 가 있으면 실패한다. 새 RPC 를 쓸 때 `WHERE true` 를 잊지 말 것.

**교훈: 역할을 바꾸는 것과 그 역할로 접속하는 것은 다르다.**
세션 설정에 딸린 동작은 이 시험으로 재현되지 않는다.

## 보안 원칙 (W1에서 확정)

- **읽기는 필요한 것만, 쓰기는 거의 열지 않는다.** 하트·투표 조작은 RPC 함수로 처리한다.
  클라이언트가 `heart_transaction` 을 INSERT 하거나 `heart_balance` 를 UPDATE 할 수 있으면
  하트를 무한정 만들 수 있다.
- **가입도 수정도 RPC 하나뿐이다.** `app_user` 에는 INSERT 도 UPDATE 도 열려 있지 않다.
  W1 에서 `GRANT UPDATE (nickname, class_id, gender)` 로 열어뒀으나 W11 에서 회수했다
  — 그 경로는 온보딩의 검증(2~20자·성별 필수·고를 수 있는 학급)을 전부 우회했다.
- **가입은** `app_user` INSERT 권한은 브라우저에 없다 — 열어주면 같은 문장에
  `heart_balance` 나 `is_synthetic` 을 끼워 넣을 수 있다. 가입은 `complete_onboarding()`
  하나뿐이다 (`db/rls/onboarding.sql`). 새 화면에서 쓰기가 필요해지면 RPC 를 먼저 의심한다.
- **id 로 남을 지목할 수 있는 경로를 만들지 않는다.** `app_user.id` 는 1부터 이어지는
  정수다. 친구 요청 INSERT 를 열었더니 코드 없이 전체 가입자를 지목할 수 있었다.
  친구 관련 쓰기는 전부 `db/rls/friends.sql` 의 RPC 로만 한다.
  ⚠️ **W10 친구 추천이 이 원칙을 좁은 범위에서 연다** — 같은 학교·비친구·비더미에
  한해 코드 없이 요청할 수 있다. `send_request_to()` 가 대상이 정말 추천 목록에
  있는지 **서버에서 다시 확인**하는 것이 이 기능의 안전장치 전부다. 손대지 말 것.
  경위는 [[DECISIONS]].
- ⚠️ **게시판의 학교 경계는 기술로 막혀 있지만, 소속은 자기신고다.**
  다른 학교 계정으로 14경로를 뚫어봐 전부 막힌 것을 확인했다(시험에 포함).
  그러나 온보딩에서 **아무 학교나 고를 수 있고** 익명 계정은 무제한이라,
  "그 학교 사람인가"는 보증되지 않는다. 불특정 다수에게 열 때 먼저 볼 항목이다.
  경위는 [[DECISIONS]].
- **남의 닉네임이 필요하면 뷰를 쓴다.** `app_user` 는 본인 행만 읽힌다.
  게시판 목록에 글쓴이 이름을 띄우려고 정책을 넓히지 않고 `board_post` 뷰를 뒀다.
- **컬럼을 가려야 하면 뷰를 쓴다.** RLS 는 행 단위라 컬럼을 숨기지 못한다.
  `vote_received` 는 직접 접근을 막고 `my_vote_received` 뷰로만 노출한다
  — `voter_id`("누가 나를 뽑았나")가 하트를 받고 파는 유료 정보이기 때문.
- RLS 를 고친 뒤에는 **양방향으로** 검증한다. 전부 막아도 침투 시험은 통과하므로,
  정상 동작 시험이 함께 있어야 의미가 있다.

## 합성 데이터가 없는 테이블

생성기가 아직 다루지 않아 비어 있다. 필요해지면 그때 만든다.

| 테이블 | 이유 |
|---|---|
| `block_record`, `friend_recommendation` | MVP 화면 범위 밖 |
| `report`, `sanction` | MVP 화면 범위 밖 (설정값은 yaml에 준비됨) |
| `meal_plan`, `timetable`, `school_notice`, `school_event`, `external_sync_log` | P3 NEIS 연동에서 채운다. **화면은 W8** |
| `post`, `post_comment`, `post_like`, `comment_like` | 실유저는 W9 부터 쓴다. **합성 생성기는 아직 안 만듦** |

## 스키마 적용 시 주의

`db/ddl/70_deferred_v2.sql`은 **적용하지 않는다.** MVP 대상이 아니다.
스키마 생성 명령은 README 참조 (파일을 명시적으로 나열한다 — 와일드카드 쓰지 말 것).

## 환경

| 용도 | 위치 | 비고 |
|---|---|---|
| 합성 데이터 DB | 로컬 Docker `pgtest` (포트 5433) | `postgres:16`, DB `pingv2`, 계정 `postgres`/`test` |
| 실유저 DB | Supabase | 구축·운영 중. 접속은 Session pooler 로만 |
| 구 서비스 분석 DB | Docker `mysql` (포트 3307) | `final`/`hackle`. **읽기만** |

로컬 DB 재생성:
```
docker run -d --name pgtest -e POSTGRES_PASSWORD=test -e POSTGRES_DB=pingv2 -p 5433:5432 postgres:16
```

## 적재 시 주의

**대량 적재 후 두 파일을 반드시 실행한다.**

`db/ddl/95_resync_sequences.sql` — identity 컬럼에 id를 직접 지정해 넣으면
시퀀스가 전진하지 않아서, 이후 실유저 가입 시 id=1을 발급하려다 PK 충돌로
실패한다. 실제로 재현된 문제다.

`db/ddl/96_backfill_updated_at.sql` — 증분 워터마크(`updated_at`)의 기본값이
`now()` 라, COPY 로 부어 넣으면 786만 행이 전부 "적재한 순간"이 된다.
3개월치가 하루에 뭉치고 BigQuery 파티션이 무의미해진다. 각 행의 원래 시각으로
되돌린다. 경위는 [[DECISIONS]].

## BigQuery

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
  커밋된 트랜잭션이 영영 누락되지 않는다. 경위는 [[DECISIONS]].

## 확정된 제약

- 합성 데이터 규모: **유저 5,000명 / 3개월치**
- 실유저와 합성 데이터는 **같은 DB에 섞지 않는다.** BigQuery 적재 시 `is_synthetic` 플래그로 구분.
- 익명 게시판은 v1 제외 (모니터링 인력 없이 열지 않는다)
- 외모·신체 관련 질문 제외 (`question_category.is_sensitive`로 표시)
- 전화번호 수집 안 함 (웹이라 연락처 동기화 자체가 불가)
- **내용은 학생용, 이용자는 성인.** 만들려는 것이 학생용 서비스이므로 질문·화면은
  학교 맥락으로 만들고, 그것이 작동하는지는 성인 지인이 확인한다.
  **만 14세 미만 가입 금지**를 가입 화면과 개인정보처리방침에 명시한다 —
  생년월일을 받지 않으므로 검증 수단이 없고, 받으면 개인정보 수집이 된다.
  자기 신고 고지로 갈음한다. ([[DECISIONS]])
- **접속 로그는 반드시 쌓는다.** 분석 자체는 합성 데이터로 하더라도,
  실유저 몇 명의 로그가 흐르는 **구조**가 있어야 파이프라인이 의미를 갖는다.
- **후보가 모자라면 스코프를 낮추지 않고 다른 친구로 채운다.** 채운 수를
  `vote_item.padded_count` 에 남기고 화면에도 밝힌다. 이용자가 여러 학교로
  흩어져도 CLASS·SCHOOL 질문이 살아 있게 하는 장치다.

## 이 프로젝트의 진짜 목표

**실서비스 운영이 아니라 데이터 파이프라인과 분석이다.** 웹앱은 실데이터를 만드는
수단이고, 클로즈드 테스트는 그 데이터를 얻는 방법이다. 기능 판단이 갈릴 때는
"분석할 데이터가 남는가"를 기준으로 정한다 — 예를 들어 이용자가 여러 학교로
흩어지는 것은 제품에는 손해지만 **분석에는 학교 차원이 생기는 이득**이다.

## 하기로 했지만 순서가 없는 기능

- ~~자유게시판~~ → **W9 에서 열었다.** 닉네임 노출 · 학교 단위 · 신고 포함
- **지목한 사람에게 익명 메시지** — 스키마 **없음**. 받은 투표에서 "나를 뽑은
  사람"에게 보낸다. 보내는 쪽은 상대가 누군지 모른다
- **채팅방 열기 (하트 차감)** — 스키마 **없음**. 하트 소비처가 하나 더 생긴다

⚠️ 셋 다 자유 텍스트가 사람에게 직접 간다. 익명 게시판을 뺐던 이유가 그대로
적용되고, **1:1 메시지는 공개 게시판보다 위험하다** — 사적인 메시지는 받은 사람이
말하기 전까지 아무도 모른다. 열기 전에 **차단·신고 화면**이 먼저 있어야 한다
(`block_record`·`report` 는 테이블만 있고 화면이 없다). 자세한 것은 [[design-spec]] 2.2.

## 미결 사항

- ~~후보 풀이 4명 미만일 때의 처리~~ → **해소.** 스코프는 유지하고 **친구 중 다른
  사람으로 채운다.** 채운 수는 `vote_item.padded_count` 에 남고 화면에도 밝힌다.
  친구 전체로도 4명이 안 되면 그 질문은 내지 않는다. 경위는 [[DECISIONS]].

## 문서 규칙

- 스키마 구조는 **DDL이 진실**이다. 문서에 테이블 정의를 복사하지 않는다.
- 코드 설명, 명령어 나열을 문서에 적지 않는다. 스크립트가 진실이다.
- 문서에는 **코드가 말해주지 못하는 것**만 남긴다: 결정과 이유, 제약, 실패한 시도, 미결 질문.
- 설계 결정이 내려지면 [[DECISIONS]]에 추가한다.
- 문서 간 참조는 `[[문서명]]` 형식 (노드 기반 위키 변환 대비).
