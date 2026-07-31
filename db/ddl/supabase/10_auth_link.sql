-- =====================================================================
-- supabase/10_auth_link.sql · Supabase 전용 추가분
-- =====================================================================
-- 로컬 Postgres 에는 auth 스키마가 없으므로 이 파일은 Supabase 에만 적용한다.
-- (db/apply.py 가 --target supabase 일 때만 실행한다)
-- =====================================================================

-- app_user 를 Supabase 익명 계정과 연결 -------------------------------
-- 이메일·비밀번호 없이 접속만으로 auth.users 행이 생기고, 그 uuid 를 여기 연결한다.
--
-- ON DELETE SET NULL 인 이유:
--   인증 계정이 사라져도 app_user 행은 남겨야 한다. 투표·하트 기록이
--   전부 이 행을 참조하고 있어서 CASCADE 로 지우면 데이터가 연쇄 삭제된다.
--   탈퇴는 status='WITHDRAWN' 으로 표현하는 것이 설계 의도다.
ALTER TABLE public.app_user
    ADD CONSTRAINT fk_app_user_auth
    FOREIGN KEY (auth_user_id) REFERENCES auth.users(id) ON DELETE SET NULL;


-- 현재 접속자의 app_user.id 를 돌려주는 헬퍼 ---------------------------
-- RLS 정책이 매번 "지금 요청한 사람이 누구인가"를 알아야 하는데,
-- auth.uid() 는 auth.users 의 uuid 라 app_user.id(bigint)로 한 번 변환해야 한다.
--
-- SECURITY DEFINER 인 이유:
--   app_user 에도 RLS 가 걸리므로, 이 함수가 일반 권한으로 돌면
--   자기 행을 찾으려다 다시 RLS 를 타고 무한 재귀에 빠진다.
--   소유자 권한으로 실행해 RLS 를 우회한다.
--
-- SET search_path = '' 인 이유:
--   SECURITY DEFINER 함수는 search_path 조작 공격에 노출된다.
--   빈 search_path 로 고정하고 모든 객체를 스키마까지 명시한다.
CREATE OR REPLACE FUNCTION public.current_app_user_id()
RETURNS bigint
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT id FROM public.app_user WHERE auth_user_id = auth.uid()
$$;

REVOKE ALL ON FUNCTION public.current_app_user_id() FROM public;
GRANT EXECUTE ON FUNCTION public.current_app_user_id() TO authenticated;


-- 두 유저가 친구인지 판정하는 헬퍼 --------------------------------------
-- 투표·후보 조회 정책에서 반복해서 쓰인다.
-- friendship 은 user_low_id < user_high_id 규칙으로 저장되므로 정렬해서 조회한다.
CREATE OR REPLACE FUNCTION public.is_friend(a bigint, b bigint)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.friendship f
        WHERE f.user_low_id  = LEAST(a, b)
          AND f.user_high_id = GREATEST(a, b)
          AND f.ended_at IS NULL          -- 끊은 관계는 친구가 아니다(011)
    )
$$;

REVOKE ALL ON FUNCTION public.is_friend(bigint, bigint) FROM public;
GRANT EXECUTE ON FUNCTION public.is_friend(bigint, bigint) TO authenticated;
