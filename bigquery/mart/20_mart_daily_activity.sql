-- =====================================================================
-- mart_daily_activity · 하루(KST) × 원천 = 한 행
-- ⚠️ **초안이다. 아직 BigQuery 에 만들지 않았다.**
--    마트 그레인은 `notebooks/dashboard.ipynb` 의 지표 12개를 보고 정한다.
--    확정되기 전까지 이 파일은 출발점일 뿐이다 — 결정된 설계가 아니다.
--    경위와 남은 결정은 docs/ops/ops-p5-p7.md.
-- =====================================================================
-- 대시보드의 시계열은 전부 이 표에서 나온다. **날짜는 이미 KST 다** —
-- 보는 쪽이 시간대를 의식하지 않게 하는 것이 이 층의 목적이다.
--
-- 뷰가 아니라 **테이블**이다. 루커 스튜디오는 화면을 그릴 때마다 쿼리를 날리는데,
-- 뷰로 두면 그때마다 1억 2천만 행을 다시 읽는다.
--
-- 세는 규칙
--   · 운영자 계정 제외
--   · 탈퇴·영구정지 **이후** 활동 제외 (`valid_until`)
--   · 중복 세션 로그(0.4%) 제외
--   · 지운 행 제외 (stg 에서 이미 걸렸다)
-- =====================================================================
CREATE OR REPLACE TABLE `{{mart}}.mart_daily_activity`
PARTITION BY activity_date
CLUSTER BY source AS

WITH u AS (
  SELECT * FROM `{{stg}}.stg_user` WHERE NOT is_admin
),

signup AS (
  SELECT source, signup_date AS d, COUNT(*) AS n
  FROM u WHERE signup_date IS NOT NULL GROUP BY 1, 2
),

unlocked AS (
  SELECT source, unlocked_date AS d, COUNT(*) AS n
  FROM u WHERE unlocked_date IS NOT NULL GROUP BY 1, 2
),

withdrawn AS (
  SELECT source, DATE(withdrawn_at, 'Asia/Seoul') AS d, COUNT(*) AS n
  FROM u WHERE withdrawn_at IS NOT NULL GROUP BY 1, 2
),

votes AS (
  SELECT
    v.source,
    v.voted_date                        AS d,
    COUNT(DISTINCT v.user_key)          AS voters,
    COUNT(*)                            AS vote_items,
    COUNT(DISTINCT v.vote_session_key)  AS vote_sessions,
    COUNTIF(v.is_padded)                AS padded_items,
    COUNTIF(v.is_sensitive)             AS sensitive_items,
    AVG(v.decide_sec)                   AS avg_decide_sec
  FROM `{{stg}}.stg_vote_item` AS v
  JOIN u ON u.user_key = v.user_key
  WHERE v.is_voted AND v.voted_at < u.valid_until
  GROUP BY 1, 2
),

served AS (
  SELECT v.source, v.served_date AS d, COUNT(*) AS n
  FROM `{{stg}}.stg_vote_item` AS v
  JOIN u ON u.user_key = v.user_key
  WHERE v.served_at < u.valid_until
  GROUP BY 1, 2
),

sessions AS (
  SELECT
    s.source,
    s.session_date              AS d,
    COUNT(DISTINCT s.user_key)  AS session_users,
    COUNT(*)                    AS sessions,
    AVG(s.duration_sec)         AS avg_session_sec
  FROM `{{stg}}.stg_user_session` AS s
  JOIN u ON u.user_key = s.user_key
  WHERE NOT s.is_duplicate AND s.started_at < u.valid_until
  GROUP BY 1, 2
),

hearts AS (
  SELECT
    t.source,
    t.tx_date            AS d,
    SUM(t.hearts_earned) AS hearts_earned,
    SUM(t.hearts_spent)  AS hearts_spent
  FROM `{{stg}}.stg_heart_transaction` AS t
  JOIN u ON u.user_key = t.user_key
  WHERE t.created_at < u.valid_until
  GROUP BY 1, 2
),

hints AS (
  SELECT
    h.source,
    h.hint_date                                AS d,
    COUNTIF(h.is_paid_hint)                    AS paid_hints,
    COUNTIF(h.is_ad_hint)                      AS ad_hints,
    SUM(IF(h.is_paid_hint, h.heart_cost, 0))   AS hint_hearts_spent
  FROM `{{stg}}.stg_hint_purchase` AS h
  JOIN u ON u.user_key = h.user_key
  WHERE h.created_at < u.valid_until
  GROUP BY 1, 2
),

-- 날짜 축. 어느 한 지표라도 값이 있는 날은 한 줄이 생긴다.
spine AS (
  SELECT source, d FROM signup
  UNION DISTINCT SELECT source, d FROM unlocked
  UNION DISTINCT SELECT source, d FROM withdrawn
  UNION DISTINCT SELECT source, d FROM votes
  UNION DISTINCT SELECT source, d FROM served
  UNION DISTINCT SELECT source, d FROM sessions
  UNION DISTINCT SELECT source, d FROM hearts
  UNION DISTINCT SELECT source, d FROM hints
)

SELECT
  sp.d                                  AS activity_date,
  sp.source,

  -- 유입
  IFNULL(g.n, 0)                        AS new_users,
  IFNULL(ul.n, 0)                       AS unlocked_users,
  IFNULL(wd.n, 0)                       AS withdrawn_users,

  -- 활동 (DAU 는 정의가 둘이다 — 접속 기준과 투표 기준. 둘 다 싣는다)
  IFNULL(se.session_users, 0)           AS dau_sessions,
  IFNULL(v.voters, 0)                   AS dau_voters,
  IFNULL(se.sessions, 0)                AS sessions,
  ROUND(se.avg_session_sec, 1)          AS avg_session_sec,

  -- 투표
  IFNULL(sv.n, 0)                       AS items_served,
  IFNULL(v.vote_items, 0)               AS items_voted,
  SAFE_DIVIDE(v.vote_items, sv.n)       AS vote_completion_rate,
  IFNULL(v.vote_sessions, 0)            AS vote_sessions,
  IFNULL(v.padded_items, 0)             AS padded_items,
  IFNULL(v.sensitive_items, 0)          AS sensitive_items,
  ROUND(v.avg_decide_sec, 1)            AS avg_decide_sec,

  -- 하트
  IFNULL(h.hearts_earned, 0)            AS hearts_earned,
  IFNULL(h.hearts_spent, 0)             AS hearts_spent,
  IFNULL(hi.paid_hints, 0)              AS paid_hints,
  IFNULL(hi.ad_hints, 0)                AS ad_hints,
  IFNULL(hi.hint_hearts_spent, 0)       AS hint_hearts_spent

FROM spine AS sp
LEFT JOIN signup    AS g  ON g.source  = sp.source AND g.d  = sp.d
LEFT JOIN unlocked  AS ul ON ul.source = sp.source AND ul.d = sp.d
LEFT JOIN withdrawn AS wd ON wd.source = sp.source AND wd.d = sp.d
LEFT JOIN votes     AS v  ON v.source  = sp.source AND v.d  = sp.d
LEFT JOIN served    AS sv ON sv.source = sp.source AND sv.d = sp.d
LEFT JOIN sessions  AS se ON se.source = sp.source AND se.d = sp.d
LEFT JOIN hearts    AS h  ON h.source  = sp.source AND h.d  = sp.d
LEFT JOIN hints     AS hi ON hi.source = sp.source AND hi.d = sp.d
