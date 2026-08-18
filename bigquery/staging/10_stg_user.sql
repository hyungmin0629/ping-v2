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

  -- 지역 — 대시보드의 시도 필터가 여기에 기댄다. 학교를 거쳐야만 닿으므로
  -- 매번 두 번 조인하게 두면 언젠가 한 곳이 빠진다. 여기서 한 번만 잇는다.
  r.sido,
  r.sigungu,

  -- ⚠️ **지도를 그리려면 이름이 아니라 코드가 필요하다.** 루커 스튜디오는 필드
  --    타입이 '지역 ID'(Region ID)일 때 ISO-3166-2 값을 받는다. 한글 정식명으로는
  --    매칭이 붙지 않고, 특히 **`강원특별자치도`처럼 최근 개편된 이름은 확실히 실패한다.**
  --    이름 매칭에 기대지 않으려고 코드를 컬럼으로 못 박는다.
  --
  --    옛 이름도 함께 받는다 — 원천이 언제 개편명으로 바뀌었는지에 이 컬럼이
  --    흔들리면 안 된다(강원도/전라북도/제주도).
  --    ⚠️ 못 알아본 값은 **NULL 로 남긴다.** 틀린 코드를 넣으면 엉뚱한 지역이
  --       칠해지고 아무도 눈치채지 못한다. NULL 은 지도에서 빠져 눈에 띈다.
  CASE r.sido
    WHEN '서울특별시'     THEN 'KR-11'
    WHEN '부산광역시'     THEN 'KR-26'
    WHEN '대구광역시'     THEN 'KR-27'
    WHEN '인천광역시'     THEN 'KR-28'
    WHEN '광주광역시'     THEN 'KR-29'
    WHEN '대전광역시'     THEN 'KR-30'
    WHEN '울산광역시'     THEN 'KR-31'
    WHEN '세종특별자치시' THEN 'KR-50'
    WHEN '경기도'         THEN 'KR-41'
    WHEN '강원특별자치도' THEN 'KR-42'
    WHEN '강원도'         THEN 'KR-42'
    WHEN '충청북도'       THEN 'KR-43'
    WHEN '충청남도'       THEN 'KR-44'
    WHEN '전북특별자치도' THEN 'KR-45'
    WHEN '전라북도'       THEN 'KR-45'
    WHEN '전라남도'       THEN 'KR-46'
    WHEN '경상북도'       THEN 'KR-47'
    WHEN '경상남도'       THEN 'KR-48'
    WHEN '제주특별자치도' THEN 'KR-49'
    WHEN '제주도'         THEN 'KR-49'
    ELSE NULL
  END                                                 AS sido_iso,

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
LEFT JOIN `{{raw}}.region` AS r
  ON r.id = s.region_id AND r._source = u._source AND r._deleted_at IS NULL
LEFT JOIN withdrawal AS w
  ON w.user_id = u.id AND w._source = u._source
LEFT JOIN sanctioned AS x
  ON x.user_id = u.id AND x._source = u._source
WHERE u._deleted_at IS NULL
