# 결정 이력

설계 결정과 **그 이유**를 남긴다. 무엇을 했는지가 아니라 **왜 그렇게 했는지**,
그리고 **무엇을 버렸는지**. 스키마 구조나 코드 설명은 여기 적지 않는다 —
DDL과 스크립트가 진실이다.

**이 문서는 색인이다.** 결정 하나하나는 `docs/decisions/` 의 파일이고,
각각이 옵시디언 노드다. 하나를 보려고 전체를 읽지 않는다.

결정 84개 · 유효 80 · 대체됨 4

## 새 결정을 적을 때

`docs/decisions/<슬러그>.md` 를 만들고 이 목록에 한 줄 넣는다.
형식은 기존 파일과 같다 — frontmatter + 결정 / 이유 / 대안 / 영향.
**뒤집는 결정이라면** 옛 파일에 `status: superseded` 와 `superseded_by` 를 단다.

## 범위

- `2026-07-29` [[no-anonymous-board|익명 게시판을 v1에서 제외]]
- `2026-07-29` [[closed-test-adults|성인 지인 대상 클로즈드 테스트로 한정]]
- `2026-07-29` [[webapp-first-track|웹앱을 최우선 트랙으로 재편]]
- `2026-07-29` [[ads-payments-stub|MVP에서 광고와 결제를 스텁으로 처리]]
- `2026-07-29` [[student-mvp-adult-testers|학생용 MVP를 만들고, 검증은 성인이 한다]]
- `2026-08-03` [[no-schema-change-for-synthetic|합성 데이터를 위해 스키마를 바꾸지 않는다]]

## 보안

- `2026-07-29` [[client-write-minimal|클라이언트에 쓰기 권한을 거의 주지 않는다]]
- `2026-07-29` [[voter-identity-view-only|투표자 신원은 뷰로만 노출한다]]
- `2026-07-29` [[anonymous-auth-no-pii|개인정보를 일절 받지 않는 익명 인증]]
- `2026-07-29` [[signup-single-rpc|가입은 RPC 하나로만 한다]]
- `2026-07-30` [[school-boundary-self-reported|학교 경계는 기술로 막지만, 소속은 자기신고다]]
- `2026-07-30` [[profile-edit-rpc|프로필 수정도 RPC 하나로 — 직접 UPDATE 권한 회수]]
- `2026-07-31` [[school-info-write-revoked|학사일정·공지의 쓰기 권한이 열려 있었다]]

## 스키마

- `2026-07-29` [[withdrawal-user-id|탈퇴 기록에 유저 식별자를 넣는다]]
- `2026-07-29` [[remove-circular-fk|순환 FK를 제거하는 방향으로 스키마 정리]]
- `2026-07-29` [[gender-at-onboarding|성별을 온보딩에서 받는다]]
- `2026-07-30` [[local-db-via-apply|로컬 DB 는 `apply.py` 로만 만든다]]
- `2026-07-30` [[withdraw-keeps-rows|계정 삭제는 행을 지우지 않는다]]
- `2026-07-31` [[drop-admin-user|admin_user 를 없애고 app_user.is_admin 하나로 접는다]]

## 하트

- `2026-07-29` [[heart-unify-point|하트와 포인트를 하나로 통합]]
- `2026-07-29` [[heart-balance-after|모든 하트 증감에 `balance_after`를 기록]]
- `2026-07-30` [[topup-stub-daily-limit|하트 충전은 결제 없는 스텁 — 대신 하루 한 번]]
- `2026-07-30` [[selectable-hints|힌트를 골라 사게 바꾼다 — 순차 4단계 폐기]]
- `2026-08-03` [[heart-economy-rebalance|하트 경제를 다시 잡는다 — v1 실측을 버린다]]
- `2026-08-03` [[app-follows-generator|앱을 생성기에 맞춘다 — 다만 생성 시험이 끝난 뒤 한 번에]]

## 투표

- `2026-07-29` [[shuffle-once-constraint|셔플은 DB 제약으로 1회를 강제한다]]
- `2026-07-29` [[candidate-rows-kept|후보 4명을 행으로 저장하고 셔플 전후를 모두 남긴다]]
- `2026-07-29` [[global-scope-is-friends|`GLOBAL` 스코프는 "내 친구 전체"]]
- `2026-07-30` [[pad-candidates-keep-scope|후보가 모자라면 스코프를 낮추지 않고 다른 친구로 채운다]]
- `2026-07-29` ~~[[lower-scope-when-short|후보가 4명이 안 되면 스코프를 낮추고, 그래도 안 되면 질문을 내지 않는다]]~~ ⛔ → [[pad-candidates-keep-scope]]
- `2026-07-30` [[one-time-reply|1회성 답장을 연다 — 차단 화면 없이]]
- `2026-08-03` [[appearance-questions-for-report-rate|외모·신체 질문을 연다 — 민감 질문이 없으면 신고율을 못 잰다]]

## 친구

- `2026-07-29` [[friend-invite-code-two-step|친구 맺기는 초대 코드로만, 요청·수락 2단계로]]
- `2026-07-30` [[friend-recommend-same-school|친구 추천 — "초대 코드로만"을 같은 학교 범위에서 연다]]
- `2026-07-31` [[friendship-ended-at|친구를 끊어도 행을 지우지 않는다]]

## 게시판

- `2026-07-30` [[open-named-board|자유게시판을 연다 — 글도 댓글도 닉네임으로]]
- `2026-07-30` [[board-school-scope|게시판 범위는 학교, 카테고리는 하나]]
- `2026-07-30` [[report-first-block-later|신고는 게시판과 함께, 차단은 뒤로]]

## 웹앱

- `2026-07-30` [[invite-link-after-deploy|초대 링크는 배포(W7) 이후로 미룬다]]
- `2026-07-30` [[invite-link-querystring|초대 링크는 동적 라우트 대신 쿼리스트링으로 만든다]]
- `2026-07-31` [[history-based-navigation|화면 이동을 브라우저 이력에 싣는다]]

## 학교 정보

- `2026-07-29` [[testers-pick-real-school|NEIS 연동 후 테스터는 실제 학교 중 하나를 고른다]]
- `2026-07-30` [[org-borrows-school-info|테스트 조직은 이름을 유지하고 실제 학교의 정보를 빌려 쓴다]]
- `2026-07-31` [[events-on-meal-calendar|학사일정을 급식 달력에 얹는다 — 따로 만들지 않고]]
- `2026-07-31` [[neis-merge-spans|NEIS 가 하루씩 주는 것을 기간으로 묶는다]]

## 신고와 제재

- `2026-07-29` [[report-sanction-fk|신고와 제재를 FK로 연결하고 정책을 데이터로 정의]]
- `2026-08-04` [[sensitive-question-report-weight|민감 질문에 신고 성향을 심는다]]

## 파이프라인

- `2026-07-29` [[synthetic-real-separation|합성 데이터와 실유저 데이터를 분리]]
- `2026-07-30` [[watermark-updated-at|증분 워터마크를 `updated_at` 하나로 통일한다]]
- `2026-07-30` [[bigquery-source-column|실유저와 합성 데이터를 같은 BigQuery 테이블에 `_source` 로 섞는다]]
- `2026-07-30` [[backfill-updated-at|대량 적재 후 `updated_at` 을 각 행의 원래 시각으로 되돌린다]]
- `2026-07-30` [[bigquery-direct-no-gcs|BigQuery 에 GCS 를 경유하지 않고 직접 올린다]]
- `2026-07-30` [[no-delete-propagation|원천의 삭제는 BigQuery 로 전파하지 않는다]]
- `2026-07-30` [[watermark-lag-5min|워터마크를 스냅샷보다 5분 뒤로 물려 저장한다]]
- `2026-07-30` [[join-requires-source|두 원천의 id 가 겹친다 — 조인에 `_source` 를 강제한다]]
- `2026-07-30` [[soft-delete-marking|삭제를 전파하지는 않되, 표시는 한다 (앞 항목 보완)]]
- `2026-07-31` [[purge-synthetic-data|합성 데이터를 전부 지운다 — 낡아서]]
- `2026-08-03` ~~[[row-guardrail-measured|행수 가드레일을 실측으로 다시 잡는다]]~~ → [[row-cap-to-query-cap]]
- `2026-08-04` [[row-cap-to-query-cap|행수 상한을 버리고 쿼리 하드캡으로 바꾼다]]
- `2026-08-04` [[generator-emits-updated-at|`updated_at` 을 생성기가 직접 싣는다]]
- `2026-08-06` [[bulk-load-batch-rows|합성 대량 적재는 배치를 20만 행으로 키운다]]
- `2026-08-06` [[partition-ordered-extract|파티션 테이블로 부을 때는 파티션 컬럼 순서로 꺼낸다]]

## 인프라

- `2026-07-29` [[supabase-session-pooler|Supabase 연결은 Session pooler 를 쓴다]]
- `2026-07-29` [[local-docker-airflow|Cloud Composer 대신 로컬 Docker Airflow]]
- `2026-07-30` [[airflow-two-services|Airflow 는 공식 컴포즈 대신 2개 서비스로 줄인다]]

## 검증

- `2026-07-31` [[integrity-checks-aged|정합성 검사 3종이 낡아 있었다]]
- `2026-08-13` [[ddl-comments-rot-with-migrations|DDL 주석은 마이그레이션 뒤에 낡는다 — 파일이 아니라 순서가 진실이다]]
- `2026-08-03` [[user-personas|페르소나는 분류가 아니라 생성 편의다]]
- `2026-08-03` [[activity-by-retention-tier|활동 강도는 잔존 구간마다 다르다]]
- `2026-08-04` [[growth-curve-two-channels|성장 곡선은 가입과 활동 두 갈래로 건다]]
- `2026-08-04` [[spring-spike-growth-curve|성장 곡선을 봄학기형으로 바꾼다]]
- `2026-08-04` [[school-sequential-adoption|학교를 순차로 열고, 학급 수를 정원에서 유도한다]]
- `2026-08-04` [[reactivation-cohort|휴면했다 돌아오는 유저를 만든다]]
- `2026-08-04` [[retention-quarter-tier|잔존 구간에 30~89일을 새로 넣는다]]
- `2026-08-04` [[popularity-floor-is-activity|인기도 45%는 도달할 수 없다]]
- `2026-08-04` [[expired-session-status|중도 이탈 세션은 EXPIRED 로 적는다]]
- `2026-08-04` [[daily-rhythm-night-peak|하루 리듬을 붙인다 — 최대 봉우리는 밤 22시]]
- `2026-08-04` [[never-voters-by-friend-count|해금하고도 투표 안 하는 유저를 의도적으로 만든다]]
- `2026-08-04` [[class-size-for-class-scope|같은 반 친구는 비율이 아니라 수가 기준이다]]
- `2026-08-05` ~~[[confirm-v4-with-known-limits|합성 데이터 v4 를 확정한다 — 한계 5건을 고치지 않고 문서화한다]]~~ → [[session-bounded-actions]]
- `2026-08-05` [[lognormal-not-uniform|시간 간격을 균등분포에서 로그정규로 바꾼다 — v5]]
- `2026-08-05` [[dow-from-legacy-attendance|요일 패턴은 구 서비스 출석 로그를 따라간다 — 우하향이 아니라 V자]]
- `2026-08-05` [[session-bounded-actions|유저의 직접 행동은 접속 세션 안에서만 일어난다 — v5]]
- `2026-08-05` [[withdrawal-is-terminal|탈퇴는 종점이다 — 그 뒤로 어떤 로그도 남기지 않는다]]

