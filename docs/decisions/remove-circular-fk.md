---
title: 순환 FK를 제거하는 방향으로 스키마 정리
date: 2026-07-29
group: 스키마
status: active
tags: [결정, 스키마]
---

# 순환 FK를 제거하는 방향으로 스키마 정리

**결정** — DDL 작성 과정에서 양방향으로 참조하던 3쌍을 단방향으로 정리했다.

- `question.origin_request_id` 제거 → `question_request.published_question_id`만 유지
- `vote_item.chosen_candidate_id` 제거 → `vote_candidate.is_chosen` 플래그 + 부분 유니크 인덱스
- `hint_purchase.heart_transaction_id` 제거 → `heart_transaction.hint_purchase_id`만 유지

**이유** — 순환 FK는 테이블 생성 순서를 꼬이게 하고, 두 방향이 어긋났을 때 어느 쪽이 진실인지
알 수 없다. 원장(`heart_transaction`)이 원인을 가리키는 단방향이 자연스럽다.

**영향** — "선택된 후보"는 `vote_candidate.is_chosen = true`로 조회한다.
아이템당 1명만 선택되는 것은 부분 유니크 인덱스가 강제한다.

## 이어지는 결정
- [[drop-admin-user|admin_user 를 없애고 app_user.is_admin 하나로 접는다]]
  — 쓰지 않는 구조를 걷어내 스키마를 줄인 판단 둘
- [[local-db-via-apply|로컬 DB 는 `apply.py` 로만 만든다]]
  — 스키마를 한 경로로만 만든다
- [[report-sanction-fk|신고와 제재를 FK로 연결하고 정책을 데이터로 정의]]
  — 관계를 DB 에 선언한다. 구 서비스는 FK 39개 중 17개만 걸려 있었다

---

`2026-07-29` · [[DECISIONS|결정 이력]] 으로 돌아가기
