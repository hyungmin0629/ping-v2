-- =====================================================================
-- 예시 · mart_user — 마트 SQL 을 이렇게 쓴다
-- =====================================================================
-- ⚠️ **이 파일은 예시다. 지표도 그레인도 확정된 것이 아니다.**
--    `_` 로 시작하는 파일은 `bigquery/build.py` 가 **건너뛴다** —
--    실수로 만들어지지 않는다. 진짜 마트를 쓸 때는 이 파일을 복사해
--    `10_mart_<이름>.sql` 처럼 번호를 붙여 저장한다(번호가 실행 순서다).
--
-- 마트 그레인은 `notebooks/dashboard.ipynb` 의 지표 12개를 보고 정한다.
-- 지금 갈래가 셋이다 — 일자 시계열 · 유저 한 명 · 퍼널 단계.
-- 절차와 남은 결정은 docs/ops/ops-p5-p7.md.
--
-- ---------------------------------------------------------------------
-- 규칙 네 가지. 어느 마트를 쓰든 이건 그대로다.
--
--   ① raw 를 직접 읽지 않는다 — 항상 `{{stg}}`. 표준 필터가 거기 들어 있다
--   ② 대리키로 잇는다 — `user_key`('local-123'). id 로 조인하면 두 원천이 섞인다
--   ③ 걸러서 담는다 — 운영자 제외 · `valid_until` 이후 활동 제외
--   ④ 날짜로 PARTITION, 원천으로 CLUSTER (이 표는 날짜 축이 없어 CLUSTER 만)
--
-- ---------------------------------------------------------------------
-- 이 표가 답하는 질문: **이 유저는 언제 들어와서, 열렸고, 첫 투표를 했나.**
-- 한 행 = 유저 한 명.
-- =====================================================================
CREATE OR REPLACE TABLE `{{mart}}.mart_user`
CLUSTER BY source AS

-- [1] 대상을 먼저 좁힌다 ------------------------------------------------
--     운영자 계정은 지표가 아니다. 여기서 한 번 빼면 아래 전부에 적용된다.
--     ⚠️ 탈퇴자는 **빼지 않는다.** 빼면 이탈률의 분자가 사라진다 —
--        플래그(is_withdrawn)로 싣고, 거를지는 보는 쪽이 고른다.
WITH users AS (
  SELECT *
  FROM `{{stg}}.stg_user`
  WHERE NOT is_admin
),

-- [2] 팩트를 유저 단위로 접는다 ------------------------------------------
--     `valid_until` 이 이 층의 핵심이다. 탈퇴·영구정지는 종점인데,
--     합성 v5 에는 제재 뒤에도 투표하는 유저가 34명 있다.
--     유저를 통째로 빼면 그 이전의 정상 활동까지 사라지므로 **시각으로 자른다.**
votes AS (
  SELECT
    v.user_key,
    MIN(v.voted_at)  AS first_vote_at,
    MAX(v.voted_at)  AS last_vote_at,
    COUNT(*)         AS vote_count
  FROM `{{stg}}.stg_vote_item` AS v
  JOIN users AS u ON u.user_key = v.user_key      -- ② 대리키로 잇는다
  WHERE v.is_voted
    AND v.voted_at < u.valid_until                -- ③ 걸러서 담는다
  GROUP BY v.user_key
),

hearts AS (
  SELECT
    t.user_key,
    SUM(t.hearts_earned) AS hearts_earned,
    SUM(t.hearts_spent)  AS hearts_spent
  FROM `{{stg}}.stg_heart_transaction` AS t
  JOIN users AS u ON u.user_key = t.user_key
  WHERE t.created_at < u.valid_until
  GROUP BY t.user_key
)

-- [3] 붙여서 낸다 --------------------------------------------------------
--     팩트가 없는 유저도 남아야 하므로 LEFT JOIN 이고,
--     "활동이 없다"는 NULL 이 아니라 0 이라 IFNULL 로 눕힌다.
SELECT
  u.user_key,
  u.source,

  -- 차원 — 대시보드에서 잘라 볼 축
  u.gender,
  u.school_name,
  u.grade,

  -- 생애 주기 — 시각(UTC)과 날짜(KST)를 나란히 둔다
  u.signed_up_at,
  u.signup_date,
  u.service_unlocked_at,
  v.first_vote_at,
  DATE(v.first_vote_at, 'Asia/Seoul')                        AS first_vote_date,
  v.last_vote_at,

  -- 퍼널 — 가입 → 해금 → 첫 투표. 대시보드에서 COUNTIF 로 바로 센다
  u.service_unlocked_at IS NOT NULL                          AS is_unlocked,
  v.first_vote_at IS NOT NULL                                AS is_activated,
  TIMESTAMP_DIFF(u.service_unlocked_at, u.signed_up_at, DAY) AS days_to_unlock,
  TIMESTAMP_DIFF(v.first_vote_at, u.signed_up_at, DAY)       AS days_to_first_vote,

  -- 이탈 — 지우지 않고 표시한다
  u.is_withdrawn,
  u.withdrawn_at,
  u.first_banned_at,

  -- 누적 활동
  IFNULL(v.vote_count, 0)                                    AS vote_count,
  u.friend_count,
  IFNULL(h.hearts_earned, 0)                                 AS hearts_earned,
  IFNULL(h.hearts_spent, 0)                                  AS hearts_spent

FROM users AS u
LEFT JOIN votes  AS v ON v.user_key = u.user_key
LEFT JOIN hearts AS h ON h.user_key = u.user_key
