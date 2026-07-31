---
title: 초대 링크는 배포(W7) 이후로 미룬다
date: 2026-07-29
group: 웹앱
status: superseded
superseded_by: invite-link-querystring
tags: [결정, 웹앱]
---

# 초대 링크는 배포(W7) 이후로 미룬다

> ⛔ **대체된 결정이다.** → [[invite-link-querystring]]

**결정** — `/add/[코드]` 라우트와 "링크 복사" 버튼을 W4 에서 걷어냈다.
친구 추가는 코드 입력 하나로 한다.

**이유** — 주소가 `localhost:3000` 인 동안 링크는 친구 기기에서 열리지 않는다.
실사용 가치가 0인데, 개발 서버에서 이 라우트가 렌더링 워커째 죽는 문제
(`Jest worker encountered 2 child process exceptions`)가 있어 디버깅 비용만 남았다.
`next build` 는 통과하는데 dev 런타임에서만 터져 원인 추적에 시간이 든다.

**영향**
- W7 에서 실제 도메인이 생길 때 다시 만든다. 그때가 링크가 주 경로가 되는 시점이다
  (카톡으로 던지면 눌러서 바로 들어온다).
- 코드 입력칸은 주소나 군더더기가 섞여 들어와도 코드만 뽑아내도록 남겨두었다
  (`normalizeCode`). 링크가 없어도 "코드: XXXX" 같은 붙여넣기가 흔하다.
- ⚠️ 다시 만들 때 위 dev 에러부터 재현·해결하고 시작할 것.

---

`2026-07-29` · [[DECISIONS|결정 이력]] 으로 돌아가기
