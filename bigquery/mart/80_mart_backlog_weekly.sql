-- =====================================================================
-- mart_backlog_weekly · 주 × 차원 = 한 행 (**시점 스냅샷**)
-- =====================================================================
-- **적체는 사건이 아니라 상태다.** "이번 주에 신고가 몇 건 들어왔나"는 접수일로
-- 셀 수 있지만(`mart_report`), "이번 주 말 기준으로 몇 건이 밀려 있나"는
-- 사건일 축으로는 나오지 않는다. 그래서 이 표만 그레인이 **주 스냅샷**이다.
--
-- 그리고 이 표가 **전주 대비 증감의 기준선**이다. 적체가 늘고 있는지 줄고 있는지는
-- 두 주를 나란히 놓아야만 보인다.
--
-- ⚠️ 누적 적재가 아니다. 과거 어느 시점의 미해결 건수는 지금 데이터로
--    **계산해서 복원**할 수 있다 —
--        접수됐고(created_at <= T) 아직 안 봤다(reviewed_at IS NULL OR reviewed_at > T)
--    그래서 `CREATE OR REPLACE` 로 매번 통째로 다시 구워도 이력이 사라지지 않는다.
--    (`mart_report.pending_days` 는 '오늘 기준'이고, 이 표는 '그 주 기준'이다.)
--
-- 주의 시작은 **월요일**이다. `DATE_TRUNC(d, WEEK(MONDAY))`.
-- =====================================================================
CREATE OR REPLACE TABLE `{{mart}}.mart_backlog_weekly`
PARTITION BY metric_date
CLUSTER BY source AS

WITH users AS (
  SELECT * FROM `{{stg}}.stg_user` WHERE NOT is_admin
),

reports AS (
  SELECT
    r.reported_at, r.report_date, r.reviewed_at, r.is_closed,
    u.source, u.sido, u.school_type, u.grade, u.gender
  FROM `{{stg}}.stg_report` AS r
  JOIN users AS u ON u.user_key = r.reporter_key
  WHERE r.reported_at < u.valid_until
),

-- 첫 신고가 들어온 주부터 마지막 신고가 들어온 주까지, 한 주도 빠뜨리지 않는다.
-- 빈 주가 빠지면 선 그래프가 그 구간을 이어 그려서 **없던 추세가 생긴다.**
weeks AS (
  SELECT week_start
  FROM (SELECT MIN(report_date) AS lo, MAX(report_date) AS hi FROM reports)
  CROSS JOIN UNNEST(GENERATE_DATE_ARRAY(
    DATE_TRUNC(lo, WEEK(MONDAY)), DATE_TRUNC(hi, WEEK(MONDAY)), INTERVAL 1 WEEK
  )) AS week_start
),

-- 그 주 **일요일 끝**을 기준 시각으로 삼는다(월요일 시작 + 7일).
snapshot AS (
  SELECT
    w.week_start,
    TIMESTAMP(DATE_ADD(w.week_start, INTERVAL 7 DAY), 'Asia/Seoul') AS as_of_ts,
    r.source, r.sido, r.school_type, r.grade, r.gender,
    r.reported_at, r.reviewed_at, r.report_date
  FROM weeks AS w
  JOIN reports AS r
    ON r.reported_at < TIMESTAMP(DATE_ADD(w.week_start, INTERVAL 7 DAY), 'Asia/Seoul')
)

SELECT
  week_start                                        AS metric_date,
  source, sido, school_type, grade, gender,

  -- 그 시점에 아직 안 본 건
  COUNTIF(reviewed_at IS NULL OR reviewed_at >= as_of_ts)              AS pending_count,
  -- 그 시점까지 종결된 건 (누적). 처리율의 분자·분모를 둘 다 싣는다
  COUNTIF(reviewed_at IS NOT NULL AND reviewed_at < as_of_ts)          AS closed_count,
  COUNT(*)                                                             AS reported_cumulative,

  -- 미해결의 나이 — 그 주 기준으로 다시 잰다
  COUNTIF((reviewed_at IS NULL OR reviewed_at >= as_of_ts)
          AND TIMESTAMP_DIFF(as_of_ts, reported_at, DAY) <= 3)         AS pending_le3d,
  COUNTIF((reviewed_at IS NULL OR reviewed_at >= as_of_ts)
          AND TIMESTAMP_DIFF(as_of_ts, reported_at, DAY) BETWEEN 4 AND 7) AS pending_4to7d,
  COUNTIF((reviewed_at IS NULL OR reviewed_at >= as_of_ts)
          AND TIMESTAMP_DIFF(as_of_ts, reported_at, DAY) > 7)          AS pending_gt7d,

  -- 그 주에 들어온 것 (증감을 볼 때 적체와 나란히 놓는다)
  COUNTIF(DATE_TRUNC(report_date, WEEK(MONDAY)) = week_start)          AS reported_in_week

FROM snapshot
GROUP BY metric_date, source, sido, school_type, grade, gender
