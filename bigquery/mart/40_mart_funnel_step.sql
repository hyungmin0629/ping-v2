-- =====================================================================
-- mart_funnel_step · 퍼널 × 단계 × 차원 × 날짜 = 한 행
-- =====================================================================
-- 퍼널이 둘이고 **세는 단위가 다르다.** 한 표에 담되 `unit` 으로 가른다.
--
--   user_journey    단위 users   가입 → 친구5 → 투표 → 세션완료 → 힌트1·2·3 → 이름공개
--   vote_received   단위 events  수신 → 열람 → 힌트1 → 힌트2 → 힌트3 → 이름공개
--
-- **날짜 축은 '그 행이 태어난 날'이다** — 유저 퍼널은 가입일, 수신 퍼널은 수신일.
-- 그래야 기간을 주로 좁혀도 같은 대상이 두 주에 걸쳐 중복되지 않는다
-- ([[mart-grain-for-weekly-filter]] 규칙 ④). 기간 필터의 뜻은 이렇게 된다 —
-- **"그 주에 가입한 사람이 어디까지 갔나" · "그 주에 받은 투표가 어디까지 갔나".**
--
-- ⚠️ 최근 코호트는 관찰기간이 짧아 뒷단계가 늘 낮다. 화면에 주석을 단다.
-- ⚠️ **비율을 담지 않는다.** 단계별 값만 싣고 나누는 것은 루커가 한다(규칙 ②).
--
-- ⚠️ **user_journey 의 단계는 독립 플래그다 — 누적 조건부가 아니다.**
--    각 값은 "앞 단계를 통과한 사람 중"이 아니라 **"그 일을 해본 사람 수"** 다.
--    그래서 중간에서 **다시 늘어난다**(2026-08-18 실측):
--
--        투표 세션 완료 13,873  →  1단계 힌트 15,210
--
--    버그가 아니다. **힌트는 받은 투표에서 사는 것이라 투표 세션과 인과가 없다** —
--    한 번도 세션을 끝내지 않고도 남이 나를 뽑은 것을 열어 힌트를 살 수 있다.
--    누적 조건부로 강제하면(`f5 AND f4`) 그 사람들이 통째로 사라져 지표가 왜곡된다.
--
--    → **화면에서 퍼널 모양으로 그리지 않는다.** 단조 감소를 전제한 퍼널 도형은
--       이 값을 오해하게 만든다. **막대 묶음**으로 그리고 "각 단계 도달자 수"라고
--       적는다. `vote_received` 퍼널은 수신 건 하나를 따라가므로 단조 감소가 맞다.
--
-- ⚠️ 이름 공개는 `hint_type = 'FULL_NAME'` 으로 센다. `reveal_status` 는 합성
--    v5 에서 갱신되지 않는다 — [[synthetic-reveal-status-not-updated]].
-- =====================================================================
CREATE OR REPLACE TABLE `{{mart}}.mart_funnel_step`
PARTITION BY metric_date
CLUSTER BY funnel_name, source AS

WITH users AS (
  SELECT * FROM `{{stg}}.stg_user` WHERE NOT is_admin
),

-- [A] 유저 퍼널 --------------------------------------------------------
--     `mart_user` 가 이미 플래그 여덟 개를 갖고 있다. 같은 정의를 여기서 다시
--     쓰면 언젠가 둘이 갈라지므로 **읽어서 편다**(2.4만 행이라 비용도 없다).
--     번호가 실행 순서라 10번이 먼저 만들어져 있다.
user_steps AS (
  SELECT
    'user_journey'                                   AS funnel_name,
    'users'                                          AS unit,
    m.metric_date, m.source, m.sido, m.school_type, m.grade, m.gender,
    s.step_no, s.step_label, s.hit
  FROM `{{mart}}.mart_user` AS m
  CROSS JOIN UNNEST([
    STRUCT(1 AS step_no, '가입 완료'        AS step_label, m.f1_signed_up        AS hit),
    STRUCT(2, '친구 5명 확보',   m.f2_five_friends),
    STRUCT(3, '투표 시작',       m.f3_voted),
    STRUCT(4, '투표 세션 완료',  m.f4_session_completed),
    STRUCT(5, '1단계 힌트 구매', m.f5_hint1),
    STRUCT(6, '2단계 힌트 구매', m.f6_hint2),
    STRUCT(7, '3단계 힌트 구매', m.f7_hint3),
    STRUCT(8, '이름 공개 구매',  m.f8_name_revealed)
  ]) AS s
),

-- [B] 수신 투표 퍼널 ---------------------------------------------------
recv AS (
  SELECT
    r.vote_received_key, r.received_date, r.is_read, r.read_at,
    u.source, u.sido, u.school_type, u.grade, u.gender
  FROM `{{stg}}.stg_vote_received` AS r
  JOIN users AS u ON u.user_key = r.receiver_key
  WHERE r.received_at < u.valid_until
),

-- 힌트는 **열람 후 24시간 안에 산 것만** 그 수신 건의 것으로 본다.
-- 며칠 뒤에 산 힌트를 같은 건으로 묶으면 "열어 보고 샀다"는 인과가 흐려진다.
hint_per_received AS (
  SELECT
    h.vote_received_key,
    COUNT(DISTINCT IF(h.hint_type <> 'FULL_NAME', h.hint_type, NULL)) AS basic_types,
    COUNTIF(h.hint_type = 'FULL_NAME') > 0                            AS got_full_name
  FROM `{{stg}}.stg_hint_purchase` AS h
  JOIN recv AS r ON r.vote_received_key = h.vote_received_key
  WHERE r.read_at IS NOT NULL
    AND h.created_at >= r.read_at
    AND h.created_at <  TIMESTAMP_ADD(r.read_at, INTERVAL 24 HOUR)
  GROUP BY h.vote_received_key
),

received_steps AS (
  SELECT
    'vote_received'                                  AS funnel_name,
    'events'                                         AS unit,
    r.received_date                                  AS metric_date,
    r.source, r.sido, r.school_type, r.grade, r.gender,
    s.step_no, s.step_label, s.hit
  FROM recv AS r
  LEFT JOIN hint_per_received AS h ON h.vote_received_key = r.vote_received_key
  CROSS JOIN UNNEST([
    STRUCT(1 AS step_no, '투표 수신'      AS step_label, TRUE AS hit),
    STRUCT(2, '수신 투표 열람', r.is_read),
    STRUCT(3, '힌트 1개',      IFNULL(h.basic_types, 0) >= 1),
    STRUCT(4, '힌트 2개',      IFNULL(h.basic_types, 0) >= 2),
    STRUCT(5, '힌트 3개',      IFNULL(h.basic_types, 0) >= 3),
    STRUCT(6, '이름 공개',     IFNULL(h.basic_types, 0) >= 3 AND IFNULL(h.got_full_name, FALSE))
  ]) AS s
),

both AS (
  SELECT * FROM user_steps
  UNION ALL
  SELECT * FROM received_steps
)

SELECT
  funnel_name,
  unit,
  step_no,
  step_label,
  metric_date,
  source, sido, school_type, grade, gender,
  COUNTIF(hit)  AS value,   -- 그 단계에 도달한 수
  COUNT(*)      AS base     -- 같은 칸의 모수. 비율은 보는 쪽이 만든다
FROM both
WHERE metric_date IS NOT NULL
GROUP BY funnel_name, unit, step_no, step_label, metric_date,
         source, sido, school_type, grade, gender
