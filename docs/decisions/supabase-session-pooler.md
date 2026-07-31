---
title: Supabase 연결은 Session pooler 를 쓴다
date: 2026-07-29
group: 인프라
status: active
tags: [결정, 인프라]
---

# Supabase 연결은 Session pooler 를 쓴다

**결정** — 직접 연결(`db.<ref>.supabase.co`) 대신 Session pooler
(`aws-1-ap-northeast-2.pooler.supabase.com:5432`)로 접속한다.

**이유** — 무료 플랜의 직접 연결 엔드포인트는 **IPv6 전용**이다. DNS 조회 결과가
AAAA 레코드뿐이라 IPv4 환경에서는 호스트 이름 해석 자체가 실패한다.
Supabase 는 IPv4 전용 애드온($4/월)을 팔지만 **Pro 플랜($25/월) 가입이 전제**라
"무료 티어를 벗어나지 않는다"는 제약과 충돌한다.
공유 pooler 는 IPv4 를 기본 지원하며 추가 비용이 없다.

**대안** — Transaction pooler(6543). 기각. 상태를 유지하지 않는 연결이라
대량 적재나 준비된 구문에서 문제가 생긴다.

**함께 겪은 것** — DB 비밀번호에 `@` 가 들어 있어 접속 URI 가 잘못 파싱됐다.
URI 안의 비밀번호는 퍼센트 인코딩이 필요하다(`@` → `%40`).
`db/apply.py` 등은 `.env` 값을 그대로 쓰므로 인코딩된 상태로 보관한다.

## 이어지는 결정
- [[anonymous-auth-no-pii|개인정보를 일절 받지 않는 익명 인증]]
  — Supabase 를 쓰기로 한 뒤 마주친 접속 제약

---

`2026-07-29` · [[DECISIONS|결정 이력]] 으로 돌아가기
