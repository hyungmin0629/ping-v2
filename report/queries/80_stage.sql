-- =====================================================================
-- 80_stage · 10문항까지 간 투표 세션 (1쪽 전주 대비 막대의 마지막 칸)
-- =====================================================================
-- ⚠️ **단위가 다르다.** 1쪽의 다른 칸은 전부 사람 수인데 이것만 **세션 수**다.
--    `mart_distribution` 의 '문항 도달'이 세션 그레인이기 때문이다(누적:
--    10문항 도달 = 10문항 이상 출제된 세션). 보고서 라벨에 '(건)'을 박아
--    사람 수로 읽히지 않게 한다.
-- =====================================================================
SELECT
  DATE_TRUNC(metric_date, WEEK(MONDAY))        AS week_start,
  SUM(IF(bucket_no = 1,  value, 0))            AS sessions_started,
  SUM(IF(bucket_no = 10, value, 0))            AS sessions_10q
FROM `{{mart}}.mart_distribution`
WHERE source    = @source
  AND dist_name = '문항 도달'
  AND metric_date BETWEEN DATE_SUB(@week_start, INTERVAL 1 WEEK)
                      AND DATE_ADD(@week_start, INTERVAL 6 DAY)
GROUP BY week_start
ORDER BY week_start
