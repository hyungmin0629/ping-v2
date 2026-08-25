-- =====================================================================
-- 10_weekly_core · 최근 8주 × 주간 핵심 지표 (1쪽·3쪽의 뼈대)
-- =====================================================================
-- 한 행이 한 주다. 금주와 전주를 따로 묻지 않고 8주를 한 번에 받아
-- **전주 대비도 8주 추이도 같은 표에서 만든다.** 두 번 물으면 두 답이
-- 갈릴 수 있고(주 경계 정의가 어긋난다), 스캔도 두 배가 된다.
--
-- 주의 시작은 **월요일**이다. `mart_backlog_weekly` 가 이미 월요일 기준이라
-- 거기 맞춘다 — 안 맞추면 적체 그래프만 한 칸 어긋난다.
--
-- ⚠️ **비율을 여기서 만들지 않는다.** 분자·분모를 나란히 싣고 나누는 것은
--    파이썬이 한다(마트 규칙 ②와 같은 이유). 분모가 작을 때 비율을 감추는
--    판단도 거기서 한다 — SQL 은 "몇 명인가"만 답한다.
--
-- 지표의 뜻:
--   wau              그 주에 활동한 사람 수 (접속·투표·하트·결제 중 하나라도)
--   voters           그 주에 투표한 사람 수
--   eligible         그 주 끝 기준 **친구 5명을 확보한** 가입자 수 = 참여율의 분모
--   eligible_voters  그중 실제로 투표한 사람 수 = 참여율의 분자
--   first_payers     그 주에 **처음** 결제한 사람 수
--                    ⚠️ `mart_user` 에 첫 결제일 컬럼이 없어 활동 이력에서 센다.
--                       `purchase_count` 는 마트에서 이미 스텁을 뺀 값이다.
-- =====================================================================
WITH win AS (
  SELECT
    DATE_SUB(@week_start, INTERVAL 7 WEEK)  AS lo,
    DATE_ADD(@week_start, INTERVAL 6 DAY)   AS hi
),

weeks AS (
  SELECT wk
  FROM win, UNNEST(GENERATE_DATE_ARRAY(win.lo, @week_start, INTERVAL 1 WEEK)) AS wk
),

-- 사람 수는 **기간이 바뀌면 다시 세야 한다.** 유저×일 원자 행에서 매번 센다.
act AS (
  SELECT
    DATE_TRUNC(a.metric_date, WEEK(MONDAY))                 AS wk,
    COUNT(DISTINCT a.user_key)                              AS wau,
    COUNT(DISTINCT IF(a.is_voter, a.user_key, NULL))        AS voters,
    COUNT(DISTINCT IF(a.is_payer, a.user_key, NULL))        AS payers,
    SUM(a.session_count)                                    AS sessions,
    SUM(a.session_seconds)                                  AS session_seconds
  FROM `{{mart}}.mart_user_activity` AS a, win
  WHERE a.source = @source AND a.metric_date BETWEEN win.lo AND win.hi
  GROUP BY wk
),

-- 유효 사용자 — 투표는 친구 5명이 있어야 열린다. 그 게이트를 통과한 사람만
-- 참여율의 분모가 된다. `mart_user.metric_date` 는 가입일이다.
elig_users AS (
  SELECT user_key, metric_date AS signup_date
  FROM `{{mart}}.mart_user`
  WHERE source = @source AND f2_five_friends
),

elig_cnt AS (
  SELECT w.wk, COUNT(*) AS eligible
  FROM weeks AS w
  JOIN elig_users AS e ON e.signup_date <= DATE_ADD(w.wk, INTERVAL 6 DAY)
  GROUP BY w.wk
),

elig_vot AS (
  SELECT
    DATE_TRUNC(a.metric_date, WEEK(MONDAY))  AS wk,
    COUNT(DISTINCT a.user_key)               AS eligible_voters
  FROM `{{mart}}.mart_user_activity` AS a
  JOIN elig_users AS e ON e.user_key = a.user_key, win
  WHERE a.source = @source AND a.is_voter
    AND a.metric_date BETWEEN win.lo AND win.hi
  GROUP BY wk
),

-- 더할 수 있는 것들. 사람 수와 달리 날짜를 걸쳐 SUM 해도 뜻이 변하지 않는다.
dly AS (
  SELECT
    DATE_TRUNC(d.metric_date, WEEK(MONDAY))  AS wk,
    SUM(d.signups)          AS signups,
    SUM(d.withdrawals)      AS withdrawals,
    SUM(d.votes_cast)       AS votes_cast,
    SUM(d.votes_received)   AS votes_received,
    SUM(d.votes_read)       AS votes_read,
    SUM(d.hints_opened)     AS hints_opened,
    SUM(d.hints_paid)       AS hints_paid,
    SUM(d.hints_by_ad)      AS hints_by_ad,
    SUM(d.hearts_earned)    AS hearts_earned,
    SUM(d.hearts_spent)     AS hearts_spent,
    SUM(d.revenue_krw)      AS revenue_krw,
    SUM(d.purchases)        AS purchases,
    SUM(d.stub_purchases)   AS stub_purchases,
    SUM(d.reports_filed)    AS reports_filed,
    SUM(d.reports_closed)   AS reports_closed
  FROM `{{mart}}.mart_daily` AS d, win
  WHERE d.source = @source AND d.metric_date BETWEEN win.lo AND win.hi
  GROUP BY wk
),

-- 첫 결제 — 전 기간을 봐야 "처음"을 알 수 있다. 창 안으로 자르면
-- 예전에 결제한 사람이 이번 주에 처음 결제한 것으로 잡힌다.
first_pay AS (
  SELECT user_key, MIN(metric_date) AS first_purchase_date
  FROM `{{mart}}.mart_user_activity`
  WHERE source = @source AND purchase_count > 0
  GROUP BY user_key
),

fp AS (
  SELECT DATE_TRUNC(first_purchase_date, WEEK(MONDAY)) AS wk, COUNT(*) AS first_payers
  FROM first_pay
  GROUP BY wk
)

SELECT
  w.wk                              AS week_start,
  IFNULL(a.wau, 0)                  AS wau,
  IFNULL(a.voters, 0)               AS voters,
  IFNULL(a.payers, 0)               AS payers,
  IFNULL(a.sessions, 0)             AS sessions,
  IFNULL(a.session_seconds, 0)      AS session_seconds,
  IFNULL(e.eligible, 0)             AS eligible,
  IFNULL(v.eligible_voters, 0)      AS eligible_voters,
  IFNULL(f.first_payers, 0)         AS first_payers,
  IFNULL(d.signups, 0)              AS signups,
  IFNULL(d.withdrawals, 0)          AS withdrawals,
  IFNULL(d.votes_cast, 0)           AS votes_cast,
  IFNULL(d.votes_received, 0)       AS votes_received,
  IFNULL(d.votes_read, 0)           AS votes_read,
  IFNULL(d.hints_opened, 0)         AS hints_opened,
  IFNULL(d.hints_paid, 0)           AS hints_paid,
  IFNULL(d.hints_by_ad, 0)          AS hints_by_ad,
  IFNULL(d.hearts_earned, 0)        AS hearts_earned,
  IFNULL(d.hearts_spent, 0)         AS hearts_spent,
  IFNULL(d.revenue_krw, 0)          AS revenue_krw,
  IFNULL(d.purchases, 0)            AS purchases,
  IFNULL(d.stub_purchases, 0)       AS stub_purchases,
  IFNULL(d.reports_filed, 0)        AS reports_filed,
  IFNULL(d.reports_closed, 0)       AS reports_closed
FROM weeks AS w
LEFT JOIN act      AS a ON a.wk = w.wk
LEFT JOIN elig_cnt AS e ON e.wk = w.wk
LEFT JOIN elig_vot AS v ON v.wk = w.wk
LEFT JOIN dly      AS d ON d.wk = w.wk
LEFT JOIN fp       AS f ON f.wk = w.wk
ORDER BY week_start
