-- =====================================================================
-- stg_vote_item · 출제된 질문 1건 = 한 행
-- =====================================================================
-- 이 프로젝트의 중심 팩트다. 질문 마스터(24행)를 여기서 미리 붙여
-- 스코프·카테고리·민감 여부를 조인 없이 쓸 수 있게 한다.
--
-- ⚠️ 마스터 조인에도 `_source` 를 건다. question 은 full 적재라 같은 id 가
--    두 원천에 각각 한 줄씩 들어 있다 — 안 걸면 행이 두 배가 된다.
--
-- served_at 은 "냈다", voted_at 은 "실제로 골랐다"이다. **둘은 다르다** —
-- 낸 뒤 안 고르고 나간 아이템이 있다. 참여율의 분모와 분자가 여기서 갈린다.
-- =====================================================================
CREATE OR REPLACE VIEW `{{stg}}.stg_vote_item` AS

SELECT
  CONCAT(i._source, '-', CAST(i.id AS STRING))          AS item_key,
  i._source                                             AS source,
  i.id                                                  AS item_id,
  CONCAT(i._source, '-', CAST(i.session_id AS STRING))  AS vote_session_key,
  CONCAT(i._source, '-', CAST(i.user_id AS STRING))     AS user_key,

  i.question_id,
  q.text                                                AS question_text,
  q.scope                                               AS question_scope,
  qc.code                                               AS category_code,
  qc.name                                               AS category_name,
  qc.is_sensitive,

  i.candidate_scope,
  i.position,
  i.shuffle_count,
  IFNULL(i.padded_count, 0)                             AS padded_count,
  i.padded_count > 0                                    AS is_padded,

  i.served_at,
  i.voted_at,
  i.voted_at IS NOT NULL                                AS is_voted,
  DATE(i.served_at, 'Asia/Seoul')                       AS served_date,
  DATE(i.voted_at,  'Asia/Seoul')                       AS voted_date,
  TIMESTAMP_DIFF(i.voted_at, i.served_at, SECOND)       AS decide_sec

FROM `{{raw}}.vote_item` AS i
LEFT JOIN `{{raw}}.question` AS q
  ON q.id = i.question_id AND q._source = i._source AND q._deleted_at IS NULL
LEFT JOIN `{{raw}}.question_category` AS qc
  ON qc.id = q.category_id AND qc._source = q._source AND qc._deleted_at IS NULL
WHERE i._deleted_at IS NULL
