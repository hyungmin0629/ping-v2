-- =====================================================================
-- 60_heart_flow · 금주 하트가 어디서 들어와 어디로 나갔나 (3쪽 막대)
-- =====================================================================
-- 원장(`heart_transaction`)이 진실이다. 유형 코드가 곧 유입·소비의 이름이고
-- 힌트는 종류까지 쪼개져 있다.
--
-- ⚠️ **광고로 연 무료 힌트는 여기 없다.** 하트가 움직이지 않았기 때문이다.
--    그 수는 `10_weekly_core` 의 `hints_by_ad` 로 따로 싣는다.
-- ⚠️ **'하트 충전'은 매출이 아니다.** MVP 의 충전 버튼은 스텁이라 하트만
--    들어오고 돈은 오지 않는다. 3쪽에서 매출과 나란히 놓지 않는다.
-- =====================================================================
SELECT
  is_credit,
  flow_label,
  SUM(hearts_earned) AS hearts_earned,
  SUM(hearts_spent)  AS hearts_spent,
  SUM(tx_count)      AS tx_count
FROM `{{mart}}.mart_heart_flow`
WHERE source = @source
  AND metric_date BETWEEN @week_start AND DATE_ADD(@week_start, INTERVAL 6 DAY)
GROUP BY is_credit, flow_label
HAVING hearts_earned > 0 OR hearts_spent > 0
ORDER BY is_credit DESC, GREATEST(hearts_earned, hearts_spent) DESC
