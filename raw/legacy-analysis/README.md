# 서비스 분석 리포트 인덱스

조사 대상: 익명 투표 SNS 앱 원본 덤프(`../raw/`) → `mysql` 컨테이너의 `final`/`hackle` 스키마로 복원 후 분석.
전체 서비스 기간: 2023-03 ~ 2024-05 (단, 대부분의 활동은 2023-05 런칭 스파이크에 쏠려 있음 — 아래 1번 문서 참고).

## 읽는 순서 추천

**바쁘면 [key_findings.md](00_key_findings.md)부터** — 아래 8개 문서를 관통하는 핵심 발견 10개만 추린 요약본.

| # | 문서 | 한 줄 요약 |
|---|---|---|
| 1 | [table_notes.md](01_table_notes.md) | 전체 테이블(final 21개 + hackle 4개) 구조/규모 개요. 가장 먼저 읽을 문서 — 여기 나온 "핵심 발견"들을 이후 모든 문서가 전제로 깔고 있음 |
| 2 | [retention_platform.md](02_retention_platform.md) | 가입 후 63.9%가 1주일 내 이탈, 코호트별 잔존율, iOS/Android 비교 |
| 3 | [social_graph.md](03_social_graph.md) | 친구요청 79.4%는 같은 학교 내에서 발생, 차단 패턴 |
| 4 | [voting_funnel.md](04_voting_funnel.md) | 투표 자체는 96%가 완료하지만, 결과를 열람하고도 83.5%가 답변을 공개 안 함 |
| 5 | [deep_dive_notes.md](05_deep_dive_notes.md) | 인기 질문 Top10, "학교 40명 이상" 조건 검증(실제론 상위 10개교만 활성화), 탈퇴 사유 |
| 6 | [payment_report.md](06_payment_report.md) | 하트 결제 구조, 결제유저의 투표 성향, 결제 매출은 투표 활성화 학교와 무관 |
| 7 | [report_ban_system.md](07_report_ban_system.md) | 신고가 쌓여도 실제 제재로 거의 안 이어짐(253회 피신고자도 정상 상태) |
| 8 | [attendance_feature.md](08_attendance_feature.md) | 출석 기능 참여 강도/요일별 패턴, 다른 기능과 달리 6월에 정점 |

## 핵심 발견 3가지만 골라본다면
1. **전체 서비스가 딱 10개 학교에서만 실제로 돌아간다** — 투표 기능이 활성화된 학교가 전체 5,951개 중 10곳뿐이고([deep_dive_notes.md](05_deep_dive_notes.md)), 이게 파워유저 쏠림([table_notes.md](01_table_notes.md) 핵심 발견 1)의 구조적 원인.
2. **가입은 많이 했지만 대부분 일주일 안에 떠난다** — 2023-05 한 달에 전체의 93.9%가 가입했는데, 이 코호트의 30일+ 잔존율은 3.9%에 불과([retention_platform.md](02_retention_platform.md)). 반면 그 이전 소수의 초기 유저는 잔존율이 훨씬 높음.
3. **매출과 핵심 기능(투표)이 완전히 분리되어 있다** — 결제 매출의 99.36%가 투표 불가능한 학교에서 발생([payment_report.md](06_payment_report.md)) — 하트가 투표 외 다른 용도로 쓰이고 있을 가능성.

## 폴더 구조
```
data/
├── raw/                  # 원본 SQL 덤프 (dump-hackle.sql, dump-votes-*.sql)
└── reports/              # 이 분석 문서들 (지금 보고 있는 폴더)
```
