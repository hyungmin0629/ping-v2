-- =====================================================================
-- mart_daily · 하루 × 차원 = 한 행 (**합계 전용**)
-- =====================================================================
-- 시계열 차트가 읽는 표다. 담는 것은 **더할 수 있는 것만**이다 —
-- 가입 수 · 투표 수 · 하트 · 매출처럼 날짜를 걸쳐 SUM 해도 뜻이 변하지 않는 값.
--
-- ⚠️ **활성 유저 수(DAU/WAU/MAU)를 여기 두지 않는다.** 사람 수는 날짜 축으로
--    더해지지 않는다 — 같은 사람이 이틀 접속하면 2가 된다. 사람을 세는 일은
--    `mart_user_activity` 가 한다([[mart-grain-for-weekly-filter]] 규칙 ③).
--    차원 축(시도·학년)으로는 더해도 된다. 유저는 한 조합에만 속하기 때문이다.
--
-- ⚠️ **비율을 굽지 않는다.** 분자·분모를 나란히 싣는다(규칙 ②).
--
-- 각 지표는 **자기 사건이 일어난 날**에 실린다. 가입은 가입일, 매출은 결제일이다.
--
-- 사건을 (유저·날짜·지표이름·값) 네 컬럼의 긴 형식으로 모았다가 한 번에 편다.
-- 지표마다 CTE 를 만들어 FULL JOIN 하면 지표를 하나 더할 때 손댈 곳이 여러 군데고,
-- 위치 기반 UNION 은 0 의 개수를 세다 틀린다.
-- =====================================================================
CREATE OR REPLACE TABLE `{{mart}}.mart_daily`
PARTITION BY metric_date
CLUSTER BY source, sido AS

WITH users AS (
  SELECT * FROM `{{stg}}.stg_user` WHERE NOT is_admin
),

events AS (
  SELECT user_key, signup_date AS d, 'signups' AS metric, 1 AS value
  FROM users

  UNION ALL
  SELECT user_key, DATE(withdrawn_at, 'Asia/Seoul'), 'withdrawals', 1
  FROM users WHERE is_withdrawn

  UNION ALL
  SELECT s.user_key, s.session_date, m.metric, m.value
  FROM `{{stg}}.stg_user_session` AS s
  JOIN users AS u ON u.user_key = s.user_key
  CROSS JOIN UNNEST([
    STRUCT('sessions' AS metric, 1 AS value),
    STRUCT('session_seconds', IFNULL(s.duration_sec, 0))
  ]) AS m
  WHERE NOT s.is_duplicate AND s.started_at < u.valid_until

  UNION ALL
  SELECT v.user_key, v.voted_date, 'votes_cast', 1
  FROM `{{stg}}.stg_vote_item` AS v
  JOIN users AS u ON u.user_key = v.user_key
  WHERE v.is_voted AND v.voted_at < u.valid_until

  UNION ALL
  SELECT r.receiver_key, r.received_date, m.metric, m.value
  FROM `{{stg}}.stg_vote_received` AS r
  JOIN users AS u ON u.user_key = r.receiver_key
  CROSS JOIN UNNEST([
    STRUCT('votes_received' AS metric, 1 AS value),
    STRUCT('votes_read', IF(r.is_read, 1, 0))
  ]) AS m
  WHERE r.received_at < u.valid_until

  UNION ALL
  SELECT h.user_key, h.hint_date, m.metric, m.value
  FROM `{{stg}}.stg_hint_purchase` AS h
  JOIN users AS u ON u.user_key = h.user_key
  CROSS JOIN UNNEST([
    STRUCT('hints_opened' AS metric, 1 AS value),
    STRUCT('hints_paid', IF(h.is_paid_hint, 1, 0)),
    STRUCT('hints_by_ad', IF(h.is_ad_hint, 1, 0))
  ]) AS m
  WHERE h.created_at < u.valid_until

  UNION ALL
  SELECT t.user_key, t.tx_date, m.metric, m.value
  FROM `{{stg}}.stg_heart_transaction` AS t
  JOIN users AS u ON u.user_key = t.user_key
  CROSS JOIN UNNEST([
    STRUCT('hearts_earned' AS metric, t.hearts_earned AS value),
    STRUCT('hearts_spent', t.hearts_spent)
  ]) AS m
  WHERE t.created_at < u.valid_until

  UNION ALL
  SELECT p.user_key, p.purchase_date, m.metric, m.value
  FROM `{{stg}}.stg_heart_purchase` AS p
  JOIN users AS u ON u.user_key = p.user_key
  CROSS JOIN UNNEST([
    STRUCT('purchases' AS metric, IF(p.is_revenue, 1, 0) AS value),
    STRUCT('revenue_krw', IF(p.is_revenue, p.price_krw, 0)),
    STRUCT('stub_purchases', IF(p.is_stub, 1, 0))
  ]) AS m
  WHERE p.created_at < u.valid_until

  UNION ALL
  SELECT rp.reporter_key, rp.report_date, m.metric, m.value
  FROM `{{stg}}.stg_report` AS rp
  JOIN users AS u ON u.user_key = rp.reporter_key
  CROSS JOIN UNNEST([
    STRUCT('reports_filed' AS metric, 1 AS value),
    STRUCT('reports_closed', IF(rp.is_closed, 1, 0))
  ]) AS m
  WHERE rp.reported_at < u.valid_until
)

SELECT
  e.d                                                AS metric_date,
  u.source,
  u.sido,
  u.sido_iso,
  u.school_type,
  u.grade,
  u.gender,

  SUM(IF(e.metric = 'signups',        e.value, 0))   AS signups,
  SUM(IF(e.metric = 'withdrawals',    e.value, 0))   AS withdrawals,
  SUM(IF(e.metric = 'sessions',       e.value, 0))   AS sessions,
  SUM(IF(e.metric = 'session_seconds', e.value, 0))  AS session_seconds,
  SUM(IF(e.metric = 'votes_cast',     e.value, 0))   AS votes_cast,
  SUM(IF(e.metric = 'votes_received', e.value, 0))   AS votes_received,
  SUM(IF(e.metric = 'votes_read',     e.value, 0))   AS votes_read,
  SUM(IF(e.metric = 'hints_opened',   e.value, 0))   AS hints_opened,
  SUM(IF(e.metric = 'hints_paid',     e.value, 0))   AS hints_paid,
  SUM(IF(e.metric = 'hints_by_ad',    e.value, 0))   AS hints_by_ad,
  SUM(IF(e.metric = 'hearts_earned',  e.value, 0))   AS hearts_earned,
  SUM(IF(e.metric = 'hearts_spent',   e.value, 0))   AS hearts_spent,
  SUM(IF(e.metric = 'purchases',      e.value, 0))   AS purchases,
  SUM(IF(e.metric = 'revenue_krw',    e.value, 0))   AS revenue_krw,
  SUM(IF(e.metric = 'stub_purchases', e.value, 0))   AS stub_purchases,
  SUM(IF(e.metric = 'reports_filed',  e.value, 0))   AS reports_filed,
  -- 접수 대비 종결. **비율이 아니라 분자**다 — 나누는 것은 루커가 한다.
  -- ⚠️ 종결 건도 **접수일**에 실린다. "이 주에 들어온 신고 중 결국 처리된 수"다.
  SUM(IF(e.metric = 'reports_closed', e.value, 0))   AS reports_closed

FROM events AS e
JOIN users AS u ON u.user_key = e.user_key
WHERE e.d IS NOT NULL
GROUP BY metric_date, source, sido, sido_iso, school_type, grade, gender
