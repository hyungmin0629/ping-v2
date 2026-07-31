---
title: 웹앱 (web/)
group: 운영
tags: [운영, 참조]
---

# 웹앱 (web/)

> `CLAUDE.md` 에서 뺀 참조 문서다. 요약과 경고는 거기 남아 있고,
> 여기에는 **실제로 그 작업을 할 때 필요한 값과 절차**가 있다.


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

---

[[CLAUDE|CLAUDE.md]] 로 돌아가기
