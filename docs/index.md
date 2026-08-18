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

## 결정 <sub>`docs/decisions` · 84</sub>

왜 그렇게 했는지. 하나가 한 노드다.

- [[activity-by-retention-tier|활동 강도는 잔존 구간마다 다르다]] — 100~200회, 1달 이내 25~70회, 1주 이내 4~20회, 당일만 1~4회, 미접속 0회.
- [[ads-payments-stub|MVP에서 광고와 결제를 스텁으로 처리]] — 스키마(ad_impression, heart_purchase)는 이미 준비돼 있으므로 나중에
- [[airflow-two-services|Airflow 는 공식 컴포즈 대신 2개 서비스로 줄인다]] — 경험이 없어서 서비스가 8개면 어디가 죽었는지 판단할 수가 없다.
- [[anonymous-auth-no-pii|개인정보를 일절 받지 않는 익명 인증]] — Supabase Anonymous Sign-in으로 접속 즉시 계정이 생기고, 유저가 입력하는 것은
- [[app-follows-generator|앱을 생성기에 맞춘다 — 다만 생성 시험이 끝난 뒤 한 번에]] — 생성기를 되돌리지 않는다. 단 지금은 고치지 않는다 — 생성 파라미터가 아직
- [[appearance-questions-for-report-rate|외모·신체 질문을 연다 — 민감 질문이 없으면 신고율을 못 잰다]] — (migration 012). 합성 데이터에서 전체 질문의 6% 를 외모·스타일 질문으로 만든다.
- [[backfill-updated-at|대량 적재 후 `updated_at` 을 각 행의 원래 시각으로 되돌린다]] — 두고, 대량 적재 직후 함께 돌린다.
- [[bigquery-direct-no-gcs|BigQuery 에 GCS 를 경유하지 않고 직접 올린다]] — . GCS_BUCKET 은 비워 둔다.
- [[bigquery-source-column|실유저와 합성 데이터를 같은 BigQuery 테이블에 `_source` 로 섞는다]] — 테이블 하나다. 적재할 때 _source 컬럼을 붙이고, 키를 (_source, id) 로 쓴다.
- [[board-school-scope|게시판 범위는 학교, 카테고리는 하나]] — 끌어온다. 카테고리는 시드에 5개가 있지만 자유게시판 하나만 연다.
- [[bulk-load-batch-rows|합성 대량 적재는 배치를 20만 행으로 키운다]] — 합성 데이터(--source local) 전량 적재에서만 20만을 쓴다.
- [[candidate-rows-kept|후보 4명을 행으로 저장하고 셔플 전후를 모두 남긴다]] — 또 "어떤 후보였을 때 셔플을 눌렀는가"는 광고 수익과 직결되는 분석인데 데이터가 없으면 못 본다.
- [[class-size-for-class-scope|같은 반 친구는 비율이 아니라 **수**가 기준이다 — 4명이 있어야 투표가 된다]] — 상한 35), 같은 반에서 친구를 고르는 비율도 올린다(same_class_ratio
- [[client-write-minimal|클라이언트에 쓰기 권한을 거의 주지 않는다]] — 클라이언트가 직접 INSERT/UPDATE 하지 못하게 막는다. 나중에 RPC 함수로 처리한다.
- [[closed-test-adults|성인 지인 대상 클로즈드 테스트로 한정]] — 필요하고, 외모 관련 투표와 익명 게시판을 미성년자에게 열면서 모니터링이 없으면 감당할 수 없다.
- [[confirm-v4-with-known-limits|합성 데이터 v4 를 확정한다 — 한계 5건을 고치지 않고 문서화한다]] — 확정 직전에 돌린 정밀 EDA 에서 결함 1건 · 경계 5건이 나왔지만,
- [[daily-rhythm-night-peak|하루 리듬을 붙인다 — 최대 봉우리는 점심이 아니라 밤 22시다]] — 12~13시 최대 봉우리"를 밤 22~23시로 바꾼다.
- [[ddl-comments-rot-with-migrations|DDL 주석은 마이그레이션 뒤에 낡는다 — 파일이 아니라 순서가 진실이다]] — 말했다. 그 요금제는 W14(마이그레이션 006)가 반년 전에 없앤 것이고, 현행은
- [[dow-from-legacy-attendance|요일 패턴은 구 서비스 출석 로그를 따라간다 — 우하향이 아니라 V자]] — (raw/legacy-analysis/08_attendance_feature.md §2)을 그대로 옮긴다.
- [[drop-admin-user|admin_user 를 없애고 app_user.is_admin 하나로 접는다]] — 유지할 근거가 "언젠가 운영 화면을 만들면"뿐이었다. 그 언젠가가 이 프로젝트의
- [[events-on-meal-calendar|학사일정을 급식 달력에 얹는다 — 따로 만들지 않고]] — 날짜 칸 아래 점이 그날 일정이고, 달력 아래에 그 달 일정이 통째로 나온다.
- [[expired-session-status|중도 이탈 세션은 EXPIRED 로 적는다 — 완료율이 98.6%로 보이던 이유]] — 이미 있는 값이라 스키마는 건드리지 않는다.
- [[friend-invite-code-two-step|친구 맺기는 초대 코드로만, 요청·수락 2단계로]] — 맺어지는 절차는 요청 → 수락이며, friend_request 와 friendship 의 직접 쓰기는
- [[friend-recommend-same-school|친구 추천 — "초대 코드로만"을 같은 학교 범위에서 연다]] — 했다. "안 볼래"로 목록에서 뺄 수도 있다.
- [[friendship-ended-at|친구를 끊어도 행을 지우지 않는다]] — UNIQUE 는 살아 있는 관계에만 걸어(부분 유니크 인덱스) 끊었다 다시 맺기가
- [[gender-at-onboarding|성별을 온보딩에서 받는다]] — 성별은 온보딩 필수 항목이며, 서버가 비어 있으면 거부한다.
- [[generator-emits-updated-at|`updated_at` 을 생성기가 직접 싣는다 — 백필 UPDATE 가 3시간을 먹었다]] — 적재 후 96_backfill_updated_at.sql 이 고칠 것이 없어진다.
- [[global-scope-is-friends|`GLOBAL` 스코프는 "내 친구 전체"]] — 그리고 차단 사유 1위가 "모르는 사람임"이었다. 전체 가입자를 후보로 넣으면
- [[growth-curve-two-channels|성장 곡선은 가입과 활동 두 갈래로 건다 — 그리고 국면이 안 겹치면 끈다]] — 곡선은 두 갈래로 작용한다 — signup_share 가 가입 시점을 나누고,
- [[heart-balance-after|모든 하트 증감에 `balance_after`를 기록]] — 원장에 남지 않아서다(heart.777이 57,873건 팔렸는데 원장의 +777 행은 21건뿐). 잔액을 원장으로
- [[heart-economy-rebalance|하트 경제를 다시 잡는다 — v1 실측을 버린다]] — 3하트 30% · 4하트 20% · 5~10하트 10%) 로 바꾼다. 광고 보상은 0 으로 한다
- [[heart-unify-point|하트와 포인트를 하나로 통합]] — UI는 "하트"라 부르고 DB 컬럼명은 point여서 분석할 때마다 혼선이 있었다.
- [[history-based-navigation|화면 이동을 브라우저 이력에 싣는다]] — 홈으로 되돌린다. 화면 안의 닫기 버튼도 history.back() 을 거친다.
- [[integrity-checks-aged|정합성 검사 3종이 낡아 있었다]] — 셋 다 데이터가 아니라 검사가 틀린 경우였다.
- [[invite-link-after-deploy|초대 링크는 배포(W7) 이후로 미룬다]] — 친구 추가는 코드 입력 하나로 한다.
- [[invite-link-querystring|초대 링크는 동적 라우트 대신 쿼리스트링으로 만든다]] — 않는다. 내용을 지운 최소한의 /probe/x 로도 재현된다 — HTTP 500,
- [[join-requires-source|두 원천의 id 가 겹친다 — 조인에 `_source` 를 강제한다]] — P6 stg 층에서 대리키를 만들어 구조적으로 막는다.
- [[local-db-via-apply|로컬 DB 는 `apply.py` 로만 만든다]] — 마이그레이션 3종 뒤처진 채 몇 주를 돌았고, 그 결과:
- [[local-docker-airflow|Cloud Composer 대신 로컬 Docker Airflow]] — 로컬 Docker면 0원이고, 나중에 필요하면 작은 VM(월 3~4만원)으로 옮기면 된다.
- [[lognormal-not-uniform|시간 간격을 균등분포에서 로그정규로 바꾼다 — v5]] — 균등분포의 stddev)가 6종에서 1.0 근처로 나왔다 — 완전한 균등이라는 뜻이다.
- [[lower-scope-when-short|후보가 4명이 안 되면 스코프를 낮추고, 그래도 안 되면 질문을 내지 않는다]] — 낮춘다. GLOBAL 에서도 모자라면 그 질문은 출제하지 않는다(세션에 넣지 않는다).
- [[neis-merge-spans|NEIS 가 하루씩 주는 것을 기간으로 묶는다]] — 하나로 합쳐 start_date~end_date 로 저장한다. 사이에 낀 주말은 이어진
- [[never-voters-by-friend-count|해금하고도 투표 안 하는 유저를 의도적으로 만든다 — 친구가 적을수록 많이]] — 확률로 만든다. 친구가 딱 5명이라 겨우 연 사람이 가장 많이 안 하고,
- [[no-anonymous-board|익명 게시판을 v1에서 제외]] — 전례가 있고, 1인 프로젝트로는 신고 검토를 감당할 수 없다. 사고가 났을 때 책임을 질 수 없는 기능은 열지 않는다.
- [[no-delete-propagation|원천의 삭제는 BigQuery 로 전파하지 않는다]] — BigQuery raw 에는 남는다.
- [[no-schema-change-for-synthetic|합성 데이터를 위해 스키마를 바꾸지 않는다]] — (TEAM-PLAN 1장). 분포의 비현실성은 거의 전부 파라미터 문제였고, 실제로
- [[one-time-reply|1회성 답장을 연다 — 차단 화면 없이]] — 20하트, 30자. 힌트를 열었든 안 열었든 보낼 수 있다.
- [[open-named-board|자유게시판을 연다 — 글도 댓글도 닉네임으로]] — 쓰지 않고 nullable 로 바꿨다(마이그레이션 005).
- [[org-borrows-school-info|테스트 조직은 이름을 유지하고 실제 학교의 정보를 빌려 쓴다]] — 급식·시간표·학사일정은 서울고등학교(표준학교코드 7010083)의 공개 데이터를 쓴다.
- [[pad-candidates-keep-scope|후보가 모자라면 스코프를 낮추지 않고 다른 친구로 채운다]] — 다른 사람으로 빈 자리를 채운다. 채운 인원 수는 vote_item.padded_count 에
- [[partition-ordered-extract|파티션 테이블로 부을 때는 파티션 컬럼 순서로 꺼낸다]] — 파티션이 걸린 표(tables.yaml 의 incremental, 파티션은 updated_at)에만 해당한다.
- [[popularity-floor-is-activity|인기도 45%는 도달할 수 없다 — 바닥은 활동 불균형이다]] — 45%는 파라미터로 도달할 수 없다는 것이 실측으로 드러났다.
- [[profile-edit-rpc|프로필 수정도 RPC 하나로 — 직접 UPDATE 권한 회수]] — 가입은 complete_onboarding() 이 닉네임 2~20자, 성별 필수, 학급 존재를
- [[purge-synthetic-data|합성 데이터를 전부 지운다 — 낡아서]] — Supabase 는 손대지 않았다. 애초에 합성이 0행이었다 — 더미 친구는 진작에 정리됐다.
- [[reactivation-cohort|휴면했다 돌아오는 유저를 만든다 — 3월에 몰리되 다른 달에도 있게]] — 복귀 시점은 봄학기에 가중치를 주되 다른 달에도 나오게 한다.
- [[remove-circular-fk|순환 FK를 제거하는 방향으로 스키마 정리]] — 알 수 없다. 원장이 원인을 가리키는 단방향이 자연스럽다.
- [[report-first-block-later|신고는 게시판과 함께, 차단은 뒤로]] — 다르다. 게시판은 공개 공간이라 "안 보이게"보다 "내려가게"가 먼저 필요하다.
- [[report-sanction-fk|신고와 제재를 FK로 연결하고 정책을 데이터로 정의]] — 자동 제재 임계값을 저장한다.
- [[retention-quarter-tier|잔존 구간에 30~89일을 새로 넣는다 — v1 실측에서 일부러 벗어난다]] — 나머지 비율을 조금씩 덜어 재배분한다. long_term 의 하한도 30일 → 90일로 올린다.
- [[row-cap-to-query-cap|행수 상한을 버리고 쿼리 하드캡으로 바꾼다]] — 쓰지 않는다. 대신 BigQuery 커스텀 할당량(일일 쿼리 바이트 상한) 을 건다.
- [[row-guardrail-measured|행수 가드레일을 실측으로 다시 잡는다 — 위험은 행수가 아니라 쿼리량이다]] — 단다 — Looker 를 raw 에 직접 붙이지 않는다(P6 stg/mart 선행),
- [[school-boundary-self-reported|학교 경계는 기술로 막지만, 소속은 자기신고다]] — "그 학교 사람인가"는 검증하지 않는다. 이 한계를 문서에 명시하고 그대로 간다.
- [[school-info-write-revoked|학사일정·공지의 쓰기 권한이 열려 있었다]] — INSERT·UPDATE·DELETE 권한이 남아 있었다. 급식은 W8 에서
- [[school-sequential-adoption|학교를 순차로 열고, 학급 수를 정원에서 유도한다]] — 개교일을 정하고, 가입일 순서로 그 시점에 열려 있는 학교 중에서 고른다.
- [[selectable-hints|힌트를 골라 사게 바꾼다 — 순차 4단계 폐기]] — 값이 커서(합계 2,000하트) 실제로 끝까지 사는 사람이 없었고, 순서가 고정이라
- [[sensitive-question-report-weight|민감 질문에 신고 성향을 심는다 — 안 심으면 플래그가 아무 의미도 없다]] — 준다.
- [[session-bounded-actions|유저의 직접 행동은 접속 세션 안에서만 일어난다 — v5]] — 만든다. 30분 넘게 비면 새 세션으로 나눈다. 자리가 없으면 그 행동을 만들지 않는다.
- [[shuffle-once-constraint|셔플은 DB 제약으로 1회를 강제한다]] — 스키마로 막으면 코드에 버그가 있어도 데이터가 오염되지 않는다.
- [[signup-single-rpc|가입은 RPC 하나로만 한다]] — RLS 는 행 단위라 이걸 막지 못한다.
- [[soft-delete-marking|삭제를 전파하지는 않되, 표시는 한다 (앞 항목 보완)]] — 다만 _deleted_at 을 찍어 지워진 행임을 표시한다.
- [[spring-spike-growth-curve|성장 곡선을 봄학기형으로 바꾼다 — 회복이 아니라 3월 스파이크 뒤 하강]] — 굴러가면서 관심이 식는 것이 학사 일정과 맞는다. 옛 곡선은 뒤로 갈수록
- [[student-mvp-adult-testers|학생용 MVP를 만들고, 검증은 성인이 한다]] — 다만 실제 이용자는 여전히 성인 지인이며, 그들이 학생용 MVP가 작동하는지 확인한다.
- [[supabase-session-pooler|Supabase 연결은 Session pooler 를 쓴다]] — 로 접속한다.
- [[synthetic-real-separation|합성 데이터와 실유저 데이터를 분리]] — BigQuery 적재 시 is_synthetic 플래그로 구분한다. 합성 규모는 유저 5,000명 / 3개월치.
- [[testers-pick-real-school|NEIS 연동 후 테스터는 실제 학교 중 하나를 고른다]] — 성인 테스터는 다니지 않는 실제 학교를 골라 쓴다. 이는 문제되지 않는다.
- [[topup-stub-daily-limit|하트 충전은 결제 없는 스텁 — 대신 하루 한 번]] — 하트가 들어온다. 대신 어떤 상품을 골랐든 하루에 한 번만 받을 수 있다.
- [[user-personas|페르소나는 분류가 아니라 생성 편의다]] — 혼합 · 트레잇 교차 · 무배정. 트레잇마다 따로 개인 편차를 곱한다.
- [[voter-identity-view-only|투표자 신원은 뷰로만 노출한다]] — 대신 my_vote_received 뷰로만 접근하며, 이 뷰가 reveal_status 에 따라
- [[watermark-lag-5min|워터마크를 스냅샷보다 5분 뒤로 물려 저장한다]] — 매 실행이 최근 5분치를 다시 읽는다.
- [[watermark-updated-at|증분 워터마크를 `updated_at` 하나로 통일한다]] — . 적재 조건은 테이블과 무관하게
- [[webapp-first-track|웹앱을 최우선 트랙으로 재편]] — 9단계를 다 끝내도 나오는 것은 BigQuery 테이블과 대시보드뿐이었다. 대화에서는
- [[withdraw-keeps-rows|계정 삭제는 행을 지우지 않는다]] — 없어 누가 탈퇴했는지 특정할 수 없었다. 사유의 57%가 "기타"였고, 탈퇴 사유를
- [[withdrawal-is-terminal|탈퇴는 종점이다 — 그 뒤로 어떤 로그도 남기지 않는다]] — 세션·투표·원장을 전부 훑어 가장 늦은 것을 찾은 다음 그 뒤에 놓는다.
- [[withdrawal-user-id|탈퇴 기록에 유저 식별자를 넣는다]] — 누가 탈퇴했는지 특정할 수 없었다. 탈퇴 사유를 유저 속성과 교차분석하는 게 원천 봉쇄됐다.

## 운영 참조 <sub>`docs/ops` · 9</sub>

실제로 그 작업을 할 때 필요한 값과 절차.

- [[ops-analysis-conventions|분석 쿼리 표준 — 노트북 4개에서 굳어진 규칙]] — 다시 쓰지 않아도 되게 만든다.
- [[ops-bigquery-team-access|BigQuery 팀 접속 안내]] — 혼동하기 쉬운 지점이라 갈라 둔다.
- [[ops-bigquery|BigQuery 적재]] — 다음 증설은 계산하고 시작한다. 결제가 붙어 있어 넘으면 막히지 않고 과금된다 —
- [[ops-local-testing|혼자 시험하기 (더미 친구)]] — 투표는 친구가 5명이어야 열리고 문항마다 후보가 4명 필요하다. 창을 다섯 개 띄울 수
- [[ops-p5-p7|P5~P7 시작하기 — 품질검증 · stg/mart · 대시보드]] — EDA까지 끝난 상태에서 다음 네 가지를 어떤 순서로, 어떤 명령으로
- [[ops-rebuild|DB 를 처음부터 다시 만들기]] — python db/apply.py --target supabase          # DDL + migrations
- [[ops-school-data|조직·학교 데이터]] — 이름은 테스트 조직이지만 급식·시간표·학사일정은 서울고등학교의 공개 데이터를 쓴다.
- [[ops-synthetic-data|합성 데이터 만들기]] — 설정 주석에 주장으로만 있던 것을 전체 규모로 확인했다 — 2만 명·12개월을 다시
- [[ops-webapp|웹앱 (web/)]] — 프로덕션 빌드는 정상이지만 로컬에서 확인이 불가능하므로, 동적 라우트 대신

## 테이블 <sub>`docs/tables` · 40</sub>

표 하나당 한 장. DDL·결정·검사·정책을 모아 뽑는다.

- [[ad_impression|ad_impression]] — 생성기가 만든다.
- [[app_user|app_user]] — "user" 는 Postgres 예약어라 app_user 로 명명한다. ★ 개인정보를 받지 않는다. 이메일·전화번호·실명·비밀번호 컬럼이 없
- [[block_record|block_record]] — 생성기가 만든다.
- [[board_category|board_category]] — 생성기가 만든다.
- [[comment_like|comment_like]] — 생성기가 만든다.
- [[friend_request|friend_request]] — 생성기가 만든다.
- [[friendship|friendship]] — user_low_id < user_high_id 를 강제해 와 가 중복 저장되는 것을 막는다.
- [[grade_class|grade_class]] — label: 화면에 보여줄 이름을 직접 지정하고 싶을 때만 채운다. 비어 있으면 앱이 "N학년 M반"으로 조립한다. 일반 학교는 비워두고, 
- [[heart_product|heart_product]] — 구 스키마는 productId 문자열만 있고 가격·수량이 코드에만 있어 매출 계산 시 값을 하드코딩해야 했다.
- [[heart_purchase|heart_purchase]] — 성공/실패를 한 테이블에 status 로 통합한다. 구 스키마는 별도 테이블이었고 실패 로깅이 2023-09에 조용히 끊겨 그 이후로는 실패
- [[heart_transaction|heart_transaction]] — 이 프로젝트에서 가장 중요한 테이블. 구 스키마의 원장은 순합계가 201만인데 유저 잔액 총합은 20억이었다. 가입 지급과 충전이 원장에 남
- [[heart_transaction_type|heart_transaction_type]] — 구 스키마는 delta_point 값만 보고 의미를 역추론해야 했다 (5~15 = 투표 적립, -300 = 힌트 구매 ... 전부 추측이었다
- [[hint_purchase|hint_purchase]] — ⚠️ 아래 정의는 최초 설계이고, W14(마이그레이션 006·007)가 갈아치웠다. 이 파일만 읽으면 죽은 요금제를 현행으로 오해한다. 현행
- [[meal_menu_item|meal_menu_item]] — 메뉴를 한 덩어리 텍스트가 아니라 요리 단위로 분리한다. "인기 급식 메뉴" 분석과 알레르기 필터가 가능해진다.
- [[meal_plan|meal_plan]] — 학교·날짜·끼니에 UNIQUE. 같은 날 중복 급식이 들어오는 것을 DB가 막는다.
- [[post|post]] — 생성기가 만든다.
- [[post_comment|post_comment]] — ⚠️ anonymous_seq 는 마이그레이션 005 가 nullable 로 바꿨고, 지금은 안 쓴다. 닉네임 게시판이라 익명 번호를 채울 
- [[post_like|post_like]] — 생성기가 만든다.
- [[question|question]] — scope: CLASS / SCHOOL / GLOBAL. 세 스코프 모두 "친구" 안에서의 범위이며, GLOBAL 도 전체 가입자가 아니라 
- [[question_category|question_category]] — 구 스키마에는 카테고리가 없어 "외모/신체 질문이 신고 상위 5개를 독점"한다는 사실을 사후 수동 분류로만 확인할 수 있었다. is_sens
- [[question_request|question_request]] — 생성기가 만든다.
- [[region|region]] — 구 스키마는 accounts_school.address 가 varchar 한 덩어리라 시/군 단위 집계가 불가능했다. 시도·시군구를 정규화한
- [[rejected_friend_recommendations|rejected_friend_recommendations]] — ★ 이름이 말하는 그대로다 — 거절만 들어온다. 추천 자체는 저장하지 않는다. friend_suggestion 뷰가 그때그때 계산한다. 이 
- [[report|report]] — 유저·질문·게시글·댓글 신고를 한 테이블로 통합하되, 대상별 FK를 명시 컬럼으로 두어 참조 무결성을 지킨다. (다형 참조 방식은 FK를 걸
- [[report_reason|report_reason]] — 생성기가 만든다.
- [[sanction|sanction]] — triggered_by_report_id 로 근거 신고를 명시한다. 이 연결이 구 시스템에는 아예 없었다.
- [[sanction_policy|sanction_policy]] — 임계값을 코드가 아니라 데이터로 정의한다. 구 시스템은 피신고 10회 이상 116명 중 제재된 사람이 0명이었고, 253회 신고받은 유저도 
- [[school|school]] — 구 스키마에는 학교 이름 컬럼이 아예 없었다. 마스킹된 이름을 저장한다. neis_school_code 는 NEIS 공개 API 연동 키. 
- [[school_event|school_event]] — 시작·종료일을 분리해 기간 일정을 지원한다. grade_scope 가 NULL 이면 전교 대상, 값이 있으면 해당 학년만 해당한다.
- [[school_notice|school_notice]] — 생성기가 만든다.
- [[school_notice_read|school_notice_read]] — 어떤 공지가 실제로 읽히는지 측정해 알림 정책을 조정한다.
- [[timetable|timetable]] — 학급·학기·요일·교시에 UNIQUE → 한 칸에 두 과목이 들어갈 수 없다. 교사명은 마스킹해서 저장한다.
- [[user_session|user_session]] — 리텐션을 추정이 아니라 실측하기 위한 테이블.
- [[user_withdrawal|user_withdrawal]] — 구 스키마 최대 결함의 해소 지점. accounts_userwithdraw 는 70,764건(가입자의 10.5%)이었지만 유저 식별자가 없어
- [[vote_candidate|vote_candidate]] — 구 스키마는 세트↔피스 관계를 JSON 배열로만 들고 있었다. 행으로 저장한다. shuffle_round: 0 = 최초 후보, 1 = 셔플 
- [[vote_item|vote_item]] — 스킵 컬럼이 없다. 스킵 기능을 폐지했기 때문이다. candidate_scope 는 출제 시점의 스코프 스냅샷이다. 질문의 scope 가 나
- [[vote_received|vote_received]] — ⚠️ 아래 정의에 없는 컬럼이 마이그레이션으로 셋 붙었다: reply_text · replied_at   008. 나를 뽑은 사람에게 보내는
- [[vote_session|vote_session]] — 생성기가 만든다.
- [[vote_shuffle|vote_shuffle]] — vote_item_id 에 UNIQUE → DB 차원에서 1회 제한을 강제한다. ad_impression_id 가 NOT NULL → 광고 
- [[withdrawal_reason|withdrawal_reason]] — 생성기가 만든다.

---

문서 151개 · `python db/wiki_index.py` 로 갱신
