---
title: 클라이언트에 쓰기 권한을 거의 주지 않는다
date: 2026-07-29
group: 보안
status: active
tags: [결정, 보안]
---

# 클라이언트에 쓰기 권한을 거의 주지 않는다

**결정** — RLS 는 읽기 위주로 열고, 하트·투표처럼 규칙이 있는 조작은
클라이언트가 직접 INSERT/UPDATE 하지 못하게 막는다. 나중에 RPC 함수로 처리한다.

**이유** — Supabase 는 브라우저가 DB에 직접 말을 건다. `heart_transaction` INSERT 를
열어주면 누구나 하트를 무한정 만들 수 있고, `app_user.heart_balance` UPDATE 를
열어주면 잔액을 마음대로 바꿀 수 있다. 실제로 침투 시험에서 두 시도 모두
`InsufficientPrivilege` 로 막히는 것을 확인했다.

**구현** — `REVOKE UPDATE ON app_user FROM authenticated` 후
`GRANT UPDATE (nickname, class_id, gender)` 로 **컬럼 단위**로만 허용했다.
RLS 는 행 단위라 컬럼을 제한할 수 없어 GRANT 와 함께 써야 한다.

---

`2026-07-29` · [[DECISIONS|결정 이력]] 으로 돌아가기
