-- =====================================================================
-- mart_report · 신고 1건 = 한 행
-- =====================================================================
-- 3만 건뿐이라 **집계하지 않고 그대로 굽는다.** 미리 접으면 "유형별 미해결"과
-- "에이징"과 "주간 처리율"을 각각 다른 표로 만들어야 하는데, 원본 그레인이
-- 이 정도로 작으면 그럴 이유가 없다. 루커가 세면 된다.
--
-- ⚠️ **에이징의 기준 시각을 표에 박는다**(`as_of_date`). "7일 이상 미해결
--    8,898건"은 **언제 기준인가**에 따라 달라지는 숫자다. 뷰로 두면 조회할 때마다
--    답이 바뀌고, 화면에는 그 사실이 안 드러난다. 마트를 구운 날로 고정한다.
--
-- ⚠️ 처리율을 굽지 않는다. `is_closed` 플래그를 세는 것은 루커가 한다
--    ([[mart-grain-for-weekly-filter]] 규칙 ②).
--
-- 차원은 **신고자 소속**이다. 대상이 유저가 아닌 신고(질문·글·댓글)도 있어
-- 대상 기준으로는 차원이 빈다. "어느 학교에서 신고가 나오나"가 물음이라
-- 신고자 쪽이 맞기도 하다.
-- =====================================================================
CREATE OR REPLACE TABLE `{{mart}}.mart_report`
PARTITION BY metric_date
CLUSTER BY source, status AS

WITH users AS (
  SELECT * FROM `{{stg}}.stg_user` WHERE NOT is_admin
),

asof AS (SELECT CURRENT_DATE('Asia/Seoul') AS as_of_date)

SELECT
  r.report_key,
  r.report_date                                             AS metric_date,

  u.source, u.sido, u.school_type, u.grade, u.gender,

  r.reason_code,
  r.reason_label,
  r.target_type,
  r.status,
  r.is_pending,
  r.is_closed,
  r.is_actioned,

  r.reported_at,
  r.reviewed_at,
  r.reviewed_date,
  r.resolution_hours,

  a.as_of_date,
  -- 미해결인 것만 나이를 갖는다. 처리된 건의 '나이'는 처리까지 걸린 시간이고
  -- 그건 resolution_hours 가 이미 답한다.
  IF(r.is_pending, DATE_DIFF(a.as_of_date, r.report_date, DAY), NULL) AS pending_days,
  CASE
    WHEN NOT r.is_pending THEN NULL
    WHEN DATE_DIFF(a.as_of_date, r.report_date, DAY) <= 3 THEN '3일 이내'
    WHEN DATE_DIFF(a.as_of_date, r.report_date, DAY) <= 7 THEN '4–7일'
    ELSE '7일 초과'
  END                                                       AS pending_bucket

FROM `{{stg}}.stg_report` AS r
JOIN users AS u ON u.user_key = r.reporter_key
CROSS JOIN asof AS a
WHERE r.reported_at < u.valid_until
