-- =====================================================================
-- recommend.sql · 친구 추천 (W10)
-- =====================================================================
-- 같은 학교 사람을 목록으로 보여주고, 요청을 보내거나 "안 볼래" 할 수 있다.
--
-- ⚠️ 이 기능은 **"초대 코드로만 친구를 맺는다"는 원칙을 좁은 범위에서 연다.**
--    코드 없이 상대를 지목할 수 있게 되기 때문이다. 그래서 범위를 좁히는 데
--    공을 들였다 — 같은 학교 · 활동 중 · 아직 아무 관계도 없는 사람만.
--    경위와 남는 위험은 [[DECISIONS]].
--
-- 절대 어기면 안 되는 것 두 가지:
--
--   1. **더미(is_synthetic)는 추천에 나오지 않는다.**
--      "테스터가 더미를 마주칠 경로가 없다"가 더미를 남겨둔 근거였다
--      (CLAUDE.md). 추천에 뜨면 그 전제가 바로 깨지고, 지인이 시험친구01 에게
--      친구 요청을 보내게 된다.
--
--   2. **초대 코드를 내보내지 않는다.**
--      추천 목록에 코드를 실으면 그 화면이 곧 코드 명부가 된다.
--      상대를 가리키는 값은 id 뿐이고, 그 id 로 할 수 있는 일은 아래 RPC 둘뿐이다.
--
-- 재실행해도 안전하다.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. 추천 목록
-- ---------------------------------------------------------------------
-- app_user 는 본인 행만 읽히므로 정의자 권한 뷰로 필요한 것만 낸다.
-- 나가는 값은 닉네임과 학년·반뿐이다. 하트도 초대 코드도 나가지 않는다.
CREATE OR REPLACE VIEW public.friend_suggestion
WITH (security_invoker = false) AS
SELECT
    u.id,
    u.nickname,
    g.grade,
    g.class_num,
    g.label                                   AS class_label,
    (g.id = me.class_id)                      AS same_class,
    CASE WHEN g.id = me.class_id THEN 'SAME_CLASS' ELSE 'SAME_SCHOOL' END::public.recommend_reason
                                              AS reason,
    u.created_at
FROM public.app_user u
JOIN public.grade_class g ON g.id = u.class_id
JOIN public.app_user me   ON me.id = public.current_app_user_id()
JOIN public.grade_class mg ON mg.id = me.class_id
WHERE g.school_id = mg.school_id           -- 같은 학교
  AND u.id <> me.id
  AND u.status = 'ACTIVE'
  AND NOT u.is_synthetic                   -- ★ 더미는 절대 나가지 않는다
  AND NOT public.is_friend(me.id, u.id)
  -- 이미 오간 요청이 있으면 빼둔다. 거절당한 사람이 다시 목록에 뜨면
  -- 코드 없이 반복해서 부를 수 있게 된다. 초대 코드 경로는 그대로 열려 있다.
  AND NOT EXISTS (
      SELECT 1 FROM public.friend_request r
       WHERE (r.sender_id = me.id AND r.receiver_id = u.id)
          OR (r.sender_id = u.id AND r.receiver_id = me.id))
  -- "안 볼래" 한 사람
  AND NOT EXISTS (
      SELECT 1 FROM public.rejected_friend_recommendations fr
       WHERE fr.user_id = me.id AND fr.recommended_user_id = u.id
         AND fr.dismissed_at IS NOT NULL)
  -- 차단. 화면은 아직 없지만 조건을 미리 넣어 둔다 —
  -- 나중에 차단 기능을 붙일 때 이 뷰를 다시 고치지 않으려고.
  AND NOT EXISTS (
      SELECT 1 FROM public.block_record b
       WHERE (b.user_id = me.id AND b.blocked_user_id = u.id)
          OR (b.user_id = u.id AND b.blocked_user_id = me.id));

GRANT SELECT ON public.friend_suggestion TO authenticated;


-- ---------------------------------------------------------------------
-- 2. 추천에서 요청 보내기
-- ---------------------------------------------------------------------
-- 초대 코드 경로(send_friend_request)와 달리 코드를 모르는 상대에게 보낸다.
-- 그래서 **대상이 정말 내 추천 목록에 있는지 서버에서 다시 확인한다.**
-- 클라이언트가 보낸 id 를 믿으면 이 함수가 곧 전체 지목 통로가 된다.
CREATE OR REPLACE FUNCTION public.send_request_to(p_user_id bigint)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me       bigint := public.current_app_user_id();
    v_incoming bigint;
BEGIN
    IF v_me IS NULL THEN
        RAISE EXCEPTION '먼저 프로필을 만들어 주세요' USING ERRCODE = '28000';
    END IF;
    IF p_user_id = v_me THEN
        RETURN 'SELF';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM public.friend_suggestion s WHERE s.id = p_user_id) THEN
        -- 추천에 없는 사람이다. 이미 친구거나, 요청이 오갔거나, 다른 학교거나,
        -- 더미다. 어느 쪽인지는 알려주지 않는다 — 알려주면 존재 확인 수단이 된다.
        RETURN 'NOT_FOUND';
    END IF;

    -- 상대가 먼저 보내둔 요청이 있으면 서로 원한다는 뜻이다. 바로 맺는다.
    -- (추천 목록에서는 걸러지지만, 목록을 띄운 뒤 상대가 보냈을 수 있다)
    SELECT r.id INTO v_incoming
      FROM public.friend_request r
     WHERE r.sender_id = p_user_id AND r.receiver_id = v_me AND r.status = 'PENDING';

    IF v_incoming IS NOT NULL THEN
        UPDATE public.friend_request
           SET status = 'ACCEPTED', responded_at = now()
         WHERE id = v_incoming;
        PERFORM public.link_friendship(v_me, p_user_id, 'RECOMMEND');
        RETURN 'ACCEPTED';
    END IF;

    INSERT INTO public.friend_request (sender_id, receiver_id, status, source)
    VALUES (v_me, p_user_id, 'PENDING', 'RECOMMEND');

    RETURN 'SENT';
END;
$$;


-- ---------------------------------------------------------------------
-- 3. "안 볼래"
-- ---------------------------------------------------------------------
-- 목록에서 빼기만 한다. 상대에게는 아무것도 알리지 않고, 상대가 나에게
-- 요청을 보내는 것도 막지 않는다 — 그건 차단이지 "안 볼래"가 아니다.
CREATE OR REPLACE FUNCTION public.dismiss_suggestion(p_user_id bigint)
RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me     bigint := public.current_app_user_id();
    v_reason public.recommend_reason;
BEGIN
    IF v_me IS NULL THEN
        RAISE EXCEPTION '먼저 프로필을 만들어 주세요' USING ERRCODE = '28000';
    END IF;

    SELECT s.reason INTO v_reason
      FROM public.friend_suggestion s WHERE s.id = p_user_id;

    IF v_reason IS NULL THEN
        RETURN false;
    END IF;

    INSERT INTO public.rejected_friend_recommendations
        (user_id, recommended_user_id, reason, dismissed_at)
    VALUES (v_me, p_user_id, v_reason, now())
    ON CONFLICT (user_id, recommended_user_id)
    DO UPDATE SET dismissed_at = now();

    RETURN true;
END;
$$;


-- ---------------------------------------------------------------------
-- 4. 권한
-- ---------------------------------------------------------------------
REVOKE ALL ON FUNCTION public.send_request_to(bigint)     FROM public;
REVOKE ALL ON FUNCTION public.dismiss_suggestion(bigint)  FROM public;
GRANT EXECUTE ON FUNCTION public.send_request_to(bigint)    TO authenticated;
GRANT EXECUTE ON FUNCTION public.dismiss_suggestion(bigint) TO authenticated;

-- 추천 테이블 자체는 브라우저가 손대지 못한다. 열어주면 남의 추천 이력을
-- 만들거나 지울 수 있다.
REVOKE INSERT, UPDATE, DELETE ON public.rejected_friend_recommendations FROM authenticated;
