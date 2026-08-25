-- =====================================================================
-- 50_segments · 세그먼트별 투표 참여율 (2쪽 막대)
-- =====================================================================
-- 전체 참여율과 같은 정의를 **차원별로** 다시 센다 —
-- 분모는 그 주 끝 기준 친구 5명 확보자, 분자는 그중 투표한 사람.
--
-- 한 사람은 학교급·학년 조합 하나에만 속하므로 차원 축으로는 더해도 된다.
-- ⚠️ 차원의 값이 하나뿐이면(실유저는 지금 전원 고등학교다) 그 축은 그리지
--    않는다 — 판단은 파이썬이 한다. 값이 하나인 막대는 정보가 0이다.
-- =====================================================================
WITH elig AS (
  SELECT user_key, school_type, grade
  FROM `{{mart}}.mart_user`
  WHERE source = @source
    AND f2_five_friends
    AND metric_date <= DATE_ADD(@week_start, INTERVAL 6 DAY)
),

voted AS (
  SELECT DISTINCT a.user_key
  FROM `{{mart}}.mart_user_activity` AS a
  WHERE a.source = @source AND a.is_voter
    AND a.metric_date BETWEEN @week_start AND DATE_ADD(@week_start, INTERVAL 6 DAY)
)

SELECT 'school_type' AS dim,
       CASE e.school_type WHEN 'HIGH' THEN '고등학교' WHEN 'MIDDLE' THEN '중학교'
                          ELSE IFNULL(e.school_type, '미상') END AS label,
       COUNT(*)                                    AS eligible,
       COUNTIF(v.user_key IS NOT NULL)             AS voters
FROM elig AS e LEFT JOIN voted AS v ON v.user_key = e.user_key
GROUP BY dim, label

UNION ALL

SELECT 'grade',
       CONCAT(CAST(e.grade AS STRING), '학년'),
       COUNT(*),
       COUNTIF(v.user_key IS NOT NULL)
FROM elig AS e LEFT JOIN voted AS v ON v.user_key = e.user_key
WHERE e.grade IS NOT NULL
GROUP BY 1, 2
ORDER BY dim, label
