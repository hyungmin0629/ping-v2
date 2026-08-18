-- =====================================================================
-- stg_heart_purchase · 충전 결제 시도 1건 = 한 행
-- =====================================================================
-- ⚠️ **MVP 의 충전은 결제가 아니다.** W13 의 충전 버튼은 스텁이라 돈이 오가지
--    않는다. 그 행은 `store_transaction_id` 가 `MVP-STUB-` 로 시작한다.
--    매출을 셀 때 반드시 걸러야 하는데, 쿼리마다 기억해서 거르게 두면
--    언젠가 한 곳이 빠진다. 여기서 컬럼으로 못 박는다.
--
--    is_stub      결제 없이 들어온 것 (매출 아님)
--    is_revenue   성공했고 스텁이 아닌 것 — **이것만 매출이다**
-- =====================================================================
CREATE OR REPLACE VIEW `{{stg}}.stg_heart_purchase` AS

SELECT
  CONCAT(p._source, '-', CAST(p.id AS STRING))         AS purchase_key,
  p._source                                            AS source,
  p.id                                                 AS heart_purchase_id,
  CONCAT(p._source, '-', CAST(p.user_id AS STRING))    AS user_key,

  p.product_id,
  hp.product_code,
  hp.label                                             AS product_label,
  p.platform,
  p.status,
  p.failure_reason,
  p.price_krw,
  p.heart_amount,

  STARTS_WITH(IFNULL(p.store_transaction_id, ''), 'MVP-STUB-')  AS is_stub,
  p.status = 'SUCCESS'                                          AS is_success,
  p.status = 'SUCCESS'
    AND NOT STARTS_WITH(IFNULL(p.store_transaction_id, ''), 'MVP-STUB-') AS is_revenue,

  p.created_at,
  p.completed_at,
  DATE(p.created_at, 'Asia/Seoul')                     AS purchase_date

FROM `{{raw}}.heart_purchase` AS p
LEFT JOIN `{{raw}}.heart_product` AS hp
  ON hp.id = p.product_id AND hp._source = p._source AND hp._deleted_at IS NULL
WHERE p._deleted_at IS NULL
