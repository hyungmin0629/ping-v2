-- =====================================================================
-- 70_backlog · 미처리 신고 적체 8주 (3쪽 선그래프·알림)
-- =====================================================================
-- **적체는 사건이 아니라 상태다.** "이번 주에 몇 건 들어왔나"는 접수일로 세지만
-- "이번 주 말 기준 몇 건이 밀려 있나"는 사건일 축으로 나오지 않는다.
--
-- ⚠️ **`mart_backlog_weekly` 를 쓰지 않는다.** 그 마트는 첫 신고~마지막 신고
--    사이의 주만 행을 만든다. 실유저는 신고가 3건뿐이라 8주 창에 한 주만
--    들어오고, 나머지 일곱 주가 통째로 빈다 — 선 그래프가 끊긴다.
--    `mart_report` 는 신고 1건 = 1행이라 **어느 주말 기준으로도 복원**할 수 있고,
--    정의는 그 마트와 같다(접수됐고 아직 안 봤다).
--
-- 주말 기준 시각은 다음 주 월요일 0시(KST)다 — 그 주의 마지막 순간.
-- =====================================================================
WITH weeks AS (
  SELECT
    wk,
    TIMESTAMP(DATE_ADD(wk, INTERVAL 7 DAY), 'Asia/Seoul') AS as_of
  FROM UNNEST(GENERATE_DATE_ARRAY(
    DATE_SUB(@week_start, INTERVAL 7 WEEK), @week_start, INTERVAL 1 WEEK)) AS wk
),

r AS (
  SELECT reported_at, reviewed_at, metric_date AS report_date, is_actioned
  FROM `{{mart}}.mart_report`
  WHERE source = @source
)

SELECT
  w.wk AS week_start,

  COUNTIF(r.reported_at < w.as_of
          AND (r.reviewed_at IS NULL OR r.reviewed_at >= w.as_of))          AS pending_count,

  COUNTIF(r.reported_at < w.as_of
          AND (r.reviewed_at IS NULL OR r.reviewed_at >= w.as_of)
          AND TIMESTAMP_DIFF(w.as_of, r.reported_at, DAY) > 7)              AS pending_gt7d,

  COUNTIF(DATE_TRUNC(r.report_date, WEEK(MONDAY)) = w.wk)                   AS reported_in_week,

  COUNTIF(r.reviewed_at IS NOT NULL
          AND DATE_TRUNC(DATE(r.reviewed_at, 'Asia/Seoul'), WEEK(MONDAY)) = w.wk)
                                                                            AS closed_in_week
FROM weeks AS w
LEFT JOIN r ON TRUE
GROUP BY w.wk
ORDER BY w.wk
