-- =====================================================================
-- stg_user · 유저 한 명 = 한 행
-- =====================================================================
-- raw 를 그대로 읽지 못하게 만드는 것이 이 층의 목적이다.
--
--   1. 대리키(user_key)      두 원천의 id 가 실제로 겹친다(app_user 16개).
--                            `_source` 를 빠뜨린 조인을 **구조적으로** 막는다.
--   2. 표준 필터             `_deleted_at IS NULL` 을 여기서 한 번만 건다.
--   3. KST 날짜              저장은 UTC 다. 안 바꾸면 날짜가 9시간 밀린다.
--   4. 탈퇴·제재 시각        매번 조인해야 하면 언젠가 안 한다. 미리 붙인다.
--
-- ⚠️ 탈퇴자·제재자를 **여기서 지우지 않는다.** 지우면 탈퇴 분석 자체가 불가능해진다.
--    거르는 것은 mart 의 일이고, 그 기준이 valid_until 이다.
-- =====================================================================
CREATE OR REPLACE VIEW `{{stg}}.stg_user` AS

WITH withdrawal AS (
  -- 탈퇴는 종점이다 — 한 유저에 한 행이지만 방어적으로 MIN 을 쓴다.
  SELECT
    _source,
    user_id,
    MIN(created_at)         AS withdrawn_at,
    ANY_VALUE(reason_code)  AS withdrawal_reason_code
  FROM `{{raw}}.user_withdrawal`
  WHERE _deleted_at IS NULL
  GROUP BY _source, user_id
),

sanctioned AS (
  -- 제재는 종점이 아니다. 그래서 "이 사람을 빼기"가 아니라
  -- "이 시각 이후를 빼기"로 쓰려고 **시각**을 싣는다.
  SELECT
    _source,
    user_id,
    MIN(starts_at)                          AS first_sanctioned_at,
    MIN(IF(type = 'BAN', starts_at, NULL))  AS first_banned_at
  FROM `{{raw}}.sanction`
  WHERE _deleted_at IS NULL
  GROUP BY _source, user_id
)

SELECT
  CONCAT(u._source, '-', CAST(u.id AS STRING))        AS user_key,
  u._source                                           AS source,
  u.id                                                AS user_id,

  -- 속성 (닉네임·초대코드는 싣지 않는다 — 분석에 쓰이지 않고, 개인 특정에 가장 가깝다)
  u.gender,
  u.status,
  u.is_admin,
  u.is_synthetic,

  -- 소속
  CONCAT(u._source, '-', CAST(u.class_id AS STRING))  AS class_key,
  c.grade,
  c.class_num,
  c.label                                             AS class_label,
  CONCAT(u._source, '-', CAST(s.id AS STRING))        AS school_key,
  s.name_masked                                       AS school_name,
  s.school_type,

  -- 현재 상태
  u.heart_balance,
  u.friend_count,

  -- 시각 (UTC 원본 + KST 날짜를 나란히 둔다)
  u.created_at                                        AS signed_up_at,
  DATE(u.created_at, 'Asia/Seoul')                    AS signup_date,
  u.service_unlocked_at,
  DATE(u.service_unlocked_at, 'Asia/Seoul')           AS unlocked_date,
  u.last_active_at,

  -- 이탈
  w.withdrawn_at,
  w.withdrawal_reason_code,
  w.withdrawn_at IS NOT NULL                          AS is_withdrawn,
  x.first_sanctioned_at,
  x.first_banned_at,

  -- **이 시각 이후의 활동은 세지 않는다.** 탈퇴는 종점이고 영구정지도 종점이다.
  -- 합성 v5 에는 제재 뒤에도 투표하는 유저가 34명 있다 — 유저를 통째로 빼면
  -- 그 이전의 정상 활동까지 사라지므로, 유저가 아니라 **시각**으로 자른다.
  LEAST(
    IFNULL(w.withdrawn_at,  TIMESTAMP '9999-12-31'),
    IFNULL(x.first_banned_at, TIMESTAMP '9999-12-31')
  )                                                   AS valid_until

FROM `{{raw}}.app_user` AS u
LEFT JOIN `{{raw}}.grade_class` AS c
  ON c.id = u.class_id AND c._source = u._source AND c._deleted_at IS NULL
LEFT JOIN `{{raw}}.school` AS s
  ON s.id = c.school_id AND s._source = u._source AND s._deleted_at IS NULL
LEFT JOIN withdrawal AS w
  ON w.user_id = u.id AND w._source = u._source
LEFT JOIN sanctioned AS x
  ON x.user_id = u.id AND x._source = u._source
WHERE u._deleted_at IS NULL
