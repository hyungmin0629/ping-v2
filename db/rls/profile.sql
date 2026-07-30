-- =====================================================================
-- profile.sql · 프로필 수정 (W11)
-- =====================================================================
-- 닉네임·소속·성별을 고친다.
--
-- 왜 RPC 인가 — W1 에서 이미 컬럼 단위로 UPDATE 를 열어뒀다:
--     GRANT UPDATE (nickname, class_id, gender) ON app_user TO authenticated;
--
-- 그 경로는 안전하지만(다른 컬럼은 못 건드린다) **검증이 없다.**
-- 가입은 complete_onboarding() 이 닉네임 2~20자, 성별 필수, 학급 존재를
-- 확인하는데, 직접 UPDATE 는 그걸 전부 우회한다:
--
--     nickname = ''      빈 이름으로 게시판에 글이 올라간다
--     gender   = NULL    힌트 4단계 중 하나가 사라진다(성별이 첫 단계다)
--     class_id = 아무거나  학급이 없는 학교로 옮겨 반을 못 고르는 상태가 된다
--
-- 가입과 수정이 같은 규칙을 따라야 하므로 통로를 하나로 모은다.
-- 직접 UPDATE 권한은 회수한다 — 남겨두면 이 함수의 검증이 우회 가능하다.
--
-- 재실행해도 안전하다.
-- =====================================================================

CREATE OR REPLACE FUNCTION public.update_profile(
    p_nickname text,
    p_class_id bigint,
    p_gender   public.gender_type
)
RETURNS public.app_user
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me   bigint := public.current_app_user_id();
    v_nick text   := btrim(coalesce(p_nickname, ''));
    v_row  public.app_user;
BEGIN
    IF v_me IS NULL THEN
        RAISE EXCEPTION '먼저 프로필을 만들어 주세요' USING ERRCODE = '28000';
    END IF;

    -- 가입과 같은 규칙이다. 두 곳의 기준이 갈리면 어느 쪽이 맞는지 알 수 없다.
    IF char_length(v_nick) < 2 OR char_length(v_nick) > 20 THEN
        RAISE EXCEPTION '닉네임은 2~20자여야 합니다' USING ERRCODE = '22023';
    END IF;
    IF p_gender IS NULL THEN
        RAISE EXCEPTION '성별을 선택해 주세요' USING ERRCODE = '22023';
    END IF;

    -- 온보딩 목록과 같은 범위로 제한한다. selectable_school 은 **학급이 등록된
    -- 학교만** 내보내는데, 그 밖으로 옮기면 반을 고를 수 없는 상태가 된다.
    -- FK 만 믿으면 전국 5,724개 학교 아무 데나 갈 수 있다.
    IF NOT EXISTS (
        SELECT 1 FROM public.grade_class g
          JOIN public.selectable_school s ON s.id = g.school_id
         WHERE g.id = p_class_id
    ) THEN
        RAISE EXCEPTION '고를 수 없는 학급입니다' USING ERRCODE = '23503';
    END IF;

    UPDATE public.app_user
       SET nickname = v_nick, class_id = p_class_id, gender = p_gender
     WHERE id = v_me
    RETURNING * INTO v_row;

    RETURN v_row;
END;
$$;

REVOKE ALL ON FUNCTION public.update_profile(text, bigint, public.gender_type) FROM public;
GRANT EXECUTE ON FUNCTION public.update_profile(text, bigint, public.gender_type) TO authenticated;


-- ---------------------------------------------------------------------
-- 직접 UPDATE 는 닫는다
-- ---------------------------------------------------------------------
-- W1 의 컬럼 단위 GRANT 를 회수한다. 남겨두면 위 검증을 건너뛸 수 있다.
-- 권한이 없으면 정책도 의미가 없으므로 함께 지운다.
REVOKE UPDATE ON public.app_user FROM authenticated;
DROP POLICY IF EXISTS update_own_user ON public.app_user;


-- ---------------------------------------------------------------------
-- 알아둘 것 — 소속을 바꾸면 따라 바뀌는 것들
-- ---------------------------------------------------------------------
-- 학교를 옮기면 **게시판과 친구 추천이 새 학교 기준으로 바뀐다.**
-- 이미 쓴 글은 옛 학교에 남는다(post.school_id 는 작성 시점 스냅샷이다).
-- 본인도 더는 그 글을 볼 수 없다. 지우는 것보다 남기는 쪽이 맞다고 보았다 —
-- 글은 그 학교 사람들에게 남긴 것이지 글쓴이를 따라다니는 것이 아니다.
--
-- 반만 바꾸면 CLASS 스코프 투표의 후보 풀이 바뀐다. 이미 한 투표는 그대로다
-- (vote_item.candidate_scope 가 출제 시점 스냅샷이다).
--
-- 닉네임을 바꾸면 **과거 글과 댓글에도 새 이름이 보인다.** board_post 뷰가
-- app_user 를 그때그때 조인하기 때문이다. 이름 변경 이력은 남기지 않는다 —
-- 지금 필요하지 않고, 필요해지면 그때가 이력 테이블을 만들 때다.
