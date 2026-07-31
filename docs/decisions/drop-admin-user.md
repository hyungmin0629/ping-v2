---
title: admin_user 를 없애고 app_user.is_admin 하나로 접는다
date: 2026-07-31
group: 스키마
status: active
tags: [결정, 스키마]
---

# admin_user 를 없애고 app_user.is_admin 하나로 접는다

**결정** — 운영자 테이블 `admin_user` 와 enum `admin_role` 을 지우고,
`app_user.is_admin boolean` 하나로 대신한다. 42 → **41 테이블.**

**이유** — 운영 화면을 만들 계획이 없다. 테이블 하나, enum 하나, FK 여섯 개를
유지할 근거가 "언젠가 운영 화면을 만들면"뿐이었다. 그 언젠가가 이 프로젝트의
범위에 없다.

**잃는 것 — 정확히 알고 지운다**

| 잃는 것 | 대신 |
|---|---|
| `admin_role` (REVIEWER/MODERATOR/SCHOOL_ADMIN/SUPER) | 없음. 권한을 코드로 가를 일이 없다 |
| `school_id` (학교별 운영자) | 없음. 학교가 5,724개인데 운영자는 없다 |
| `is_active` (퇴사 표시) | `app_user.status` 가 같은 일을 한다 |

**잃지 않는 것** — "누가 처리했나"는 그대로다. FK 여섯 개
(`question.created_by_admin_id`, `question_request.reviewed_by_admin_id`,
`heart_transaction.admin_id`, `report.reviewed_by_admin_id`,
`sanction.issued_by_admin_id`, `school_notice.created_by_admin_id`)가
`app_user` 를 가리키게만 바뀐다.

**컬럼 이름은 그대로 둔다.** `reviewed_by_admin_id` 를 `reviewed_by_user_id` 로
바꾸지 않았다. 이름이 말하는 것은 **가리키는 표**가 아니라 **그 사람이 어떤
자격으로 한 행위인지**다. 바꾸면 BigQuery 에서 컬럼이 사라지고 다시 생겨
다섯 테이블을 full-refresh 해야 하는데, 얻는 것이 없다.

**대안**
- 그냥 둔다. 기각. 빈 테이블이 ERD 에 남아 "운영 기능이 있나?"를 묻게 만든다.
  팀원과 스키마를 논의할 때 설명해야 하는 항목이 하나 더 생긴다.
- `admin_role` 만 남기고 테이블을 접는다. 기각. 역할을 읽는 코드가 없으면
  값은 주석과 다를 게 없다. 필요해지는 때가 곧 권한 체계를 다시 설계할 때다.

**새로 생긴 위험 — 시험을 함께 넣었다**

운영자 여부가 이제 **유저가 UPDATE 하는 표**에 산다. `app_user` 직접 UPDATE 는
W11 에서 이미 회수했지만, 그 사실에 기대는 것과 그것을 시험하는 것은 다르다.
`A 가 스스로 운영자가 되기`를 침투 시험에 넣었다(188 → 189항목).

⚠️ **is_admin 을 켜는 경로는 앱에 없다.** DB 에서 직접 켠다. 프로필 수정 RPC
(`update_profile`)에 이 컬럼을 끼워 넣지 말 것 — 그 순간 유저가 자기 값을
바꿀 수 있는 컬럼이 된다.

**영향 — 합성 데이터를 다시 만들어야 한다**

생성기가 운영자 5명을 따로 만들고 그 id 로 검수 이력을 채우고 있었다.
이제 **먼저 가입한 유저 다섯 명에 표시**한다 — 운영자도 계정이 있어야 한다는
뜻이 되었기 때문이다. 로컬 Postgres 와 BigQuery 의 합성 분면은 재생성 전까지
옛 구조다. 실유저 분면은 `app_user` 를 full-refresh 해 맞춰 두었다
(컬럼을 추가해도 워터마크는 안 움직인다 — 이 프로젝트의 단골 함정이다).

BigQuery `raw.admin_user` 는 **지우지 않는다.** raw 는 이력을 잃지 않는 층이다.
`pipeline/tables.yaml` 에서만 뺐으므로 더 이상 갱신되지 않고 그대로 남는다.

---

`2026-07-31` · [[DECISIONS|결정 이력]] 으로 돌아가기
