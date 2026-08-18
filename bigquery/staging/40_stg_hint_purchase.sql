-- =====================================================================
-- stg_hint_purchase · 힌트를 연 기록 1건 = 한 행
-- =====================================================================
-- ⚠️ "구매"라는 이름이 함정이다. W14 이후 **하트를 내지 않고 광고로 여는 힌트**가
--    있다(성별 힌트의 30%). `COUNT(*)` 로 구매 건수를 세면 부풀려진다 —
--    revenue 노트북이 실제로 그렇게 세고 있었다.
--
--    그래서 두 갈래를 컬럼으로 못 박는다.
--      is_paid_hint  하트를 낸 것       (heart_cost > 0)
--      is_ad_hint    광고로 연 것       (ad_impression_id IS NOT NULL)
--
--    정합성 검사 4번(원장 없는 힌트 구매)이 같은 이유로 고쳐졌다.
-- =====================================================================
CREATE OR REPLACE VIEW `{{stg}}.stg_hint_purchase` AS

SELECT
  CONCAT(h._source, '-', CAST(h.id AS STRING))                AS hint_key,
  h._source                                                   AS source,
  h.id                                                        AS hint_purchase_id,
  CONCAT(h._source, '-', CAST(h.user_id AS STRING))           AS user_key,
  CONCAT(h._source, '-', CAST(h.vote_received_id AS STRING))  AS vote_received_key,

  h.hint_type,
  h.step,
  h.char_index,
  h.heart_cost,
  h.heart_cost > 0                                            AS is_paid_hint,
  h.ad_impression_id IS NOT NULL                              AS is_ad_hint,

  h.created_at,
  DATE(h.created_at, 'Asia/Seoul')                            AS hint_date

FROM `{{raw}}.hint_purchase` AS h
WHERE h._deleted_at IS NULL
