-- =====================================================================
-- stg_heart_transaction · 하트 원장 1줄 = 한 행
-- =====================================================================
-- 하트는 이 서비스의 유일한 통화다. 원장은 **하트가 움직인 사실**만 적는다 —
-- 힌트를 열었다는 사실을 적는 곳이 아니다(광고 무료 힌트는 원장에 안 남는다).
--
-- delta 의 부호가 방향이다. 부호로 갈라 두 컬럼(earned/spent)을 만들어 두면
-- 대시보드에서 SUM 만 해도 적립·소비가 나온다.
-- =====================================================================
CREATE OR REPLACE VIEW `{{stg}}.stg_heart_transaction` AS

SELECT
  CONCAT(t._source, '-', CAST(t.id AS STRING))       AS heart_tx_key,
  t._source                                          AS source,
  t.id                                               AS heart_transaction_id,
  CONCAT(t._source, '-', CAST(t.user_id AS STRING))  AS user_key,

  t.type_code,
  ty.label                                           AS type_label,
  ty.is_credit,

  t.delta,
  IF(t.delta > 0,  t.delta, 0)                       AS hearts_earned,
  IF(t.delta < 0, -t.delta, 0)                       AS hearts_spent,
  t.balance_after,

  -- 무엇 때문에 움직였는지. NULL 이 아닌 것 하나만 차 있다.
  t.vote_item_id,
  t.hint_purchase_id,
  t.purchase_id,
  t.ad_impression_id,

  t.created_at,
  DATE(t.created_at, 'Asia/Seoul')                   AS tx_date

FROM `{{raw}}.heart_transaction` AS t
-- 마스터도 원천별로 한 줄씩 있다. `_source` 를 안 걸면 행이 두 배가 된다.
LEFT JOIN `{{raw}}.heart_transaction_type` AS ty
  ON ty.code = t.type_code AND ty._source = t._source AND ty._deleted_at IS NULL
WHERE t._deleted_at IS NULL
