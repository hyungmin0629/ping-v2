-- =====================================================================
-- 30_funnel_received · 그 주에 받은 투표가 이름 공개까지 갔나
-- =====================================================================
-- 단위가 **건**이다(수신 1건이 한 행). 수신 건 하나를 따라가므로
-- 단조 감소가 성립한다 — 퍼널 도형으로 그려도 되는 쪽이다.
-- 날짜 축은 수신일이라 기간 필터의 뜻은 "그 주에 받은 투표"다.
-- =====================================================================
SELECT
  step_no,
  step_label,
  SUM(value) AS value,
  SUM(base)  AS base
FROM `{{mart}}.mart_funnel_step`
WHERE funnel_name = 'vote_received'
  AND source      = @source
  AND metric_date BETWEEN @week_start AND DATE_ADD(@week_start, INTERVAL 6 DAY)
GROUP BY step_no, step_label
ORDER BY step_no
