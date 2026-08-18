-- =====================================================================
-- mart_user · 유저 한 명 = 한 행 (차원 표)
-- =====================================================================
-- 이 표가 답하는 질문: **이 사람은 어디까지 왔나.**
-- 가입 → 친구 5명 → 투표 시작 → 세션 완료 → 힌트 1·2·3 → 이름 공개.
--
-- 날짜 축은 **가입일**이다(`metric_date = signup_date`). 기간 필터를 걸면
-- "그 주에 가입한 사람"이 되고, 유저는 가입일이 하나뿐이라 기간 합산이 성립한다.
-- ⚠️ 최근 코호트는 관찰기간이 짧아 뒷단계가 늘 낮게 나온다 — 화면에 주석을 단다.
--
-- ⚠️ **탈퇴자를 빼지 않는다.** 빼면 이탈률의 분자가 사라진다. 플래그로 싣고
--    거를지는 보는 쪽이 고른다. 운영자만 뺀다.
--
-- ⚠️ **비율을 굽지 않는다.** 분자와 분모를 각각 싣고 루커가 나눈다
--    ([[mart-grain-for-weekly-filter]] 규칙 ②).
-- =====================================================================
CREATE OR REPLACE TABLE `{{mart}}.mart_user`
PARTITION BY metric_date
CLUSTER BY source, sido AS

WITH users AS (
  SELECT * FROM `{{stg}}.stg_user` WHERE NOT is_admin
),

-- [1] 친구 — 가입 7일 내에 몇 명을 맺었나 --------------------------------
--     `stg_friend_edge` 는 관계를 유저 관점 2행으로 펴 둔 뷰다.
--     ⚠️ 끊긴 관계도 센다. "그때 맺었다"는 사실은 지금 살아 있는지와 무관하다.
friends AS (
  SELECT
    e.user_key,
    COUNTIF(e.friended_at < TIMESTAMP_ADD(u.signed_up_at, INTERVAL 7 DAY)) AS friends_7d,
    COUNT(*)                                    AS friends_ever,
    COUNTIF(e.is_active)                        AS friends_now,
    -- 통틀어 5명을 맺어본 적이 있는가. 해금 조건과 같은 물음이다.
    COUNT(*) >= 5                               AS ever_five_friends
  FROM `{{stg}}.stg_friend_edge` AS e
  JOIN users AS u ON u.user_key = e.user_key
  WHERE e.friended_at < u.valid_until
  GROUP BY e.user_key
),

-- [2] 투표 — 낸 쪽 -------------------------------------------------------
votes AS (
  SELECT
    v.user_key,
    MIN(v.voted_at)                             AS first_vote_at,
    MAX(v.voted_at)                             AS last_vote_at,
    COUNT(*)                                    AS vote_count
  FROM `{{stg}}.stg_vote_item` AS v
  JOIN users AS u ON u.user_key = v.user_key
  WHERE v.is_voted AND v.voted_at < u.valid_until
  GROUP BY v.user_key
),

sessions AS (
  SELECT
    s.user_key,
    COUNT(*)                                    AS vote_session_count,
    COUNTIF(s.is_completed)                     AS vote_session_completed
  FROM `{{stg}}.stg_vote_session` AS s
  JOIN users AS u ON u.user_key = s.user_key
  WHERE s.started_at < u.valid_until
  GROUP BY s.user_key
),

-- [3] 접속 -------------------------------------------------------------
--     중복 로그(0.4%)를 여기서 뺀다. 안 빼면 접속일 수가 부풀려진다.
access AS (
  SELECT
    a.user_key,
    COUNT(DISTINCT a.session_date)              AS active_days,
    MIN(a.started_at)                           AS first_seen_at,
    MAX(a.started_at)                           AS last_seen_at
  FROM `{{stg}}.stg_user_session` AS a
  JOIN users AS u ON u.user_key = a.user_key
  WHERE NOT a.is_duplicate AND a.started_at < u.valid_until
  GROUP BY a.user_key
),

-- [4] 투표 — 받은 쪽 ----------------------------------------------------
--     '수신 미경험'(스케치 2쪽)의 분모가 여기서 나온다.
received AS (
  SELECT
    r.receiver_key                              AS user_key,
    COUNT(*)                                    AS received_count,
    COUNTIF(r.is_read)                          AS read_count
  FROM `{{stg}}.stg_vote_received` AS r
  JOIN users AS u ON u.user_key = r.receiver_key
  WHERE r.received_at < u.valid_until
  GROUP BY r.receiver_key
),

-- [5] 힌트 --------------------------------------------------------------
--     ⚠️ 이름 공개는 `hint_type = 'FULL_NAME'` 으로 센다. `reveal_status` 는
--        합성 v5 에서 갱신되지 않는다 — [[synthetic-reveal-status-not-updated]].
--     ⚠️ 광고로 연 무료 힌트를 '구매'로 세지 않는다. 둘을 갈라 싣는다.
hints AS (
  SELECT
    h.user_key,
    COUNT(*)                                                        AS hint_open_count,
    COUNTIF(h.is_paid_hint)                                         AS hint_paid_count,
    COUNTIF(h.is_ad_hint)                                           AS hint_ad_count,
    COUNT(DISTINCT IF(h.hint_type <> 'FULL_NAME', h.hint_type, NULL)) AS basic_hint_types,
    COUNTIF(h.hint_type = 'FULL_NAME')                              AS full_name_count
  FROM `{{stg}}.stg_hint_purchase` AS h
  JOIN users AS u ON u.user_key = h.user_key
  WHERE h.created_at < u.valid_until
  GROUP BY h.user_key
),

-- [6] 하트와 결제 --------------------------------------------------------
hearts AS (
  SELECT
    t.user_key,
    SUM(t.hearts_earned)                        AS hearts_earned,
    SUM(t.hearts_spent)                         AS hearts_spent
  FROM `{{stg}}.stg_heart_transaction` AS t
  JOIN users AS u ON u.user_key = t.user_key
  WHERE t.created_at < u.valid_until
  GROUP BY t.user_key
),

purchases AS (
  SELECT
    p.user_key,
    COUNTIF(p.is_revenue)                       AS purchase_count,
    SUM(IF(p.is_revenue, p.price_krw, 0))       AS revenue_krw,
    COUNTIF(p.is_stub)                          AS stub_count
  FROM `{{stg}}.stg_heart_purchase` AS p
  JOIN users AS u ON u.user_key = p.user_key
  WHERE p.created_at < u.valid_until
  GROUP BY p.user_key
),

reports AS (
  SELECT r.reporter_key AS user_key, COUNT(*) AS reports_filed
  FROM `{{stg}}.stg_report` AS r
  JOIN users AS u ON u.user_key = r.reporter_key
  WHERE r.reported_at < u.valid_until
  GROUP BY r.reporter_key
)

SELECT
  u.user_key,

  -- 날짜 축 — 가입일 코호트
  u.signup_date                                              AS metric_date,

  -- 차원 (여덟 표 전부 같은 이름을 쓴다)
  u.source,
  u.sido,
  u.sido_iso,
  u.school_type,
  u.grade,
  u.gender,
  u.school_name,
  u.sigungu,

  -- 생애 주기
  u.signed_up_at,
  u.service_unlocked_at,
  a.first_seen_at,
  a.last_seen_at,
  v.first_vote_at,
  DATE(v.first_vote_at, 'Asia/Seoul')                        AS first_vote_date,
  TIMESTAMP_DIFF(u.service_unlocked_at, u.signed_up_at, DAY) AS days_to_unlock,
  TIMESTAMP_DIFF(v.first_vote_at, u.signed_up_at, DAY)       AS days_to_first_vote,

  -- 퍼널 여덟 단계. 뒤 단계는 앞 단계를 포함한다(누적 정의).
  TRUE                                                       AS f1_signed_up,
  IFNULL(f.ever_five_friends, FALSE)                         AS f2_five_friends,
  v.first_vote_at IS NOT NULL                                AS f3_voted,
  IFNULL(s.vote_session_completed, 0) > 0                    AS f4_session_completed,
  IFNULL(h.basic_hint_types, 0) >= 1                         AS f5_hint1,
  IFNULL(h.basic_hint_types, 0) >= 2                         AS f6_hint2,
  IFNULL(h.basic_hint_types, 0) >= 3                         AS f7_hint3,
  IFNULL(h.full_name_count, 0) > 0                           AS f8_name_revealed,

  -- 친구
  IFNULL(f.friends_7d, 0)                                    AS friends_7d,
  CASE
    WHEN IFNULL(f.friends_7d, 0) = 0  THEN '0명'
    WHEN     f.friends_7d <= 2        THEN '1–2명'
    WHEN     f.friends_7d <= 4        THEN '3–4명'
    WHEN     f.friends_7d <= 9        THEN '5–9명'
    ELSE '10명 이상'
  END                                                        AS friends_7d_bucket,
  IFNULL(f.friends_ever, 0)                                  AS friends_ever,
  IFNULL(f.friends_now, 0)                                   AS friends_now,
  u.service_unlocked_at IS NOT NULL                          AS is_unlocked,

  -- 받은 투표 — 미경험 세그먼트(스케치 2쪽). 셋으로 갈린다.
  IFNULL(r.received_count, 0)                                AS received_count,
  IFNULL(r.read_count, 0)                                    AS read_count,
  IFNULL(r.received_count, 0) = 0                            AS is_never_received,
  CASE
    WHEN IFNULL(r.received_count, 0) > 0        THEN NULL
    WHEN v.first_vote_at IS NOT NULL            THEN '발신 경험 + 미수신'
    WHEN u.service_unlocked_at IS NULL          THEN '미해금 + 미수신'
    ELSE '해금 + 미수신'
  END                                                        AS unreceived_segment,

  -- 활동 누계
  IFNULL(a.active_days, 0)                                   AS active_days,
  IFNULL(v.vote_count, 0)                                    AS vote_count,
  IFNULL(s.vote_session_count, 0)                            AS vote_session_count,
  IFNULL(s.vote_session_completed, 0)                        AS vote_session_completed,
  IFNULL(h.hint_open_count, 0)                               AS hint_open_count,
  IFNULL(h.hint_paid_count, 0)                               AS hint_paid_count,
  IFNULL(h.hint_ad_count, 0)                                 AS hint_ad_count,
  IFNULL(hb.hearts_earned, 0)                                AS hearts_earned,
  IFNULL(hb.hearts_spent, 0)                                 AS hearts_spent,
  IFNULL(p.purchase_count, 0)                                AS purchase_count,
  IFNULL(p.revenue_krw, 0)                                   AS revenue_krw,
  IFNULL(p.purchase_count, 0) > 0                            AS is_payer,
  IFNULL(p.stub_count, 0)                                    AS stub_purchase_count,
  IFNULL(rp.reports_filed, 0)                                AS reports_filed,

  -- 이탈 — 지우지 않고 표시한다
  u.is_withdrawn,
  u.withdrawn_at,
  u.withdrawal_reason_code,
  u.first_banned_at IS NOT NULL                              AS is_banned,
  u.is_synthetic

FROM users     AS u
LEFT JOIN friends   AS f  ON f.user_key  = u.user_key
LEFT JOIN votes     AS v  ON v.user_key  = u.user_key
LEFT JOIN sessions  AS s  ON s.user_key  = u.user_key
LEFT JOIN access    AS a  ON a.user_key  = u.user_key
LEFT JOIN received  AS r  ON r.user_key  = u.user_key
LEFT JOIN hints     AS h  ON h.user_key  = u.user_key
LEFT JOIN hearts    AS hb ON hb.user_key = u.user_key
LEFT JOIN purchases AS p  ON p.user_key  = u.user_key
LEFT JOIN reports   AS rp ON rp.user_key = u.user_key
