-- =====================================================================
-- friends.sql · 친구 맺기 (W4)
-- =====================================================================
-- 왜 RPC 인가:
--   policies.sql 은 friend_request 의 INSERT/UPDATE 를 클라이언트에 열어두고
--   있었다. 그런데 app_user.id 는 1부터 이어지는 정수다. 요청을 직접 INSERT 할
--   수 있으면 receiver_id 를 1,2,3… 으로 바꿔가며 전체 가입자에게 요청을
--   뿌릴 수 있다 — 코드를 아는 사람만 서로를 찾는다는 전제가 무너진다.
--   status 를 마음대로 넣는 것도 막을 수 없다.
--
--   그래서 보내기·수락·거절을 전부 함수로 옮기고 테이블 권한을 회수한다.
--   상대를 지목하는 유일한 수단은 초대 코드다.
--
-- 5명 게이트:
--   친구가 5명이 되면 투표가 열린다(service_unlocked_at). 이 값은 수락 시점에
--   찍는다. 보낸 것만으로 열리면 혼자 계정을 만들어 게이트를 통과할 수 있다.
--
-- 재실행해도 안전하다.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. 친구 수와 게이트 다시 계산
-- ---------------------------------------------------------------------
-- 증감이 아니라 friendship 을 세서 덮어쓴다. 어긋나 있어도 부를 때마다
-- 제자리를 찾고, 두 번 불려도 결과가 같다. 구 서비스의 친구 수는 증감식으로
-- 관리되다 실제 관계와 어긋나 있었다.
--
-- service_unlocked_at 은 한 번 찍히면 유지한다. 친구가 줄어도 이미 연 서비스를
-- 다시 닫지는 않는다(투표 기록이 이미 쌓였을 수 있다).
CREATE OR REPLACE FUNCTION public.refresh_friend_state(p_user_id bigint)
RETURNS void
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
    UPDATE public.app_user u
       SET friend_count = c.n::int,
           service_unlocked_at = CASE
               WHEN u.service_unlocked_at IS NOT NULL THEN u.service_unlocked_at
               WHEN c.n >= 5 THEN now()   -- 5명 게이트
           END,
           updated_at = now()
      FROM (SELECT count(*) AS n
              FROM public.friendship f
             WHERE (f.user_low_id = p_user_id OR f.user_high_id = p_user_id)
               AND f.ended_at IS NULL) c
     WHERE u.id = p_user_id
$$;

REVOKE ALL ON FUNCTION public.refresh_friend_state(bigint) FROM public;


-- ---------------------------------------------------------------------
-- 2. 두 사람을 친구로 만든다 (내부용)
-- ---------------------------------------------------------------------
-- friendship 은 user_low_id < user_high_id 규칙이라 정렬해서 넣는다.
CREATE OR REPLACE FUNCTION public.link_friendship(
    a bigint, b bigint, p_source public.relation_source)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
BEGIN
    -- 부분 UNIQUE(살아 있는 관계에만) 라 조건까지 적어야 짝이 맞는다.
    -- 끊었던 사이면 옛 행은 그대로 두고 **새 행**이 생긴다 —
    -- 그래야 "몇 번 끊었다 붙었나"가 행 수로 남는다(011).
    INSERT INTO public.friendship (user_low_id, user_high_id, source)
    VALUES (LEAST(a, b), GREATEST(a, b), p_source)
    ON CONFLICT (user_low_id, user_high_id) WHERE ended_at IS NULL DO NOTHING;

    PERFORM public.refresh_friend_state(a);
    PERFORM public.refresh_friend_state(b);
END;
$$;

REVOKE ALL ON FUNCTION public.link_friendship(bigint, bigint, public.relation_source) FROM public;


-- ---------------------------------------------------------------------
-- 3. 초대 코드로 친구 요청 보내기
-- ---------------------------------------------------------------------
-- 결과를 예외가 아니라 문자열로 돌려준다. "이미 친구다", "코드가 없다"는
-- 오류가 아니라 화면이 안내해야 할 정상적인 상황이기 때문이다.
--
--   NOT_FOUND       그런 코드가 없다
--   SELF            내 코드다
--   ALREADY_FRIEND  이미 친구다
--   ALREADY_SENT    이미 보냈고 상대가 아직 응답하지 않았다
--   ACCEPTED        상대가 먼저 나에게 보내둔 요청이 있어 그 자리에서 맺어졌다
--   SENT            요청을 보냈다
CREATE OR REPLACE FUNCTION public.send_friend_request(p_code text)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me     bigint := public.current_app_user_id();
    v_target bigint;
    v_incoming bigint;
BEGIN
    IF v_me IS NULL THEN
        RAISE EXCEPTION '먼저 프로필을 만들어 주세요' USING ERRCODE = '28000';
    END IF;

    SELECT u.id INTO v_target
      FROM public.app_user u
     WHERE u.invite_code = upper(btrim(p_code))
       AND u.status = 'ACTIVE';

    IF v_target IS NULL THEN
        RETURN 'NOT_FOUND';
    END IF;
    IF v_target = v_me THEN
        RETURN 'SELF';
    END IF;
    IF public.is_friend(v_me, v_target) THEN
        RETURN 'ALREADY_FRIEND';
    END IF;

    -- 상대가 먼저 보내둔 요청이 있으면 서로 원한다는 뜻이다. 바로 맺는다.
    SELECT r.id INTO v_incoming
      FROM public.friend_request r
     WHERE r.sender_id = v_target AND r.receiver_id = v_me AND r.status = 'PENDING';

    IF v_incoming IS NOT NULL THEN
        UPDATE public.friend_request
           SET status = 'ACCEPTED', responded_at = now()
         WHERE id = v_incoming;
        PERFORM public.link_friendship(v_me, v_target, 'INVITE_CODE');
        RETURN 'ACCEPTED';
    END IF;

    -- 이미 보내둔 요청이 있으면 다시 보내지 않는다.
    IF EXISTS (SELECT 1 FROM public.friend_request r
                WHERE r.sender_id = v_me AND r.receiver_id = v_target
                  AND r.status = 'PENDING') THEN
        RETURN 'ALREADY_SENT';
    END IF;

    -- 거절당한 뒤, 또는 친구였다가 끊은 뒤 다시 보내는 경우가 있다.
    -- ⚠️ 예전에는 옛 행을 PENDING 으로 **되돌렸다.** UNIQUE(sender,receiver) 가
    --    행 하나만 허용했기 때문이다. 그 방식은 이전 요청의 시각을 덮어써
    --    "언제 처음 불렀나"를 지웠다. W19 에서 UNIQUE 를 PENDING 인 것에만
    --    걸도록 바꿨으므로 이제 **새 행**을 넣는다 — 요청 이력이 쌓인다.
    INSERT INTO public.friend_request (sender_id, receiver_id, status, source)
    VALUES (v_me, v_target, 'PENDING', 'INVITE_CODE');

    RETURN 'SENT';
END;
$$;

REVOKE ALL ON FUNCTION public.send_friend_request(text) FROM public;
GRANT EXECUTE ON FUNCTION public.send_friend_request(text) TO authenticated;


-- ---------------------------------------------------------------------
-- 4. 받은 요청에 응답하기
-- ---------------------------------------------------------------------
-- 받은 사람만 응답할 수 있다. 남의 요청 id 를 넣어도 아무 일이 없다.
CREATE OR REPLACE FUNCTION public.accept_friend_request(p_request_id bigint)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me bigint := public.current_app_user_id();
    v_sender bigint;
    v_source public.relation_source;
BEGIN
    SELECT r.sender_id, r.source INTO v_sender, v_source
      FROM public.friend_request r
     WHERE r.id = p_request_id
       AND r.receiver_id = v_me
       AND r.status = 'PENDING';

    IF v_sender IS NULL THEN
        RETURN 'NOT_FOUND';
    END IF;

    UPDATE public.friend_request
       SET status = 'ACCEPTED', responded_at = now()
     WHERE id = p_request_id;

    PERFORM public.link_friendship(v_me, v_sender, v_source);
    RETURN 'ACCEPTED';
END;
$$;

CREATE OR REPLACE FUNCTION public.reject_friend_request(p_request_id bigint)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me bigint := public.current_app_user_id();
BEGIN
    UPDATE public.friend_request
       SET status = 'REJECTED', responded_at = now()
     WHERE id = p_request_id
       AND receiver_id = v_me
       AND status = 'PENDING';

    IF NOT FOUND THEN
        RETURN 'NOT_FOUND';
    END IF;
    RETURN 'REJECTED';
END;
$$;

REVOKE ALL ON FUNCTION public.accept_friend_request(bigint) FROM public;
REVOKE ALL ON FUNCTION public.reject_friend_request(bigint) FROM public;
GRANT EXECUTE ON FUNCTION public.accept_friend_request(bigint) TO authenticated;
GRANT EXECUTE ON FUNCTION public.reject_friend_request(bigint) TO authenticated;


-- ---------------------------------------------------------------------
-- 5. 내 요청 목록 (뷰)
-- ---------------------------------------------------------------------
-- 요청을 보여주려면 상대의 닉네임이 필요한데, 아직 친구가 아니라서
-- app_user 도 friend_profile 도 그 사람을 보여주지 않는다.
-- 그래서 상대 정보 중 닉네임과 소속만 골라 내보내는 뷰를 둔다.
-- (하트 잔액이나 초대 코드는 나가지 않는다)
CREATE OR REPLACE VIEW public.my_friend_request
WITH (security_invoker = false) AS
SELECT
    r.id,
    CASE WHEN r.receiver_id = public.current_app_user_id()
         THEN 'INCOMING' ELSE 'OUTGOING' END AS direction,
    r.status,
    r.created_at,
    c.id       AS counterpart_id,
    c.nickname AS counterpart_nickname,
    c.class_id AS counterpart_class_id
FROM public.friend_request r
JOIN public.app_user c
  ON c.id = CASE WHEN r.sender_id = public.current_app_user_id()
                 THEN r.receiver_id ELSE r.sender_id END
WHERE r.sender_id = public.current_app_user_id()
   OR r.receiver_id = public.current_app_user_id();

GRANT SELECT ON public.my_friend_request TO authenticated;


-- ---------------------------------------------------------------------
-- 6. 친구 끊기 (W19)
-- ---------------------------------------------------------------------
-- 행을 지우지 않고 ended_at 을 찍는다. 왜인지는 migration 011 에 적었다 —
-- 요약하면 친구 끊기가 관계 이탈 신호라서 지우면 못 본다.
--
-- 한쪽이 끊으면 양쪽 다 끊긴다. friendship 은 방향이 없는 간선이고,
-- "나는 친구인데 상대는 아니다"를 담을 자리가 없다. 담을 수 있게 만들 수도
-- 있지만 그건 팔로우지 친구가 아니다.
--
-- 끊어도 **차단이 아니다.** 상대는 초대 코드로 다시 요청할 수 있다.
-- 차단은 block_record 가 할 일이고 아직 화면이 없다.
--
--   NOT_FRIEND  친구가 아니다(이미 끊었거나 애초에 아니었다)
--   SELF        나 자신
--   OK          끊었다
CREATE OR REPLACE FUNCTION public.remove_friend(p_user_id bigint)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me bigint := public.current_app_user_id();
    v_hit int;
BEGIN
    IF v_me IS NULL THEN
        RETURN 'NOT_FRIEND';
    END IF;
    IF v_me = p_user_id THEN
        RETURN 'SELF';
    END IF;

    UPDATE public.friendship
       SET ended_at = now(), updated_at = now()
     WHERE user_low_id  = LEAST(v_me, p_user_id)
       AND user_high_id = GREATEST(v_me, p_user_id)
       AND ended_at IS NULL;

    GET DIAGNOSTICS v_hit = ROW_COUNT;
    IF v_hit = 0 THEN
        RETURN 'NOT_FRIEND';
    END IF;

    -- 양쪽 friend_count 를 다시 센다. service_unlocked_at 은 그대로 둔다 —
    -- 이미 연 서비스를 닫지 않는 것이 refresh_friend_state 의 규칙이다.
    PERFORM public.refresh_friend_state(v_me);
    PERFORM public.refresh_friend_state(p_user_id);
    RETURN 'OK';
END;
$$;

REVOKE ALL ON FUNCTION public.remove_friend(bigint) FROM public;
GRANT EXECUTE ON FUNCTION public.remove_friend(bigint) TO authenticated;


-- ---------------------------------------------------------------------
-- 7. 직접 쓰기를 닫는다
-- ---------------------------------------------------------------------
-- policies.sql 의 insert_own_friend_request / respond_friend_request 를 대체한다.
DROP POLICY IF EXISTS insert_own_friend_request ON public.friend_request;
DROP POLICY IF EXISTS respond_friend_request ON public.friend_request;
REVOKE INSERT, UPDATE ON public.friend_request FROM authenticated;

-- friendship 은 원래 INSERT 정책이 없어 RLS 가 막고 있었지만,
-- 관계를 만드는 유일한 경로가 위 함수임을 권한으로도 못박는다.
REVOKE INSERT, UPDATE, DELETE ON public.friendship FROM authenticated;
