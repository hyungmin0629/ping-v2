-- =====================================================================
-- 01_freshness · 이 보고서가 언제까지의 데이터를 보고 있나
-- =====================================================================
-- **보고서에 반드시 실린다.** 적재가 멈춰 있어도 보고서는 예쁘게 나오기
-- 때문이다. 마지막 데이터 날짜가 보고 주간의 끝보다 이르면 머리말에
-- 경고를 띄운다(`render.py` 가 판단한다).
--
--   last_data_date  mart_daily 에 실린 마지막 날 = 적재가 여기까지 왔다
--   mart_built_on   mart_report.as_of_date = 마트를 마지막으로 구운 날
-- =====================================================================
SELECT
  (SELECT MAX(metric_date) FROM `{{mart}}.mart_daily`  WHERE source = @source) AS last_data_date,
  (SELECT MAX(as_of_date)  FROM `{{mart}}.mart_report`)                        AS mart_built_on
