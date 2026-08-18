-- =====================================================================
-- stg_vote_received · 받은 투표 1건 = 한 행
-- =====================================================================
-- 이 서비스의 수익 구조가 얹혀 있는 표다. 받은 투표를 **열고**(is_read),
-- 힌트를 사고, 끝내 **이름을 공개**(reveal_status)하는 흐름이 전부 여기 있다.
--
-- ⚠️ **`voter_id`("누가 나를 뽑았나")를 싣지 않는다.** 앱에서 하트를 받고 파는
--    유료 정보라 직접 접근을 막고 `my_vote_received` 뷰로만 노출한다
--    (CLAUDE.md 보안 원칙). `stg_user` 가 닉네임·초대코드를 뺀 것과 같은 기준이고,
--    대시보드도 쓰지 않는다. 필요해지면 `item_key` 로 `stg_vote_item` 에 이어
--    그때 연다 — 기본으로 열어두지 않는다.
--
-- reveal_status 는 세 값이다.
--    HIDDEN    아직 아무것도 안 열었다
--    PARTIAL   힌트를 샀다 (초성·중성·종성·성별·반)
--    REVEALED  이름 공개까지 샀다 — 100하트짜리 마지막 단계
--
-- ⚠️ **그런데 이름 공개를 이 컬럼으로 세면 안 된다.** 합성 v5 에는 REVEALED 가
--    **한 건도 없다**(2026-08-18 실측: local 0건 · supabase 10건). 그러면서
--    `hint_purchase` 에는 FULL_NAME 구매가 8,411건(4,921명) 들어 있다 —
--    **생성기가 이름 공개 힌트를 팔면서 이 컬럼을 갱신하지 않는다.** 앱은 갱신한다
--    (실유저는 REVEALED 10건 = FULL_NAME 구매 10건으로 정확히 맞는다).
--    CLAUDE.md 가 적어 둔 「앱과 생성기가 어긋난 곳」의 세 번째다.
--
--    → **이름 공개는 `stg_hint_purchase.hint_type = 'FULL_NAME'` 으로 센다.**
--       `is_name_revealed` 는 사실 그대로 싣되 퍼널에는 쓰지 않는다.
--
-- `hours_to_read` 는 "받고 나서 얼마 만에 열었나"다. 열람 자체가 유료 행동의
-- 입구라 3쪽의 지연 분포가 여기서 나온다.
-- =====================================================================
CREATE OR REPLACE VIEW `{{stg}}.stg_vote_received` AS

SELECT
  CONCAT(r._source, '-', CAST(r.id AS STRING))               AS vote_received_key,
  r._source                                                  AS source,
  r.id                                                       AS vote_received_id,
  CONCAT(r._source, '-', CAST(r.vote_item_id AS STRING))     AS item_key,
  CONCAT(r._source, '-', CAST(r.receiver_id AS STRING))      AS receiver_key,

  r.question_id,
  q.text                                                     AS question_text,
  q.scope                                                    AS question_scope,
  qc.code                                                    AS category_code,
  qc.is_sensitive,

  -- 열람
  r.is_read,
  r.read_at,
  DATE(r.read_at, 'Asia/Seoul')                              AS read_date,
  TIMESTAMP_DIFF(r.read_at, r.created_at, HOUR)              AS hours_to_read,

  -- 공개 단계
  r.reveal_status,
  r.reveal_status = 'REVEALED'                               AS is_name_revealed,

  -- 답장 (마이그레이션 008 이 연 하트 소비처. NONE 이면 답장하지 않았다)
  r.answer_status,
  r.answer_status <> 'NONE'                                  AS is_answered,
  r.answered_at,

  r.created_at                                               AS received_at,
  DATE(r.created_at, 'Asia/Seoul')                           AS received_date

FROM `{{raw}}.vote_received` AS r
-- 질문 마스터는 full 적재라 같은 id 가 원천마다 한 줄씩 있다. `_source` 를
-- 안 걸면 행이 두 배가 된다 — `stg_vote_item` 과 같은 함정이다.
LEFT JOIN `{{raw}}.question` AS q
  ON q.id = r.question_id AND q._source = r._source AND q._deleted_at IS NULL
LEFT JOIN `{{raw}}.question_category` AS qc
  ON qc.id = q.category_id AND qc._source = q._source AND qc._deleted_at IS NULL
WHERE r._deleted_at IS NULL
