-- =====================================================================
-- 20_funnel_user · 그 주에 가입한 사람이 어디까지 갔나
-- =====================================================================
-- 날짜 축이 **가입일**이라 기간을 주로 좁히면 "금주 가입 코호트"가 된다.
--
-- ⚠️ **1~4단계만 쓴다.** 5단계 이후(힌트)는 받은 투표에서 사는 것이라
--    투표 세션과 인과가 없어 중간에 다시 늘어난다. 퍼널 도형으로 그리면
--    거짓말이 된다 — 힌트 쪽은 `30_funnel_received` 가 담당한다.
--    경위는 `bigquery/mart/40_mart_funnel_step.sql` 머리말.
-- ⚠️ 최근 코호트는 관찰기간이 짧아 뒷단계가 늘 낮다. 보고서에 주석을 단다.
-- =====================================================================
SELECT
  step_no,
  step_label,
  SUM(value) AS value,
  SUM(base)  AS base
FROM `{{mart}}.mart_funnel_step`
WHERE funnel_name = 'user_journey'
  AND source      = @source
  AND step_no    <= 4
  AND metric_date BETWEEN @week_start AND DATE_ADD(@week_start, INTERVAL 6 DAY)
GROUP BY step_no, step_label
ORDER BY step_no
