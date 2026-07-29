-- =====================================================================
-- school_picker.sql · 온보딩에서 고를 수 있는 학교 (P3)
-- =====================================================================
-- 왜 필요한가:
--   NEIS 에서 전국 중·고 5,700여 개를 받아오면서 학교 목록이 감당할 수 없게
--   커졌다. PostgREST 는 한 번에 1,000행까지만 주므로 임시 조직이 목록에서
--   잘려나갔고, 온보딩이 조용히 깨졌다.
--
-- 무엇을 거르나:
--   **학급이 등록된 학교만** 내보낸다. 학급이 없는 학교를 고르면 반을 고를 수
--   없어 온보딩을 끝내지 못한다. 고를 수 없는 것을 보여주지 않는 게 맞다.
--
--   학급은 학교마다 NEIS 를 한 번씩 불러야 해서 5,700개를 미리 받아둘 수 없다
--   (개발계정 일일 호출 한도). 클로즈드 테스트는 학교 하나로 진행하므로
--   그 학교의 학급만 받아두면 된다. (db/neis_schools.py --classes)
--
-- 재실행해도 안전하다.
-- =====================================================================

CREATE OR REPLACE VIEW public.selectable_school
WITH (security_invoker = false) AS
SELECT
    s.id,
    s.name_masked,
    s.school_type,
    r.sido,
    r.sigungu
FROM public.school s
JOIN public.region r ON r.id = s.region_id
WHERE EXISTS (SELECT 1 FROM public.grade_class g WHERE g.school_id = s.id);

GRANT SELECT ON public.selectable_school TO authenticated;
