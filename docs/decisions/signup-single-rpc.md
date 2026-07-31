---
title: 가입은 RPC 하나로만 한다
date: 2026-07-29
group: 보안
status: active
tags: [결정, 보안]
---

# 가입은 RPC 하나로만 한다

**결정** — 온보딩에서 `app_user` 를 클라이언트가 직접 INSERT 하지 않는다.
`complete_onboarding(닉네임, 반, 성별)` 함수로만 계정을 만들고,
`authenticated` 의 INSERT 권한 자체를 회수했다.

**이유** — INSERT 를 열면 같은 문장에 `heart_balance = 999999` 나
`is_synthetic = true` 를 끼워 넣을 수 있다. 하트는 "RPC 로만 바뀐다"고 정한 값이고,
`is_synthetic` 이 오염되면 BigQuery 에서 실유저와 합성 데이터를 영영 구분하지 못한다.
RLS 는 행 단위라 이걸 막지 못한다.

**대안** — 컬럼 단위 INSERT 권한(`GRANT INSERT (nickname, class_id, ...)`). 기각.
`invite_code` 가 NOT NULL UNIQUE 라 클라이언트가 코드를 만들어야 하고,
그러면 코드 생성 규칙과 중복 재시도가 브라우저로 나간다. 어차피 SQL 을 손대야 한다면
RPC 쪽이 화면 코드가 더 단순해진다.

**영향**
- 가입 하트 300 지급을 이 함수 안에서 함께 처리한다. 잔액을 만드는 트랜잭션이
  원장(`heart_transaction`)도 같이 만들어서, 구 시스템 최대 결함이었던
  원장·잔액 불일치가 생길 자리를 없앴다. 금액 근거는 구 서비스 실측 최빈값
  (`generator/config/distribution.yaml` · `signup_grant`).
- 두 번 호출되면 기존 행을 그대로 돌려준다. 새로고침·중복 클릭에 계정이 갈라지지 않는다.
- `policies.sql` 의 `insert_own_user` 정책은 제거했다.
- 정책·시드처럼 나중에 하나씩 추가되는 SQL 을 올리려고 `db/run_sql.py` 를 만들었다.

---

`2026-07-29` · [[DECISIONS|결정 이력]] 으로 돌아가기
