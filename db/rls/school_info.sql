-- =====================================================================
-- school_info.sql · 학교 정보(급식·공지·학사일정) 읽기 (W8)
-- =====================================================================
-- 왜 고치나:
--   기존 정책은 "내 소속 학교의 것만" 이었다. 그런데 테스트 조직은 실제 학교가
--   아니어서 급식이 없고, 서울고등학교의 데이터를 빌려 쓴다
--   (school.info_school_id, migration 002).
--   급식은 **데이터를 준 학교 아래** 저장한다 — 조직마다 복사해두면 같은 급식이
--   조직 수만큼 늘어난다. 대신 정책이 그 연결을 따라간다.
--
-- 보통 학교는 info_school_id 가 비어 있어 자기 자신을 가리키므로 동작이 같다.
--
-- 재실행해도 안전하다.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. 내가 학교 정보를 받아올 학교
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.my_info_school_id()
RETURNS bigint
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
AS $$
    SELECT coalesce(s.info_school_id, s.id)
      FROM public.app_user u
      JOIN public.grade_class g ON g.id = u.class_id
      JOIN public.school s      ON s.id = g.school_id
     WHERE u.id = public.current_app_user_id()
$$;

REVOKE ALL ON FUNCTION public.my_info_school_id() FROM public;
GRANT EXECUTE ON FUNCTION public.my_info_school_id() TO authenticated;


-- ---------------------------------------------------------------------
-- 2. 급식
-- ---------------------------------------------------------------------
DROP POLICY IF EXISTS read_own_school_meal ON public.meal_plan;
CREATE POLICY read_own_school_meal ON public.meal_plan
    FOR SELECT TO authenticated
    USING (school_id = public.my_info_school_id());

-- 기존 정책은 "부모 급식표가 존재하기만 하면" 통과였다. 부모의 학교까지 확인한다.
DROP POLICY IF EXISTS read_own_meal_item ON public.meal_menu_item;
CREATE POLICY read_own_meal_item ON public.meal_menu_item
    FOR SELECT TO authenticated
    USING (EXISTS (
        SELECT 1 FROM public.meal_plan m
         WHERE m.id = meal_plan_id
           AND m.school_id = public.my_info_school_id()));


-- ---------------------------------------------------------------------
-- 3. 공지 · 학사일정 (아직 화면은 없지만 같은 규칙을 적용해 둔다)
-- ---------------------------------------------------------------------
DROP POLICY IF EXISTS read_own_school_notice ON public.school_notice;
CREATE POLICY read_own_school_notice ON public.school_notice
    FOR SELECT TO authenticated
    USING (school_id = public.my_info_school_id());

DROP POLICY IF EXISTS read_own_school_event ON public.school_event;
CREATE POLICY read_own_school_event ON public.school_event
    FOR SELECT TO authenticated
    USING (school_id = public.my_info_school_id());

-- 시간표는 학교가 아니라 **학급**에 걸려 있어 그대로 둔다.
-- 빌려 쓰는 조직의 학급 id 와 실제 학교의 학급 id 가 달라서, 시간표를 붙일 때는
-- 학급끼리 맺어주는 별도 처리가 필요하다. 급식과 달리 지금 풀 문제가 아니다.


-- ---------------------------------------------------------------------
-- 4. 쓰기는 닫는다
-- ---------------------------------------------------------------------
-- 학교 정보는 전부 수집기(서버)만 넣는다.
REVOKE INSERT, UPDATE, DELETE ON public.meal_plan FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.meal_menu_item FROM authenticated;

-- ⚠️ 급식만 회수해 두고 공지·학사일정은 빠져 있었다(W8 → W16 에서 발견).
--   INSERT 정책이 없어 RLS 가 막고는 있었지만, 정책 하나를 잘못 넓히는 순간
--   뚫린다. 권한을 아예 주지 않으면 정책 실수가 사고로 이어지지 않는다.
REVOKE INSERT, UPDATE, DELETE ON public.school_event FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.school_notice FROM authenticated;


-- ---------------------------------------------------------------------
-- 5. 내 학교가 어디 정보를 빌려 쓰는가
-- ---------------------------------------------------------------------
-- 화면에 "이 급식은 OO고등학교 공개 데이터입니다"를 띄우려면 앱이 그 사실을
-- 알아야 한다. 빌려 쓰지 않는 보통 학교에는 그 문구가 필요 없으므로,
-- 앱이 판단할 수 있도록 두 이름을 함께 내보낸다.
CREATE OR REPLACE VIEW public.my_school_source
WITH (security_invoker = false) AS
SELECT
    s.id                                            AS school_id,
    s.name_masked                                   AS school_name,
    i.id                                            AS info_school_id,
    i.name_masked                                   AS info_school_name,
    (s.info_school_id IS NOT NULL
     AND s.info_school_id <> s.id)                  AS borrowed
FROM public.app_user u
JOIN public.grade_class g ON g.id = u.class_id
JOIN public.school s      ON s.id = g.school_id
JOIN public.school i      ON i.id = coalesce(s.info_school_id, s.id)
WHERE u.id = public.current_app_user_id();

GRANT SELECT ON public.my_school_source TO authenticated;
