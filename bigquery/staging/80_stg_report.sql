-- =====================================================================
-- stg_report · 신고 1건 = 한 행
-- =====================================================================
-- ⚠️ **신고는 이 서비스에서 지금 고이고 있는 곳이다.** 처리 화면이 없어서
--    PENDING 으로 쌓인다(CLAUDE.md 「비어 있는 테이블」의 `sanction` 항목).
--    그러니 이 뷰의 목적은 "얼마나 들어오나"보다 **"얼마나 안 처리되나"** 다.
--
-- 상태는 넷이 정의돼 있지만(PENDING·REVIEWING·ACTIONED·DISMISSED)
-- **실제로 쓰이는 것은 셋**이다 — REVIEWING 으로 넘기는 화면이 없기 때문이다.
--
--    PENDING    접수 = 미해결
--    ACTIONED   조치 완료
--    DISMISSED  기각
--
-- ⚠️ **에이징(며칠째 안 봤나)을 여기서 계산하지 않는다.** 뷰는 조회할 때마다
--    다시 계산되므로 "지금 기준 8,898건"이 조회 시각마다 달라진다. 언제 기준의
--    숫자인지가 화면에 남아야 하므로, 자르는 시각은 **마트가 정한다**
--    (`mart_report.as_of_date` · `mart_backlog_weekly`). 여기서는 `created_at`
--    과 `reviewed_at` 두 사실만 싣는다.
-- =====================================================================
CREATE OR REPLACE VIEW `{{stg}}.stg_report` AS

SELECT
  CONCAT(r._source, '-', CAST(r.id AS STRING))                  AS report_key,
  r._source                                                     AS source,
  r.id                                                          AS report_id,
  CONCAT(r._source, '-', CAST(r.reporter_id AS STRING))         AS reporter_key,

  -- 대상 — target_type 과 짝이 맞는 컬럼 하나만 차 있다(ck_report_target).
  -- 유저 신고만 사람에게 이어지므로 그것만 대리키로 만든다.
  r.target_type,
  IF(r.target_user_id IS NULL, NULL,
     CONCAT(r._source, '-', CAST(r.target_user_id AS STRING)))  AS target_user_key,
  r.target_question_id,
  r.target_post_id,
  r.target_comment_id,

  r.reason_code,
  rr.label                                                      AS reason_label,

  -- 상태. 분자·분모를 나눠 셀 수 있게 **비율이 아니라 플래그**로 싣는다.
  r.status,
  r.status = 'PENDING'                                          AS is_pending,
  r.status IN ('ACTIONED', 'DISMISSED')                         AS is_closed,
  r.status = 'ACTIONED'                                         AS is_actioned,

  r.reviewed_at,
  TIMESTAMP_DIFF(r.reviewed_at, r.created_at, HOUR)             AS resolution_hours,

  r.created_at                                                  AS reported_at,
  DATE(r.created_at, 'Asia/Seoul')                              AS report_date,
  DATE(r.reviewed_at, 'Asia/Seoul')                             AS reviewed_date

FROM `{{raw}}.report` AS r
-- 사유 마스터도 원천마다 한 줄씩 있다. `_source` 를 안 걸면 행이 두 배가 된다.
LEFT JOIN `{{raw}}.report_reason` AS rr
  ON rr.code = r.reason_code AND rr._source = r._source AND rr._deleted_at IS NULL
WHERE r._deleted_at IS NULL
