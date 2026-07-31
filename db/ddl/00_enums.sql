-- =====================================================================
-- 00_enums.sql · 열거 타입 정의
-- =====================================================================
-- 구 스키마는 상태 코드를 varchar(1~3)로 두어 DB 차원 제약이 없었고,
-- 그 결과 '기타 이유'와 '기타'가 별도 값으로 쌓이는 오염이 발생했다.
-- 여기서는 Postgres 네이티브 ENUM으로 허용값을 고정한다.
-- 값 추가는 ALTER TYPE ... ADD VALUE 로 가능하다.
-- =====================================================================

-- 조직 ---------------------------------------------------------------
CREATE TYPE school_type      AS ENUM ('MIDDLE', 'HIGH');

-- 유저 ---------------------------------------------------------------
CREATE TYPE gender_type      AS ENUM ('F', 'M', 'X');
CREATE TYPE user_status      AS ENUM ('ACTIVE', 'SUSPENDED', 'WITHDRAWN');
CREATE TYPE platform_type    AS ENUM ('IOS', 'ANDROID', 'WEB');

-- 소셜 ---------------------------------------------------------------
-- INVITE_CODE 가 MVP의 유일한 친구 추가 경로다.
-- CONTACT_SYNC 는 연락처(전화번호)를 받아야 하므로 MVP에서 사용하지 않는다.
CREATE TYPE friend_req_status AS ENUM ('PENDING', 'ACCEPTED', 'REJECTED', 'CANCELLED');
CREATE TYPE relation_source   AS ENUM ('INVITE_CODE', 'SEARCH', 'CONTACT_SYNC', 'RECOMMEND');
CREATE TYPE recommend_reason  AS ENUM ('MUTUAL_CONTACT', 'MUTUAL_FRIEND', 'SAME_CLASS', 'SAME_SCHOOL');
CREATE TYPE block_reason      AS ENUM ('UNKNOWN_PERSON', 'AWKWARD', 'IMPERSONATION', 'IRRELEVANT', 'TOO_MANY');

-- 질문 / 투표 ---------------------------------------------------------
-- 세 스코프 모두 "친구" 안에서의 범위다. GLOBAL도 모르는 사람이 아니라 친구 전체를 뜻한다.
CREATE TYPE question_scope   AS ENUM ('CLASS', 'SCHOOL', 'GLOBAL');
CREATE TYPE question_status  AS ENUM ('ACTIVE', 'PAUSED', 'RETIRED');
CREATE TYPE question_source  AS ENUM ('OFFICIAL', 'USER_SUBMITTED');
CREATE TYPE request_status   AS ENUM ('PENDING', 'APPROVED', 'REJECTED');
CREATE TYPE session_status   AS ENUM ('IN_PROGRESS', 'COMPLETED', 'EXPIRED');
CREATE TYPE reveal_status    AS ENUM ('HIDDEN', 'PARTIAL', 'REVEALED');
CREATE TYPE answer_status    AS ENUM ('NONE', 'PUBLIC', 'PRIVATE');
CREATE TYPE hint_type        AS ENUM ('INITIAL', 'GENDER', 'CLASS', 'FULL_NAME');

-- 광고 ---------------------------------------------------------------
CREATE TYPE ad_placement     AS ENUM ('VOTE_SHUFFLE', 'HEART_REWARD');
CREATE TYPE ad_status        AS ENUM ('STARTED', 'COMPLETED', 'ABANDONED', 'FAILED');

-- 결제 ---------------------------------------------------------------
-- 구 스키마는 성공/실패 테이블이 분리돼 있었고 실패 로깅이 2023-09에 조용히 끊겼다.
-- 하나의 테이블에 status로 통합해 실패율이 항상 계산되게 한다.
CREATE TYPE purchase_status  AS ENUM ('PENDING', 'SUCCESS', 'FAILED', 'REFUNDED');

-- 신고 / 제재 ---------------------------------------------------------
CREATE TYPE report_target    AS ENUM ('USER', 'QUESTION', 'POST', 'COMMENT');
CREATE TYPE report_status    AS ENUM ('PENDING', 'REVIEWING', 'ACTIONED', 'DISMISSED');
CREATE TYPE sanction_type    AS ENUM ('WARNING', 'MUTE', 'SUSPEND', 'BAN');

-- 학교 부가 서비스 -----------------------------------------------------
CREATE TYPE data_source      AS ENUM ('NEIS', 'MANUAL');
CREATE TYPE meal_type        AS ENUM ('BREAKFAST', 'LUNCH', 'DINNER');
CREATE TYPE school_event_type AS ENUM ('HOLIDAY', 'EXAM', 'CEREMONY', 'FIELD_TRIP', 'ETC');
CREATE TYPE sync_resource    AS ENUM ('MEAL', 'TIMETABLE', 'EVENT', 'NOTICE');
CREATE TYPE sync_status      AS ENUM ('SUCCESS', 'PARTIAL', 'FAILED');

-- 게시판 ---------------------------------------------------------------
CREATE TYPE content_status   AS ENUM ('PUBLISHED', 'HIDDEN', 'DELETED');
