-- =====================================================================
-- stg_user_session · 접속 세션 한 건 = 한 행
-- =====================================================================
-- 체류시간을 여기서 한 번만 계산한다. 쿼리마다 TIMESTAMP_DIFF 를 다시 쓰면
-- 언젠가 단위(초/분)를 섞는다.
--
-- ⚠️ 합성 v5 에는 **중복 로그가 0.4%** 있다(같은 유저·같은 시각에 두 줄).
--    일부러 남긴 노이즈다 — 정제 연습이 되라고 넣었다. 여기서 지우지 않고
--    `is_duplicate` 로 **표시만** 한다. 지우면 "정제 연습"이 사라지고,
--    표시하지 않으면 체류시간이 부풀려진다.
-- =====================================================================
CREATE OR REPLACE VIEW `{{stg}}.stg_user_session` AS

SELECT
  CONCAT(s._source, '-', CAST(s.id AS STRING))       AS session_key,
  s._source                                          AS source,
  s.id                                               AS session_id,
  CONCAT(s._source, '-', CAST(s.user_id AS STRING))  AS user_key,

  s.platform,
  s.app_version,
  s.device_id,

  s.started_at,
  s.ended_at,
  DATE(s.started_at, 'Asia/Seoul')                   AS session_date,
  EXTRACT(HOUR FROM s.started_at AT TIME ZONE 'Asia/Seoul') AS session_hour_kst,
  TIMESTAMP_DIFF(s.ended_at, s.started_at, SECOND)   AS duration_sec,

  -- 같은 유저·같은 시작 시각이 두 번 이상 나오면 두 번째부터 중복으로 본다.
  ROW_NUMBER() OVER (
    PARTITION BY s._source, s.user_id, s.started_at ORDER BY s.id
  ) > 1                                              AS is_duplicate

FROM `{{raw}}.user_session` AS s
WHERE s._deleted_at IS NULL
