---
title: 로컬 DB 는 `apply.py` 로만 만든다
date: 2026-07-30
group: 스키마
status: active
tags: [결정, 스키마]
---

# 로컬 DB 는 `apply.py` 로만 만든다

**결정** — README 의 "스키마 만들기"를 `cat db/ddl/*.sql | psql` 에서
`python db/apply.py --target local` 로 바꿨다.

**이유** — 그 `cat` 경로에는 `db/migrations/` 가 없다. 실제로 로컬 합성 DB 가
마이그레이션 3종(001·002·003) 뒤처진 채 몇 주를 돌았고, 그 결과:

- 정합성 검사 17종이 `padded_count` 를 못 찾아 **통째로 실행되지 않았다.**
  합성 데이터를 검증할 수단이 끊겨 있었는데 아무도 몰랐다.
- 그 상태로 BigQuery 에 올라가 `vote_item.padded_count` 가 합성 803,187행
  전부 NULL 이 됐다.

문서가 두 개의 서로 다른 재구축 경로를 말하고 있었던 것이 원인이다
(CLAUDE.md 는 `apply.py`, README 는 `cat`). 진실을 하나로 줄였다.

**영향**
- 마이그레이션을 적용한 뒤에는 그 테이블을 `--full-refresh` 해야 한다.
  `ALTER TABLE ADD COLUMN` 은 트리거를 발동시키지 않아 `updated_at` 이 그대로고,
  증분은 아무것도 잡지 못한다. 이 함정을 CLAUDE.md 에 적었다.
- `docker run` 에 `--shm-size=1g` 를 추가했다. 도커 기본 64MB 로는 786만 행
  정합성 검사가 `No space left on device` 로 죽는다. 디스크가 아니라 공유메모리다.

---

`2026-07-30` · [[DECISIONS|결정 이력]] 으로 돌아가기
