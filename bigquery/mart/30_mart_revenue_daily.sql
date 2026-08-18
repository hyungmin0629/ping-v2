-- =====================================================================
-- mart_revenue_daily · 하루(KST) × 원천 = 한 행 (돈과 하트)
-- ⚠️ **초안이다. 아직 BigQuery 에 만들지 않았다.**
--    마트 그레인은 `notebooks/dashboard.ipynb` 의 지표 12개를 보고 정한다.
--    확정되기 전까지 이 파일은 출발점일 뿐이다 — 결정된 설계가 아니다.
--    경위와 남은 결정은 docs/ops/ops-p5-p7.md.
-- =====================================================================
-- **MVP 의 충전은 결제가 아니다.** 스텁으로 들어온 충전을 매출에 섞으면
-- 숫자가 통째로 거짓이 된다. 그래서 이 표는 세 갈래를 나란히 싣는다.
--
--   revenue_*   진짜 결제 (성공 · 스텁 아님)  ← 매출은 이것뿐이다
--   stub_*      스텁 충전 (W13)              ← 매출 아님. 참여 지표로만 본다
--   failed_*    실패한 결제                   ← 합성 데이터에만 있다
--
-- 하트 소비는 돈이 아니지만 **하트 경제의 건강도**라 함께 본다.
-- 적립(공급)과 소비(수요)가 벌어지면 하트가 남아돌고, 힌트가 안 팔린다.
-- =====================================================================
CREATE OR REPLACE TABLE `{{mart}}.mart_revenue_daily`
PARTITION BY activity_date
CLUSTER BY source AS

WITH u AS (
  SELECT * FROM `{{stg}}.stg_user` WHERE NOT is_admin
),

topups AS (
  SELECT
    p.source,
    p.purchase_date                                        AS d,
    COUNTIF(p.is_revenue)                                  AS revenue_count,
    SUM(IF(p.is_revenue, p.price_krw, 0))                  AS revenue_krw,
    SUM(IF(p.is_revenue, p.heart_amount, 0))               AS revenue_hearts,
    COUNT(DISTINCT IF(p.is_revenue, p.user_key, NULL))     AS paying_users,
    COUNTIF(p.is_stub AND p.is_success)                    AS stub_count,
    SUM(IF(p.is_stub AND p.is_success, p.heart_amount, 0)) AS stub_hearts,
    COUNT(DISTINCT IF(p.is_stub AND p.is_success, p.user_key, NULL)) AS stub_users,
    COUNTIF(NOT p.is_success)                              AS failed_count
  FROM `{{stg}}.stg_heart_purchase` AS p
  JOIN u ON u.user_key = p.user_key
  WHERE p.created_at < u.valid_until
  GROUP BY 1, 2
),

spend AS (
  -- 하트가 **나간** 것만 본다. type_code 별로 갈라 어디로 나갔는지 보인다.
  SELECT
    t.source,
    t.tx_date                                                   AS d,
    SUM(t.hearts_spent)                                         AS hearts_spent,
    SUM(IF(t.type_code = 'HINT_PURCHASE', t.hearts_spent, 0))   AS hearts_spent_hint,
    SUM(IF(t.type_code = 'VOTE_REPLY',    t.hearts_spent, 0))   AS hearts_spent_reply,
    SUM(t.hearts_earned)                                        AS hearts_earned,
    SUM(IF(t.type_code = 'VOTE_REWARD',   t.hearts_earned, 0))  AS hearts_earned_vote,
    SUM(IF(t.type_code = 'AD_REWARD',     t.hearts_earned, 0))  AS hearts_earned_ad,
    COUNT(DISTINCT IF(t.delta < 0, t.user_key, NULL))           AS spending_users
  FROM `{{stg}}.stg_heart_transaction` AS t
  JOIN u ON u.user_key = t.user_key
  WHERE t.created_at < u.valid_until
  GROUP BY 1, 2
),

hints AS (
  SELECT
    h.source,
    h.hint_date                               AS d,
    COUNTIF(h.is_paid_hint)                   AS paid_hint_count,
    COUNTIF(h.is_ad_hint)                     AS ad_hint_count,
    COUNT(DISTINCT IF(h.is_paid_hint, h.user_key, NULL)) AS paid_hint_users
  FROM `{{stg}}.stg_hint_purchase` AS h
  JOIN u ON u.user_key = h.user_key
  WHERE h.created_at < u.valid_until
  GROUP BY 1, 2
),

spine AS (
  SELECT source, d FROM topups
  UNION DISTINCT SELECT source, d FROM spend
  UNION DISTINCT SELECT source, d FROM hints
)

SELECT
  sp.d                              AS activity_date,
  sp.source,

  -- 매출 (스텁 제외)
  IFNULL(t.revenue_count, 0)        AS revenue_count,
  IFNULL(t.revenue_krw, 0)          AS revenue_krw,
  IFNULL(t.revenue_hearts, 0)       AS revenue_hearts,
  IFNULL(t.paying_users, 0)         AS paying_users,

  -- 스텁 충전 — 매출이 아니다. 참여 지표로만 본다
  IFNULL(t.stub_count, 0)           AS stub_count,
  IFNULL(t.stub_hearts, 0)          AS stub_hearts,
  IFNULL(t.stub_users, 0)           AS stub_users,
  IFNULL(t.failed_count, 0)         AS failed_count,

  -- 하트 경제
  IFNULL(s.hearts_earned, 0)        AS hearts_earned,
  IFNULL(s.hearts_earned_vote, 0)   AS hearts_earned_vote,
  IFNULL(s.hearts_earned_ad, 0)     AS hearts_earned_ad,
  IFNULL(s.hearts_spent, 0)         AS hearts_spent,
  IFNULL(s.hearts_spent_hint, 0)    AS hearts_spent_hint,
  IFNULL(s.hearts_spent_reply, 0)   AS hearts_spent_reply,
  IFNULL(s.spending_users, 0)       AS spending_users,
  SAFE_DIVIDE(s.hearts_spent, s.hearts_earned) AS spend_earn_ratio,

  -- 힌트 (하트를 낸 것과 광고로 연 것을 절대 합치지 않는다)
  IFNULL(h.paid_hint_count, 0)      AS paid_hint_count,
  IFNULL(h.ad_hint_count, 0)        AS ad_hint_count,
  IFNULL(h.paid_hint_users, 0)      AS paid_hint_users

FROM spine AS sp
LEFT JOIN topups AS t ON t.source = sp.source AND t.d = sp.d
LEFT JOIN spend  AS s ON s.source = sp.source AND s.d = sp.d
LEFT JOIN hints  AS h ON h.source = sp.source AND h.d = sp.d
