-- =====================================================================
-- mart_distribution · 분포 × 버킷 × 차원 × 날짜 = 한 행
-- =====================================================================
-- 막대 차트 세 개가 이 표 하나를 읽는다. 셋 다 **그레인이 다르다** —
-- 세션 단위 · 수신 건 단위 · 힌트 단위. 그래서 넓은 표로 만들 수 없고,
-- `dist_name` 으로 가르는 긴 형식이 된다.
--
--   문항 도달        세션 하나가 몇 문항까지 왔나 (1~10)
--   열람→첫 힌트     열어 보고 얼마 만에 첫 힌트를 샀나 (4구간)
--   힌트 종류        어떤 힌트를 여는가 (하트로 산 것과 광고로 연 것을 **가르지 않고 합치지 않는다**)
--
-- ⚠️ 버킷은 **누적이 아니라 배타적**이다. 단 '문항 도달'만 누적이다
--    (N문항 도달 = N문항 이상 낸 세션 수). 스케치의 "1문항 출제 = 100%" 가 그 뜻이다.
--    `is_cumulative` 로 표시해 둔다 — 안 적으면 보는 쪽이 반드시 헷갈린다.
--
-- 날짜 축은 사건일이다(세션 시작일 · 열람일 · 힌트일).
-- =====================================================================
CREATE OR REPLACE TABLE `{{mart}}.mart_distribution`
PARTITION BY metric_date
CLUSTER BY dist_name, source AS

WITH users AS (
  SELECT * FROM `{{stg}}.stg_user` WHERE NOT is_admin
),

-- [1] 문항 도달 --------------------------------------------------------
--     '푼 문항'이 아니라 '출제된 문항'으로 센다. 낸 뒤 안 고르고 나간 것도
--     거기까지 온 것이기 때문이다(`served_at` 은 있고 `voted_at` 은 없는 아이템).
session_items AS (
  SELECT
    v.vote_session_key,
    ANY_VALUE(u.source)      AS source,
    ANY_VALUE(u.sido)        AS sido,
    ANY_VALUE(u.school_type) AS school_type,
    ANY_VALUE(u.grade)       AS grade,
    ANY_VALUE(u.gender)      AS gender,
    MIN(v.served_date)       AS d,
    COUNT(*)                 AS items_served
  FROM `{{stg}}.stg_vote_item` AS v
  JOIN users AS u ON u.user_key = v.user_key
  WHERE v.served_at < u.valid_until
  GROUP BY v.vote_session_key
),

item_reach AS (
  SELECT
    '문항 도달'                            AS dist_name,
    TRUE                                   AS is_cumulative,
    'sessions'                             AS unit,
    n                                      AS bucket_no,
    FORMAT('%d문항', n)                    AS bucket_label,
    CAST(NULL AS STRING)                   AS sub_bucket,
    s.d                                    AS metric_date,
    s.source, s.sido, s.school_type, s.grade, s.gender,
    COUNTIF(s.items_served >= n)           AS value,
    COUNT(*)                               AS base
  FROM session_items AS s
  CROSS JOIN UNNEST(GENERATE_ARRAY(1, 10)) AS n
  GROUP BY dist_name, bucket_no, bucket_label, metric_date,
           s.source, s.sido, s.school_type, s.grade, s.gender
),

-- [2] 열람 → 첫 힌트 지연 ----------------------------------------------
--     분모는 '열어 본 수신 건' 전체가 아니라 **힌트를 하나라도 산 건**이다.
--     안 산 사람은 지연 시간이 없다 — 0 이 아니라 없음이다.
first_hint AS (
  SELECT
    r.vote_received_key,
    r.read_date                                     AS d,
    u.source, u.sido, u.school_type, u.grade, u.gender,
    TIMESTAMP_DIFF(MIN(h.created_at), r.read_at, HOUR) AS wait_hours
  FROM `{{stg}}.stg_vote_received` AS r
  JOIN users AS u ON u.user_key = r.receiver_key
  JOIN `{{stg}}.stg_hint_purchase` AS h
    ON h.vote_received_key = r.vote_received_key AND h.created_at >= r.read_at
  WHERE r.is_read AND r.received_at < u.valid_until
  GROUP BY r.vote_received_key, r.read_date, r.read_at,
           u.source, u.sido, u.school_type, u.grade, u.gender
),

hint_delay AS (
  SELECT
    '열람→첫 힌트'                                  AS dist_name,
    FALSE                                           AS is_cumulative,
    'events'                                        AS unit,
    CASE
      WHEN wait_hours < 1  THEN 1
      WHEN wait_hours < 6  THEN 2
      WHEN wait_hours < 24 THEN 3
      ELSE 4
    END                                             AS bucket_no,
    CASE
      WHEN wait_hours < 1  THEN '1시간 이내'
      WHEN wait_hours < 6  THEN '1–6시간'
      WHEN wait_hours < 24 THEN '6–24시간'
      ELSE '24시간 이후'
    END                                             AS bucket_label,
    CAST(NULL AS STRING)                            AS sub_bucket,
    d                                               AS metric_date,
    source, sido, school_type, grade, gender,
    COUNT(*)                                        AS value,
    COUNT(*)                                        AS base
  FROM first_hint
  GROUP BY dist_name, bucket_no, bucket_label, metric_date,
           source, sido, school_type, grade, gender
),

-- [3] 힌트 종류 --------------------------------------------------------
--     ⚠️ 하트로 산 것과 광고로 연 것을 **합치지 않는다.** 성별 힌트의 30%가
--        광고 경로라(W14) 합치면 '많이 팔린 힌트'로 잘못 읽힌다.
hint_kind AS (
  SELECT
    '힌트 종류'                                     AS dist_name,
    FALSE                                           AS is_cumulative,
    'events'                                        AS unit,
    CASE h.hint_type
      WHEN 'GENDER' THEN 1 WHEN 'INITIAL' THEN 2 WHEN 'MEDIAL' THEN 3
      WHEN 'FINAL'  THEN 4 WHEN 'CLASS'   THEN 5 ELSE 6
    END                                             AS bucket_no,
    CASE h.hint_type
      WHEN 'GENDER' THEN '성별' WHEN 'INITIAL' THEN '초성' WHEN 'MEDIAL' THEN '중성'
      WHEN 'FINAL'  THEN '종성' WHEN 'CLASS'   THEN '반'   ELSE '이름 공개'
    END                                             AS bucket_label,
    IF(h.is_ad_hint, '광고', '하트')                AS sub_bucket,
    h.hint_date                                     AS metric_date,
    u.source, u.sido, u.school_type, u.grade, u.gender,
    COUNT(*)                                        AS value,
    COUNT(*)                                        AS base
  FROM `{{stg}}.stg_hint_purchase` AS h
  JOIN users AS u ON u.user_key = h.user_key
  WHERE h.created_at < u.valid_until
  GROUP BY dist_name, bucket_no, bucket_label, sub_bucket, metric_date,
           u.source, u.sido, u.school_type, u.grade, u.gender
)

SELECT * FROM item_reach  WHERE metric_date IS NOT NULL
UNION ALL
SELECT * FROM hint_delay  WHERE metric_date IS NOT NULL
UNION ALL
SELECT * FROM hint_kind   WHERE metric_date IS NOT NULL
