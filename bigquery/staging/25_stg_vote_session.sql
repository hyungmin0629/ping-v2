-- =====================================================================
-- stg_vote_session · 투표 세션 1건 = 한 행
-- =====================================================================
-- 한 번 앉아서 푸는 질문 묶음이다. `stg_vote_item` 이 그 안의 낱개 질문이고,
-- 둘은 `vote_session_key` 로 이어진다 — **이름을 일부러 맞췄다.**
--
-- 왜 아이템 집계로 대신하지 않는가. "10문항을 다 풀었다"를 아이템 수로 세면
-- **낸 것과 푼 것이 섞인다.** 출제는 됐지만 안 고르고 나간 아이템이 있어서다
-- (`stg_vote_item` 의 `served_at` vs `voted_at`). 세션의 `status` 는 앱이
-- 찍은 사실이라 해석의 여지가 없다. 퍼널의 '투표 세션 완료' 단계는 이것을 쓴다.
--
-- `item_count` 는 **출제 예정 수**다. 실제로 몇 개를 풀었는지는 아이템을 센다.
-- =====================================================================
CREATE OR REPLACE VIEW `{{stg}}.stg_vote_session` AS

SELECT
  CONCAT(s._source, '-', CAST(s.id AS STRING))       AS vote_session_key,
  s._source                                          AS source,
  s.id                                               AS vote_session_id,
  CONCAT(s._source, '-', CAST(s.user_id AS STRING))  AS user_key,

  s.status,
  s.status = 'COMPLETED'                             AS is_completed,
  s.item_count,

  s.started_at,
  s.completed_at,
  DATE(s.started_at, 'Asia/Seoul')                   AS session_date,
  TIMESTAMP_DIFF(s.completed_at, s.started_at, SECOND) AS duration_sec

FROM `{{raw}}.vote_session` AS s
WHERE s._deleted_at IS NULL
