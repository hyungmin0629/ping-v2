-- =====================================================================
-- seed_org.sql · 클로즈드 테스트용 조직 데이터
-- =====================================================================
-- ⚠️ 임시 데이터다. NEIS 연동(P3) 후 실제 학교 목록으로 교체한다.
--
-- 왜 임시로라도 필요한가:
--   온보딩에서 소속을 골라야 하는데 고를 것이 없으면 진행이 막힌다.
--   테스터가 성인 지인이라 실제 학교 대신 "코드잇 DA 14기"를 하나 두고
--   반 대신 팀으로 나눈다.
--
-- 교체 시점:
--   NEIS 에서 실 학교 목록을 받아온 뒤. 이 학교는 지우거나
--   status 개념을 넣어 숨긴다. 그때 온보딩 화면은 손댈 필요가 없다
--   (학교를 목록에서 고르는 구조는 그대로이므로).
--
-- 재실행해도 안전하다.
-- =====================================================================

-- 지역 --------------------------------------------------------------
INSERT INTO region (sido, sigungu)
VALUES ('서울특별시', '성동구')
ON CONFLICT (sido, sigungu) DO NOTHING;

-- 학교 --------------------------------------------------------------
-- name_masked 지만 실명 마스킹이 아니라 표시명 그대로다.
-- 개인 이름이 아니라 조직 이름이라 가릴 것이 없다.
INSERT INTO school (name_masked, region_id, school_type, student_count)
SELECT '코드잇 DA 14기', r.id, 'HIGH', 0
FROM region r
WHERE r.sido = '서울특별시' AND r.sigungu = '성동구'
  AND NOT EXISTS (SELECT 1 FROM school WHERE name_masked = '코드잇 DA 14기');

-- 팀 ----------------------------------------------------------------
-- grade 는 1 로 고정하고 class_num 1~4 를 팀 번호로 쓴다.
-- 화면에는 label("1팀")이 그대로 나온다.
INSERT INTO grade_class (school_id, grade, class_num, label)
SELECT s.id, 1, t.n, t.n || '팀'
FROM school s
CROSS JOIN (VALUES (1), (2), (3), (4)) AS t(n)
WHERE s.name_masked = '코드잇 DA 14기'
ON CONFLICT (school_id, grade, class_num) DO UPDATE
    SET label = EXCLUDED.label;
