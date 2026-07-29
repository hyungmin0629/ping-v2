-- =====================================================================
-- session_log.sql · 접속 로그
-- =====================================================================
-- 왜 필요한가:
--   user_session 은 "리텐션을 추정이 아니라 실측하기 위한" 테이블인데
--   (20_social.sql 주석) W2~W5 어디에서도 쓰지 않아 계속 비어 있었다.
--   app_user.last_active_at 도 마찬가지였다. 이대로 배포하면 BigQuery 에
--   투표·하트는 흘러도 접속·리텐션 지표는 계산할 수 없다.
--
--   분석 자체는 합성 데이터로 하더라도, 실유저 몇 명의 로그가 실제로 흐르는
--   구조가 있어야 파이프라인이 의미를 갖는다. ([[CLAUDE]] 확정 제약)
--
-- 왜 RPC 인가:
--   started_at 을 조작하면 리텐션 지표가 통째로 오염된다. 시각은 서버가 찍는다.
--   클라이언트가 넘기는 것은 플랫폼과 앱 버전뿐이다.
--
-- 세션의 정의:
--   마지막 활동에서 30분이 지나면 새 세션으로 센다. 그 안이면 기존 세션의
--   ended_at 만 늘린다 — 새로고침할 때마다 세션이 생기면 "한 번 켰다"를
--   셀 수 없다. 30분은 웹 분석의 관례적 기준이다.
--
-- 재실행해도 안전하다.
-- =====================================================================

CREATE OR REPLACE FUNCTION public.touch_session(
    p_platform    public.platform_type DEFAULT 'WEB',
    p_app_version text                 DEFAULT 'unknown')
RETURNS bigint
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me      bigint := public.current_app_user_id();
    v_session bigint;
BEGIN
    -- 온보딩 전에는 app_user 행이 없다. 기록할 대상이 없으므로 조용히 넘어간다
    -- (예외를 던지면 첫 접속마다 화면에 오류가 뜬다).
    IF v_me IS NULL THEN
        RETURN NULL;
    END IF;

    SELECT s.id INTO v_session
      FROM public.user_session s
     WHERE s.user_id = v_me
       AND coalesce(s.ended_at, s.started_at) > now() - interval '30 minutes'
     ORDER BY s.started_at DESC
     LIMIT 1;

    IF FOUND THEN
        UPDATE public.user_session SET ended_at = now() WHERE id = v_session;
    ELSE
        INSERT INTO public.user_session (user_id, platform, app_version, started_at, ended_at)
        VALUES (v_me, p_platform, left(p_app_version, 20), now(), now())
        RETURNING id INTO v_session;
    END IF;

    UPDATE public.app_user
       SET last_active_at = now(), updated_at = now()
     WHERE id = v_me;

    RETURN v_session;
END;
$$;

REVOKE ALL ON FUNCTION public.touch_session(public.platform_type, text) FROM public;
GRANT EXECUTE ON FUNCTION public.touch_session(public.platform_type, text) TO authenticated;


-- 시각을 클라이언트가 정하지 못하게 한다. 읽기(SELECT)는 그대로 둔다.
DROP POLICY IF EXISTS insert_own_session ON public.user_session;
REVOKE INSERT, UPDATE, DELETE ON public.user_session FROM authenticated;
