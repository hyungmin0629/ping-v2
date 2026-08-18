-- =====================================================================
-- mart_user · 유저 한 명 = 한 행 (차원 + 누적 지표)
-- ⚠️ **초안이다. 아직 BigQuery 에 만들지 않았다.**
--    마트 그레인은 `notebooks/dashboard.ipynb` 의 지표 12개를 보고 정한다.
--    확정되기 전까지 이 파일은 출발점일 뿐이다 — 결정된 설계가 아니다.
--    경위와 남은 결정은 docs/ops/ops-p5-p7.md.
-- =====================================================================
-- "이 유저는 언제 들어와서, 언제 열렸고, 얼마나 투표했고, 언제 나갔나"를
-- 한 줄로 답한다. 코호트·퍼널·리텐션이 전부 이 표에서 시작한다.
--
-- 규칙 두 가지를 여기서 못 박는다.
--   · 운영자 계정(is_admin)은 **아예 넣지 않는다.** 지표가 아니다.
--   · 누적 지표는 `valid_until` **이전 활동만** 센다 — 탈퇴·영구정지 이후의
--     활동은 존재해도 세지 않는다(합성 v5 에 실제로 34명 있다).
--
-- ⚠️ 탈퇴자를 **행에서 지우지는 않는다.** 지우면 이탈률의 분자가 사라진다.
--    거를 때는 `WHERE NOT is_withdrawn` 을 쓰는 쪽이 고른다.
-- =====================================================================
CREATE OR REPLACE TABLE `{{mart}}.mart_user`
CLUSTER BY source AS

WITH u AS (
  SELECT * FROM `{{stg}}.stg_user` WHERE NOT is_admin
),

votes AS (
  SELECT
    v.user_key,
    MIN(v.voted_at)                    AS first_vote_at,
    MAX(v.voted_at)                    AS last_vote_at,
    COUNT(*)                           AS vote_count,
    COUNT(DISTINCT v.vote_session_key) AS vote_session_count,
    COUNTIF(v.is_padded)               AS padded_item_count
  FROM `{{stg}}.stg_vote_item` AS v
  JOIN u ON u.user_key = v.user_key
  WHERE v.is_voted AND v.voted_at < u.valid_until
  GROUP BY v.user_key
),

sessions AS (
  SELECT
    s.user_key,
    COUNT(*)                  AS session_count,
    MIN(s.started_at)         AS first_session_at,
    MAX(s.started_at)         AS last_session_at,
    SUM(s.duration_sec)       AS total_session_sec
  FROM `{{stg}}.stg_user_session` AS s
  JOIN u ON u.user_key = s.user_key
  WHERE NOT s.is_duplicate AND s.started_at < u.valid_until
  GROUP BY s.user_key
),

hearts AS (
  SELECT
    t.user_key,
    SUM(t.hearts_earned) AS hearts_earned,
    SUM(t.hearts_spent)  AS hearts_spent
  FROM `{{stg}}.stg_heart_transaction` AS t
  JOIN u ON u.user_key = t.user_key
  WHERE t.created_at < u.valid_until
  GROUP BY t.user_key
),

hints AS (
  SELECT
    h.user_key,
    COUNTIF(h.is_paid_hint)                       AS paid_hint_count,
    COUNTIF(h.is_ad_hint)                         AS ad_hint_count,
    SUM(IF(h.is_paid_hint, h.heart_cost, 0))      AS hint_hearts_spent
  FROM `{{stg}}.stg_hint_purchase` AS h
  JOIN u ON u.user_key = h.user_key
  WHERE h.created_at < u.valid_until
  GROUP BY h.user_key
),

topups AS (
  SELECT
    p.user_key,
    COUNTIF(p.is_revenue)                       AS paid_topup_count,
    SUM(IF(p.is_revenue, p.price_krw, 0))       AS revenue_krw,
    COUNTIF(p.is_stub AND p.is_success)         AS stub_topup_count
  FROM `{{stg}}.stg_heart_purchase` AS p
  JOIN u ON u.user_key = p.user_key
  WHERE p.created_at < u.valid_until
  GROUP BY p.user_key
)

SELECT
  u.user_key,
  u.source,
  u.gender,
  u.school_key,
  u.school_name,
  u.school_type,
  u.grade,
  u.class_num,
  u.is_synthetic,

  -- 생애 주기
  u.signed_up_at,
  u.signup_date,
  u.service_unlocked_at,
  u.unlocked_date,
  v.first_vote_at,
  DATE(v.first_vote_at, 'Asia/Seoul')                                   AS first_vote_date,
  v.last_vote_at,
  s.last_session_at,
  u.withdrawn_at,
  u.withdrawal_reason_code,
  u.is_withdrawn,
  u.first_sanctioned_at,
  u.first_banned_at,
  u.valid_until,

  -- 퍼널 단계 (가입 → 해금 → 첫 투표). 대시보드에서 COUNTIF 로 바로 센다.
  u.service_unlocked_at IS NOT NULL                                     AS is_unlocked,
  v.first_vote_at IS NOT NULL                                           AS is_activated,
  TIMESTAMP_DIFF(u.service_unlocked_at, u.signed_up_at, DAY)            AS days_to_unlock,
  TIMESTAMP_DIFF(v.first_vote_at, u.signed_up_at, DAY)                  AS days_to_first_vote,
  TIMESTAMP_DIFF(v.last_vote_at, v.first_vote_at, DAY)                  AS active_span_days,

  -- 누적 활동
  IFNULL(v.vote_count, 0)                                               AS vote_count,
  IFNULL(v.vote_session_count, 0)                                       AS vote_session_count,
  IFNULL(v.padded_item_count, 0)                                        AS padded_item_count,
  IFNULL(s.session_count, 0)                                            AS session_count,
  IFNULL(s.total_session_sec, 0)                                        AS total_session_sec,
  u.friend_count,

  -- 하트
  IFNULL(h.hearts_earned, 0)                                            AS hearts_earned,
  IFNULL(h.hearts_spent, 0)                                             AS hearts_spent,
  u.heart_balance,
  IFNULL(hi.paid_hint_count, 0)                                         AS paid_hint_count,
  IFNULL(hi.ad_hint_count, 0)                                           AS ad_hint_count,
  IFNULL(hi.hint_hearts_spent, 0)                                       AS hint_hearts_spent,

  -- 매출 (스텁 결제는 빠져 있다)
  IFNULL(t.paid_topup_count, 0)                                         AS paid_topup_count,
  IFNULL(t.revenue_krw, 0)                                              AS revenue_krw,
  IFNULL(t.stub_topup_count, 0)                                         AS stub_topup_count,
  IFNULL(t.paid_topup_count, 0) > 0                                     AS is_payer

FROM u
LEFT JOIN votes    AS v  ON v.user_key  = u.user_key
LEFT JOIN sessions AS s  ON s.user_key  = u.user_key
LEFT JOIN hearts   AS h  ON h.user_key  = u.user_key
LEFT JOIN hints    AS hi ON hi.user_key = u.user_key
LEFT JOIN topups   AS t  ON t.user_key  = u.user_key
