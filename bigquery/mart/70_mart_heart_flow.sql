-- =====================================================================
-- mart_heart_flow · 하루 × 하트 유형 × 차원 = 한 행
-- =====================================================================
-- 하트가 **어디서 들어와 어디로 나가는가.** 원장(`heart_transaction`)이 진실이고,
-- 유형 코드가 곧 유입·소비의 이름이다.
--
--   들어오는 것  SIGNUP_GRANT · VOTE_REWARD · AD_REWARD · TOPUP · EVENT_GRANT · ADMIN_ADJUST
--   나가는 것    HINT_PURCHASE · VOTE_REPLY(답장, 마이그레이션 008) · REFUND
--
-- ⚠️ **힌트는 종류까지 쪼갠다.** '힌트 구매' 한 줄로는 4쪽의 소비처 막대를 못 그린다
--    (초성·중성·종성·반·성별·이름 공개가 각각 다른 값이다). 원장의
--    `hint_purchase_id` 로 이어 붙인다.
--
-- ⚠️ **광고로 연 무료 힌트는 여기에 없다.** 하트가 움직이지 않았기 때문이다 —
--    원장은 하트의 움직임을 적는 곳이지 힌트를 연 사실을 적는 곳이 아니다.
--    그 수를 보려면 `mart_distribution` 의 '힌트 종류' 를 본다.
-- =====================================================================
CREATE OR REPLACE TABLE `{{mart}}.mart_heart_flow`
PARTITION BY metric_date
CLUSTER BY source, type_code AS

WITH users AS (
  SELECT * FROM `{{stg}}.stg_user` WHERE NOT is_admin
)

SELECT
  t.tx_date                                   AS metric_date,
  u.source, u.sido, u.school_type, u.grade, u.gender,

  t.type_code,
  t.type_label,
  t.is_credit,

  -- 힌트일 때만 채워진다. 소비처 막대가 이 컬럼으로 갈린다.
  h.hint_type,
  CASE h.hint_type
    WHEN 'GENDER' THEN '힌트 · 성별'   WHEN 'INITIAL' THEN '힌트 · 초성'
    WHEN 'MEDIAL' THEN '힌트 · 중성'   WHEN 'FINAL'   THEN '힌트 · 종성'
    WHEN 'CLASS'  THEN '힌트 · 반'     WHEN 'FULL_NAME' THEN '힌트 · 이름 공개'
    ELSE t.type_label
  END                                         AS flow_label,

  SUM(t.hearts_earned)                        AS hearts_earned,
  SUM(t.hearts_spent)                         AS hearts_spent,
  COUNT(*)                                    AS tx_count

FROM `{{stg}}.stg_heart_transaction` AS t
JOIN users AS u ON u.user_key = t.user_key
LEFT JOIN `{{stg}}.stg_hint_purchase` AS h
  ON h.hint_purchase_id = t.hint_purchase_id AND h.source = t.source
WHERE t.created_at < u.valid_until
GROUP BY metric_date, source, sido, school_type, grade, gender,
         type_code, type_label, is_credit, hint_type, flow_label

-- ⚠️ **사람 수를 여기 두지 않았다.** "하트를 쓴 사람 수"를 칸마다 미리 세면
--    날짜·유형을 걸쳐 합칠 때 같은 사람이 여러 번 세어진다. 기간을 걸친 사람
--    수는 `mart_user_activity` 에서 센다([[mart-grain-for-weekly-filter]] 규칙 ③).
