---
title: 위키 색인
group: 위키
tags: [위키, 색인]
---

# 위키 색인

이 저장소의 문서 전체 목록이다. **손으로 고치지 않는다** —
`python db/wiki_index.py` 가 다시 만든다.

문서는 세 층이다. 자세한 것은 [[CLAUDE|CLAUDE.md]] 의 *위키 구조*.

| 층 | 무엇 | 고치는 주체 |
|---|---|---|
| 1 | `raw/` 원본 — 회의록·분석·외부 자료 | **사람만** |
| 2 | `docs/` 위키 — 원본과 코드에서 뽑아 만든 것 | 에이전트 |
| 3 | `CLAUDE.md` 규약 — 그 일을 어떻게 하는지 | 사람 + 에이전트 |

## 낱장 문서

- [[CLAUDE|프로젝트 규약]] — 에이전트가 매번 읽는다. 위키 구조와 워크플로.
- [[README|저장소 소개]] — 무엇을 만드는 프로젝트인가.
- [[DECISIONS|결정 색인]] — 결정 노드 56개 목록.
- [[design-spec|설계 명세]] — 통독용. 배경·목표·단계.
- [[ONBOARDING|온보딩]] — 저장소를 처음 받은 사람용.
- [[TEAM-PLAN|팀 작업 절차]] — 협업·스키마 변경 영향 범위.
- [[erd|ERD (생성물)]] — `db/erd.py` 가 살아 있는 DB 에서 뽑는다.
- [[log|작업 이력]] — 위키에 무엇을 언제 했나.

## 회의록 <sub>`raw/meetings` · 0</sub>

팀 회의 원본. 고치지 않는다.

_아직 없다._

## 구 서비스 분석 <sub>`raw/legacy-analysis` · 10</sub>

이 프로젝트가 시작된 근거. 2026-07-28 조사.

- [[00_key_findings|핵심 발견 Top 10]] — 전체 리포트를 관통하는 가장 중요한 발견만 추려서 정리. 각 항목은 어느 문서에서 나온 건지 링크 걸어둠 — 근거/쿼리는 해당 문서 참고.
- [[01_table_notes|`final` DB 테이블별 메모]] — 조사 시점: 2026-07-27 / DB: mysql 컨테이너(포트 3307) → final 스키마
- [[02_retention_platform|리텐션(잔존) & 플랫폼 분석]] — 조사 시점: 2026-07-28 / DB: mysql 컨테이너(포트 3307) → final/hackle 스키마
- [[03_social_graph|소셜 그래프 분석 — 친구요청 & 차단]] — 조사 시점: 2026-07-28 / DB: mysql 컨테이너(포트 3307) → final 스키마
- [[04_voting_funnel|투표 퍼널 분석 — 노출부터 답변 공개까지]] — 조사 시점: 2026-07-28 / DB: mysql 컨테이너(포트 3307) → final 스키마
- [[05_deep_dive_notes|`final` DB 딥다이브 — 테이블 조인 기반 분석]] — 조사 시점: 2026-07-28 / DB: mysql 컨테이너(포트 3307) → final 스키마
- [[06_payment_report|결제(하트) 딥다이브 리포트]] — 조사 시점: 2026-07-28 / DB: mysql 컨테이너(포트 3307) → final 스키마
- [[07_report_ban_system|신고 & 제재 시스템 분석]] — 조사 시점: 2026-07-28 / DB: mysql 컨테이너(포트 3307) → final 스키마
- [[08_attendance_feature|출석 기능 분석]] — 조사 시점: 2026-07-28 / DB: mysql 컨테이너(포트 3307) → final 스키마
- [[README|서비스 분석 리포트 인덱스]] — 조사 대상: 익명 투표 SNS 앱 원본 덤프 → mysql 컨테이너의 final/hackle 스키마로 복원 후 분석.

## 외부 자료 <sub>`raw/external` · 0</sub>

API 스펙 등 바깥에서 온 문서.

_아직 없다._

## 결정 <sub>`docs/decisions` · 56</sub>

왜 그렇게 했는지. 하나가 한 노드다.

- [[ads-payments-stub|MVP에서 광고와 결제를 스텁으로 처리]] — 스키마(ad_impression, heart_purchase)는 이미 준비돼 있으므로 나중에
- [[airflow-two-services|Airflow 는 공식 컴포즈 대신 2개 서비스로 줄인다]] — 경험이 없어서 서비스가 8개면 어디가 죽었는지 판단할 수가 없다.
- [[anonymous-auth-no-pii|개인정보를 일절 받지 않는 익명 인증]] — Supabase Anonymous Sign-in으로 접속 즉시 계정이 생기고, 유저가 입력하는 것은
- [[backfill-updated-at|대량 적재 후 `updated_at` 을 각 행의 원래 시각으로 되돌린다]] — 두고, 대량 적재 직후 함께 돌린다.
- [[bigquery-direct-no-gcs|BigQuery 에 GCS 를 경유하지 않고 직접 올린다]] — . GCS_BUCKET 은 비워 둔다.
- [[bigquery-source-column|실유저와 합성 데이터를 같은 BigQuery 테이블에 `_source` 로 섞는다]] — 테이블 하나다. 적재할 때 _source 컬럼을 붙이고, 키를 (_source, id) 로 쓴다.
- [[board-school-scope|게시판 범위는 학교, 카테고리는 하나]] — 끌어온다. 카테고리는 시드에 5개가 있지만 자유게시판 하나만 연다.
- [[candidate-rows-kept|후보 4명을 행으로 저장하고 셔플 전후를 모두 남긴다]] — 또 "어떤 후보였을 때 셔플을 눌렀는가"는 광고 수익과 직결되는 분석인데 데이터가 없으면 못 본다.
- [[client-write-minimal|클라이언트에 쓰기 권한을 거의 주지 않는다]] — 클라이언트가 직접 INSERT/UPDATE 하지 못하게 막는다. 나중에 RPC 함수로 처리한다.
- [[closed-test-adults|성인 지인 대상 클로즈드 테스트로 한정]] — 필요하고, 외모 관련 투표와 익명 게시판을 미성년자에게 열면서 모니터링이 없으면 감당할 수 없다.
- [[drop-admin-user|admin_user 를 없애고 app_user.is_admin 하나로 접는다]] — 유지할 근거가 "언젠가 운영 화면을 만들면"뿐이었다. 그 언젠가가 이 프로젝트의
- [[events-on-meal-calendar|학사일정을 급식 달력에 얹는다 — 따로 만들지 않고]] — 날짜 칸 아래 점이 그날 일정이고, 달력 아래에 그 달 일정이 통째로 나온다.
- [[friend-invite-code-two-step|친구 맺기는 초대 코드로만, 요청·수락 2단계로]] — 맺어지는 절차는 요청 → 수락이며, friend_request 와 friendship 의 직접 쓰기는
- [[friend-recommend-same-school|친구 추천 — "초대 코드로만"을 같은 학교 범위에서 연다]] — 했다. "안 볼래"로 목록에서 뺄 수도 있다.
- [[friendship-ended-at|친구를 끊어도 행을 지우지 않는다]] — UNIQUE 는 살아 있는 관계에만 걸어(부분 유니크 인덱스) 끊었다 다시 맺기가
- [[gender-at-onboarding|성별을 온보딩에서 받는다]] — 성별은 온보딩 필수 항목이며, 서버가 비어 있으면 거부한다.
- [[global-scope-is-friends|`GLOBAL` 스코프는 "내 친구 전체"]] — 그리고 차단 사유 1위가 "모르는 사람임"이었다. 전체 가입자를 후보로 넣으면
- [[heart-balance-after|모든 하트 증감에 `balance_after`를 기록]] — 원장에 남지 않아서다(heart.777이 57,873건 팔렸는데 원장의 +777 행은 21건뿐). 잔액을 원장으로
- [[heart-unify-point|하트와 포인트를 하나로 통합]] — UI는 "하트"라 부르고 DB 컬럼명은 point여서 분석할 때마다 혼선이 있었다.
- [[history-based-navigation|화면 이동을 브라우저 이력에 싣는다]] — 홈으로 되돌린다. 화면 안의 닫기 버튼도 history.back() 을 거친다.
- [[integrity-checks-aged|정합성 검사 3종이 낡아 있었다]] — 셋 다 데이터가 아니라 검사가 틀린 경우였다.
- [[invite-link-after-deploy|초대 링크는 배포(W7) 이후로 미룬다]] — 친구 추가는 코드 입력 하나로 한다.
- [[invite-link-querystring|초대 링크는 동적 라우트 대신 쿼리스트링으로 만든다]] — 않는다. 내용을 지운 최소한의 /probe/x 로도 재현된다 — HTTP 500,
- [[join-requires-source|두 원천의 id 가 겹친다 — 조인에 `_source` 를 강제한다]] — P6 stg 층에서 대리키를 만들어 구조적으로 막는다.
- [[local-db-via-apply|로컬 DB 는 `apply.py` 로만 만든다]] — 마이그레이션 3종 뒤처진 채 몇 주를 돌았고, 그 결과:
- [[local-docker-airflow|Cloud Composer 대신 로컬 Docker Airflow]] — 로컬 Docker면 0원이고, 나중에 필요하면 작은 VM(월 3~4만원)으로 옮기면 된다.
- [[lower-scope-when-short|후보가 4명이 안 되면 스코프를 낮추고, 그래도 안 되면 질문을 내지 않는다]] — 낮춘다. GLOBAL 에서도 모자라면 그 질문은 출제하지 않는다(세션에 넣지 않는다).
- [[neis-merge-spans|NEIS 가 하루씩 주는 것을 기간으로 묶는다]] — 하나로 합쳐 start_date~end_date 로 저장한다. 사이에 낀 주말은 이어진
- [[no-anonymous-board|익명 게시판을 v1에서 제외]] — 전례가 있고, 1인 프로젝트로는 신고 검토를 감당할 수 없다. 사고가 났을 때 책임을 질 수 없는 기능은 열지 않는다.
- [[no-delete-propagation|원천의 삭제는 BigQuery 로 전파하지 않는다]] — BigQuery raw 에는 남는다.
- [[one-time-reply|1회성 답장을 연다 — 차단 화면 없이]] — 20하트, 30자. 힌트를 열었든 안 열었든 보낼 수 있다.
- [[open-named-board|자유게시판을 연다 — 글도 댓글도 닉네임으로]] — 쓰지 않고 nullable 로 바꿨다(마이그레이션 005).
- [[org-borrows-school-info|테스트 조직은 이름을 유지하고 실제 학교의 정보를 빌려 쓴다]] — 급식·시간표·학사일정은 서울고등학교(표준학교코드 7010083)의 공개 데이터를 쓴다.
- [[pad-candidates-keep-scope|후보가 모자라면 스코프를 낮추지 않고 다른 친구로 채운다]] — 다른 사람으로 빈 자리를 채운다. 채운 인원 수는 vote_item.padded_count 에
- [[profile-edit-rpc|프로필 수정도 RPC 하나로 — 직접 UPDATE 권한 회수]] — 가입은 complete_onboarding() 이 닉네임 2~20자, 성별 필수, 학급 존재를
- [[purge-synthetic-data|합성 데이터를 전부 지운다 — 낡아서]] — Supabase 는 손대지 않았다. 애초에 합성이 0행이었다 — 더미 친구는 진작에 정리됐다.
- [[remove-circular-fk|순환 FK를 제거하는 방향으로 스키마 정리]] — 알 수 없다. 원장이 원인을 가리키는 단방향이 자연스럽다.
- [[report-first-block-later|신고는 게시판과 함께, 차단은 뒤로]] — 다르다. 게시판은 공개 공간이라 "안 보이게"보다 "내려가게"가 먼저 필요하다.
- [[report-sanction-fk|신고와 제재를 FK로 연결하고 정책을 데이터로 정의]] — 자동 제재 임계값을 저장한다.
- [[school-boundary-self-reported|학교 경계는 기술로 막지만, 소속은 자기신고다]] — "그 학교 사람인가"는 검증하지 않는다. 이 한계를 문서에 명시하고 그대로 간다.
- [[school-info-write-revoked|학사일정·공지의 쓰기 권한이 열려 있었다]] — INSERT·UPDATE·DELETE 권한이 남아 있었다. 급식은 W8 에서
- [[selectable-hints|힌트를 골라 사게 바꾼다 — 순차 4단계 폐기]] — 값이 커서(합계 2,000하트) 실제로 끝까지 사는 사람이 없었고, 순서가 고정이라
- [[shuffle-once-constraint|셔플은 DB 제약으로 1회를 강제한다]] — 스키마로 막으면 코드에 버그가 있어도 데이터가 오염되지 않는다.
- [[signup-single-rpc|가입은 RPC 하나로만 한다]] — RLS 는 행 단위라 이걸 막지 못한다.
- [[soft-delete-marking|삭제를 전파하지는 않되, 표시는 한다 (앞 항목 보완)]] — 다만 _deleted_at 을 찍어 지워진 행임을 표시한다.
- [[student-mvp-adult-testers|학생용 MVP를 만들고, 검증은 성인이 한다]] — 다만 실제 이용자는 여전히 성인 지인이며, 그들이 학생용 MVP가 작동하는지 확인한다.
- [[supabase-session-pooler|Supabase 연결은 Session pooler 를 쓴다]] — 로 접속한다.
- [[synthetic-real-separation|합성 데이터와 실유저 데이터를 분리]] — BigQuery 적재 시 is_synthetic 플래그로 구분한다. 합성 규모는 유저 5,000명 / 3개월치.
- [[testers-pick-real-school|NEIS 연동 후 테스터는 실제 학교 중 하나를 고른다]] — 성인 테스터는 다니지 않는 실제 학교를 골라 쓴다. 이는 문제되지 않는다.
- [[topup-stub-daily-limit|하트 충전은 결제 없는 스텁 — 대신 하루 한 번]] — 하트가 들어온다. 대신 어떤 상품을 골랐든 하루에 한 번만 받을 수 있다.
- [[voter-identity-view-only|투표자 신원은 뷰로만 노출한다]] — 대신 my_vote_received 뷰로만 접근하며, 이 뷰가 reveal_status 에 따라
- [[watermark-lag-5min|워터마크를 스냅샷보다 5분 뒤로 물려 저장한다]] — 매 실행이 최근 5분치를 다시 읽는다.
- [[watermark-updated-at|증분 워터마크를 `updated_at` 하나로 통일한다]] — . 적재 조건은 테이블과 무관하게
- [[webapp-first-track|웹앱을 최우선 트랙으로 재편]] — 9단계를 다 끝내도 나오는 것은 BigQuery 테이블과 대시보드뿐이었다. 대화에서는
- [[withdraw-keeps-rows|계정 삭제는 행을 지우지 않는다]] — 없어 누가 탈퇴했는지 특정할 수 없었다. 사유의 57%가 "기타"였고, 탈퇴 사유를
- [[withdrawal-user-id|탈퇴 기록에 유저 식별자를 넣는다]] — 누가 탈퇴했는지 특정할 수 없었다. 탈퇴 사유를 유저 속성과 교차분석하는 게 원천 봉쇄됐다.

## 운영 참조 <sub>`docs/ops` · 5</sub>

실제로 그 작업을 할 때 필요한 값과 절차.

- [[ops-bigquery|BigQuery 적재]] — 다만 결제가 붙어 있으면 한도를 넘을 때 막히지 않고 과금된다. 예산 알림을 걸어둔다.
- [[ops-local-testing|혼자 시험하기 (더미 친구)]] — 투표는 친구가 5명이어야 열리고 문항마다 후보가 4명 필요하다. 창을 다섯 개 띄울 수
- [[ops-rebuild|DB 를 처음부터 다시 만들기]] — python db/apply.py --target supabase          # DDL + migrations
- [[ops-school-data|조직·학교 데이터]] — 이름은 테스트 조직이지만 급식·시간표·학사일정은 서울고등학교의 공개 데이터를 쓴다.
- [[ops-webapp|웹앱 (web/)]] — 프로덕션 빌드는 정상이지만 로컬에서 확인이 불가능하므로, 동적 라우트 대신

---

문서 79개 · `python db/wiki_index.py` 로 갱신
