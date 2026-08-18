-- =====================================================================
-- stg_friend_edge · 친구 관계를 **유저 관점**으로 편다 (관계 1건 = 두 행)
-- =====================================================================
-- `friendship` 은 관계 하나를 한 줄로 적고, 두 사람을 `user_low_id < user_high_id`
-- 로 **정렬해서** 넣는다(`db/ddl/20_social.sql` 의 ck_friendship_order).
-- 저장에는 좋지만 분석에는 함정이다 — `user_low_id` 만 세면 **친구 수가 절반이 된다.**
-- id 가 작은 사람에게만 친구가 있는 것처럼 보이고, 오류는 나지 않는다.
--
-- 그래서 여기서 뒤집어 붙여 **"내 친구가 누구인가"** 그레인으로 만든다.
-- 이름이 `friendship` 이 아니라 `friend_edge` 인 것이 그 뜻이다 —
-- 한 행은 관계가 아니라 **한 사람이 본 관계**다. 관계 수를 세려면 2로 나눈다.
--
-- ⚠️ **끊긴 관계를 지우지 않는다.** 끊었다는 사실이 관계 이탈 신호이고
--    ([[friendship-ended-at]]), "가입 7일 내에 몇 명을 맺었나" 같은 물음은
--    지금 살아 있는지와 무관하다. `is_active` 로 표시만 한다.
--
-- ⚠️ **이름 충돌.** `friendship` 에는 이미 `source` 컬럼이 있다(어떻게 맺어졌나 —
--    INVITE_CODE·SEARCH·RECOMMEND). 적재 원천 `_source` 를 `source` 로 싣는
--    관례와 부딪히므로 관계 출처는 `relation_source` 로 이름을 바꿔 싣는다.
-- =====================================================================
CREATE OR REPLACE VIEW `{{stg}}.stg_friend_edge` AS

WITH both_ways AS (
  -- 낮은 id 쪽에서 본 관계
  SELECT
    f._source, f.id, f.source AS relation_source, f.created_at, f.ended_at,
    f.user_low_id  AS user_id,
    f.user_high_id AS friend_id,
    'LOW'          AS side
  FROM `{{raw}}.friendship` AS f
  WHERE f._deleted_at IS NULL

  UNION ALL

  -- 높은 id 쪽에서 본 같은 관계
  SELECT
    f._source, f.id, f.source AS relation_source, f.created_at, f.ended_at,
    f.user_high_id AS user_id,
    f.user_low_id  AS friend_id,
    'HIGH'         AS side
  FROM `{{raw}}.friendship` AS f
  WHERE f._deleted_at IS NULL
)

SELECT
  -- 같은 관계가 두 행이므로 관계 id 만으로는 키가 안 된다. 방향을 붙인다.
  CONCAT(e._source, '-', CAST(e.id AS STRING), '-', e.side)  AS edge_key,
  e._source                                                  AS source,
  e.id                                                       AS friendship_id,
  CONCAT(e._source, '-', CAST(e.user_id AS STRING))          AS user_key,
  CONCAT(e._source, '-', CAST(e.friend_id AS STRING))        AS friend_key,

  e.relation_source,

  e.created_at                                               AS friended_at,
  DATE(e.created_at, 'Asia/Seoul')                           AS friended_date,
  e.ended_at,
  DATE(e.ended_at, 'Asia/Seoul')                             AS ended_date,
  e.ended_at IS NULL                                         AS is_active

FROM both_ways AS e
