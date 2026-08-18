-- =====================================================================
-- mart_user_activity · 유저 한 명의 활동일 하루 = 한 행
-- =====================================================================
-- **이 표의 존재 이유는 하나다 — distinct 를 미리 세지 않기 위해서.**
--
-- MAU·WAU·주간 투표자·주간 결제자는 **기간이 바뀌면 다시 세야 하는** 지표다.
-- 월별로 미리 집계해 두면 주간 값을 낼 수 없고, 일별 DAU 를 7일 더해도 WAU 가
-- 아니다(같은 사람이 여러 날 접속한다). 원자 행을 **유저 단위로** 남겨 두면
-- 루커가 어떤 기간에서든 `COUNT(DISTINCT user_key)` 를 다시 센다
-- ([[mart-grain-for-weekly-filter]] 규칙 ③).
--
-- 크기를 재고 골랐다 — 유저×일 상한은 654만 행이지만 실측 **262,540행**이다.
-- 세션이 병합돼 있어 유저당 접속일이 평균 14일뿐이다.
--
-- ⚠️ '활동일'은 접속한 날만이 아니다. 투표·하트·결제가 일어난 날도 포함한다 —
--    세션 로그가 없는 활동이 섞여 있어도 그 날이 통째로 사라지지 않게 한다.
-- ⚠️ 중복 세션 로그(0.4%)는 여기서 뺀다.
-- =====================================================================
CREATE OR REPLACE TABLE `{{mart}}.mart_user_activity`
PARTITION BY metric_date
CLUSTER BY source, sido AS

WITH users AS (
  SELECT * FROM `{{stg}}.stg_user` WHERE NOT is_admin
),

sess AS (
  SELECT
    s.user_key,
    s.session_date                              AS d,
    COUNT(*)                                    AS session_count,
    SUM(s.duration_sec)                         AS session_seconds
  FROM `{{stg}}.stg_user_session` AS s
  JOIN users AS u ON u.user_key = s.user_key
  WHERE NOT s.is_duplicate AND s.started_at < u.valid_until
  GROUP BY s.user_key, s.session_date
),

votes AS (
  SELECT v.user_key, v.voted_date AS d, COUNT(*) AS vote_count
  FROM `{{stg}}.stg_vote_item` AS v
  JOIN users AS u ON u.user_key = v.user_key
  WHERE v.is_voted AND v.voted_at < u.valid_until
  GROUP BY v.user_key, v.voted_date
),

recv AS (
  SELECT
    r.receiver_key                              AS user_key,
    r.received_date                             AS d,
    COUNT(*)                                    AS received_count,
    COUNTIF(r.is_read)                          AS read_count
  FROM `{{stg}}.stg_vote_received` AS r
  JOIN users AS u ON u.user_key = r.receiver_key
  WHERE r.received_at < u.valid_until
  GROUP BY r.receiver_key, r.received_date
),

hints AS (
  SELECT
    h.user_key, h.hint_date AS d,
    COUNT(*)                                    AS hint_open_count,
    COUNTIF(h.is_paid_hint)                     AS hint_paid_count,
    COUNTIF(h.is_ad_hint)                       AS hint_ad_count
  FROM `{{stg}}.stg_hint_purchase` AS h
  JOIN users AS u ON u.user_key = h.user_key
  WHERE h.created_at < u.valid_until
  GROUP BY h.user_key, h.hint_date
),

hearts AS (
  SELECT
    t.user_key, t.tx_date AS d,
    SUM(t.hearts_earned)                        AS hearts_earned,
    SUM(t.hearts_spent)                         AS hearts_spent
  FROM `{{stg}}.stg_heart_transaction` AS t
  JOIN users AS u ON u.user_key = t.user_key
  WHERE t.created_at < u.valid_until
  GROUP BY t.user_key, t.tx_date
),

pays AS (
  SELECT
    p.user_key, p.purchase_date AS d,
    COUNTIF(p.is_revenue)                       AS purchase_count,
    SUM(IF(p.is_revenue, p.price_krw, 0))       AS revenue_krw,
    COUNTIF(p.is_stub)                          AS stub_count
  FROM `{{stg}}.stg_heart_purchase` AS p
  JOIN users AS u ON u.user_key = p.user_key
  WHERE p.created_at < u.valid_until
  GROUP BY p.user_key, p.purchase_date
),

-- 활동이 있었던 (유저, 날짜) 를 모은다. 어느 한 갈래만 있어도 그 날은 살아 있다.
spine AS (
  SELECT user_key, d FROM sess
  UNION DISTINCT SELECT user_key, d FROM votes
  UNION DISTINCT SELECT user_key, d FROM recv
  UNION DISTINCT SELECT user_key, d FROM hints
  UNION DISTINCT SELECT user_key, d FROM hearts
  UNION DISTINCT SELECT user_key, d FROM pays
)

SELECT
  sp.user_key,
  sp.d                                          AS metric_date,

  -- 차원 — 여덟 표가 같은 이름을 쓴다. 루커에서 조인하지 않게 복사해 싣는다.
  u.source,
  u.sido,
  u.school_type,
  u.grade,
  u.gender,

  -- 접속했는가 (세션 기준). 투표만 있고 세션이 없는 날과 구분한다.
  s.user_key IS NOT NULL                        AS is_active,
  IFNULL(s.session_count, 0)                    AS session_count,
  IFNULL(s.session_seconds, 0)                  AS session_seconds,

  IFNULL(v.vote_count, 0)                       AS vote_count,
  v.user_key IS NOT NULL                        AS is_voter,

  IFNULL(r.received_count, 0)                   AS received_count,
  IFNULL(r.read_count, 0)                       AS read_count,

  IFNULL(h.hint_open_count, 0)                  AS hint_open_count,
  IFNULL(h.hint_paid_count, 0)                  AS hint_paid_count,
  IFNULL(h.hint_ad_count, 0)                    AS hint_ad_count,

  IFNULL(t.hearts_earned, 0)                    AS hearts_earned,
  IFNULL(t.hearts_spent, 0)                     AS hearts_spent,

  IFNULL(p.purchase_count, 0)                   AS purchase_count,
  IFNULL(p.revenue_krw, 0)                      AS revenue_krw,
  IFNULL(p.purchase_count, 0) > 0               AS is_payer,
  IFNULL(p.stub_count, 0)                       AS stub_purchase_count,

  -- 가입 후 며칠째인가 — 코호트 리텐션을 이 표 하나로 그릴 수 있게 둔다
  DATE_DIFF(sp.d, u.signup_date, DAY)           AS days_since_signup

FROM spine AS sp
JOIN users     AS u ON u.user_key = sp.user_key
LEFT JOIN sess   AS s ON s.user_key = sp.user_key AND s.d = sp.d
LEFT JOIN votes  AS v ON v.user_key = sp.user_key AND v.d = sp.d
LEFT JOIN recv   AS r ON r.user_key = sp.user_key AND r.d = sp.d
LEFT JOIN hints  AS h ON h.user_key = sp.user_key AND h.d = sp.d
LEFT JOIN hearts AS t ON t.user_key = sp.user_key AND t.d = sp.d
LEFT JOIN pays   AS p ON p.user_key = sp.user_key AND p.d = sp.d
