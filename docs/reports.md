---
title: 리포트 — PDF 로 뽑은 것들
group: 색인
tags: [색인, 리포트]
---

# 리포트 — PDF 로 뽑은 것들

이 저장소에는 마크다운이 아닌 문서가 있다. **EDA 리포트 · 감사 · 설명서**가
그렇다. 표와 막대가 많아 한 장으로 읽어야 뜻이 통하기 때문에 HTML 로 쓰고
PDF 로 뽑는다.

⚠️ **PDF 는 위키 노드가 아니다.** 옵시디언 그래프에서 첨부로만 보이고,
검색·백링크가 마크다운만큼 되지 않는다. 그래서 **이 페이지가 목록 역할을 한다** —
무엇이 있고 무엇을 담았는지 여기서 찾는다.

**생성 방식** — `docs/<이름>.html` 을 쓰고 헤드리스 크롬으로 PDF 를 뽑는다.
HTML 이 원본이고 PDF 는 산출물이다. 고칠 때는 **HTML 을 고치고 다시 뽑는다.**

---

## 합성 데이터

| 리포트 | 대상 | 무엇을 담았나 |
|---|---|---|
| [결정 이력](synthetic-data-decision-history.pdf) | 전체 | **30문답 · 5판본 · 뒤집힌 결정 8건 · 교훈 10가지.** 왜 이 값인지 되짚을 때 여기부터 |
| [12개월 v2 전면 감사](EDA-final-12m-v2.pdf) | 1억 8,826만 행 | **확정 전 검수.** 무결성 · 분포 · 그래프 · 행동 전 영역. 발견한 결함 3건 |
| [12개월 v3](EDA-final-12m-v3.pdf) <span class="dim">폐기</span> | 1억 8,918만 행 | 감사 3건 수정본. **확정 직전 `user_session` 결함이 나와 중단.** 측정값은 남겼다 |
| [12개월 v1](EDA-final-12m-v1.pdf) | 1억 4,126만 행 | 성장 곡선 첫 구현. 결함 8건을 드러낸 판본 |
| [1개월 샘플 v3](EDA-sample-1m-v3.pdf) | 500명·1개월 | 페르소나 도입 · 확률 보정 · **우측 절단** 발견 |
| [1개월 샘플 v2](EDA-sample-1m-v2.pdf) | 500명·1개월 | 5개 해결. 하트 문제의 **성격이 뒤집힌** 판본 |
| [1개월 샘플 v1](EDA-sample-1m-v1.pdf) | 500명·1개월 | 첫 검증. 깨진 것 4가지 |

판본이 왜 이렇게 여러 개인지, 각각에서 무엇을 고쳤는지는
[결정 이력](synthetic-data-decision-history.pdf) 3~5장에 정리돼 있다.
설계 근거는 [[synthetic-v2-decisions]] 의 30문답이 원본이다.

## 파이프라인 · 프로젝트

| 리포트 | 무엇을 담았나 |
|---|---|
| [파이프라인 전체 그림](pipeline-overview.pdf) | 저장소 셋(Supabase · 로컬 · BigQuery)이 어떻게 갈라지고 만나는가. **id 충돌 함정** |
| [프로젝트 여정](PROJECT-JOURNEY.pdf) | 전체 흐름 |
| [위키 리포트](WIKI-REPORT.pdf) | 문서 구조 |
| [설계서](design-spec.pdf) | [[design-spec]] 의 PDF 판 |
| [팀 계획](TEAM-PLAN.pdf) | [[TEAM-PLAN]] 의 PDF 판 |

## 그 밖

- `docs/erd-board.html` — 카드형 ERD. `db/erd_board.py` 가 뽑는다
- `docs/erd.json` — ERD 원자료. 행 수와 빈 표 사유가 함께 들어 있다

---

## 어느 것을 봐야 하나

| 묻는 것 | 볼 것 |
|---|---|
| "이 값이 왜 이렇게 정해졌지?" | [결정 이력](synthetic-data-decision-history.pdf) |
| "이 데이터 써도 되나?" | [12개월 v2 감사](EDA-final-12m-v2.pdf) 0장과 15장 |
| "실데이터랑 합성이 어떻게 다르지?" | [파이프라인 전체 그림](pipeline-overview.pdf) |
| "판본마다 뭐가 달랐지?" | [결정 이력](synthetic-data-decision-history.pdf) 0장 표 |

개별 결정의 근거는 PDF 가 아니라 [[DECISIONS|결정 색인]] 의 노드에 있다.
PDF 는 **여러 결정을 한 흐름으로 엮어 볼 때** 쓴다.
