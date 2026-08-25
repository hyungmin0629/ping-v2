-- =====================================================================
-- 40_cohort · 첫 투표 코호트의 주차별 재투표 (2쪽 표)
-- =====================================================================
-- **가입 코호트가 아니라 첫 투표 코호트다.** 투표는 친구 5명이 있어야 열려서
-- 가입일과 시작점이 다르다. "핵심 행동을 한 날"을 W0 로 잡는 쪽이 리텐션의
-- 뜻에 맞는다.
--
-- 관찰 기간이 안 지난 칸은 **여기서 지우지 않는다** — 파이썬이 보고 주간의
-- 끝과 견줘 회색으로 칠한다. SQL 이 지우면 "0명"과 "아직 모른다"가 구별되지
-- 않는다.
--
-- ⚠️ 마지막 5개 코호트만 본다. 그보다 옛 코호트는 주간 보고서가 볼 대상이
--    아니고, 루커의 코호트 화면이 담당한다.
-- =====================================================================
WITH cohort AS (
  SELECT
    user_key,
    DATE_TRUNC(first_vote_date, WEEK(MONDAY)) AS cohort_week
  FROM `{{mart}}.mart_user`
  WHERE source = @source
    AND first_vote_date IS NOT NULL
    AND DATE_TRUNC(first_vote_date, WEEK(MONDAY))
        BETWEEN DATE_SUB(@week_start, INTERVAL 4 WEEK) AND @week_start
),

size AS (
  SELECT cohort_week, COUNT(*) AS cohort_size
  FROM cohort GROUP BY cohort_week
),

ret AS (
  SELECT
    c.cohort_week,
    DATE_DIFF(DATE_TRUNC(a.metric_date, WEEK(MONDAY)), c.cohort_week, WEEK) AS week_no,
    COUNT(DISTINCT a.user_key)                                              AS voters
  FROM cohort AS c
  JOIN `{{mart}}.mart_user_activity` AS a
    ON a.user_key = c.user_key
  WHERE a.source = @source
    AND a.is_voter
    AND a.metric_date >= c.cohort_week
    AND a.metric_date <= DATE_ADD(@week_start, INTERVAL 6 DAY)
  GROUP BY c.cohort_week, week_no
)

SELECT
  s.cohort_week,
  s.cohort_size,
  r.week_no,
  r.voters
FROM size AS s
LEFT JOIN ret AS r ON r.cohort_week = s.cohort_week
WHERE r.week_no IS NULL OR r.week_no BETWEEN 0 AND 4
ORDER BY s.cohort_week, r.week_no
