-- =====================================================================
-- replies.sql · 받은 투표에 1회성 답장 (W15)
-- =====================================================================
-- 나를 뽑은 사람에게 짧은 말을 **한 번** 보낸다. 20하트, 30자.
-- 힌트와 순서가 없다 — 누군지 몰라도 고맙다고 할 수는 있다.
--
-- 방향에 주의할 것:
--   보내는 쪽(지목당한 사람)은 **상대가 누군지 모를 수 있다.**
--   받는 쪽(뽑은 사람)은 자기가 누구를 뽑았는지 알므로 **보낸 사람을 안다.**
--   그래서 답장은 익명이 아니다. 신고할 대상이 분명하다는 뜻이기도 하다.
--
-- ⚠️ 자유 텍스트가 사람에게 직접 간다. design-spec 2.2 는 이런 기능 앞에
--    차단 화면을 먼저 두라고 적어두었다. 차단은 아직 없으므로 최소한
--    **신고**는 열어 둔다. 30자·1회성이 나머지 위험을 눌러 준다.
--
-- 재실행해도 안전하다.
-- =====================================================================

CREATE OR REPLACE FUNCTION public.reply_cost()
RETURNS int LANGUAGE sql IMMUTABLE AS $$ SELECT 20 $$;


-- ---------------------------------------------------------------------
-- 1. 답장 보내기
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.send_reply(p_received_id bigint, p_text text)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me    bigint := public.current_app_user_id();
    v_text  text   := btrim(coalesce(p_text, ''));
    v_cost  int    := public.reply_cost();
    v_item  bigint;
    v_after bigint;
BEGIN
    IF v_me IS NULL THEN
        RAISE EXCEPTION '먼저 프로필을 만들어 주세요' USING ERRCODE = '28000';
    END IF;
    IF v_text = '' THEN
        RETURN 'EMPTY';
    END IF;
    -- 화면도 막지만 여기서 한 번 더 본다. 화면만 막으면 API 를 직접 부르는
    -- 경로가 남는다. varchar(30) 이 결국 자르지만 오류로 끝나면 안내가 없다.
    IF char_length(v_text) > 30 THEN
        RETURN 'TOO_LONG';
    END IF;

    -- 내가 받은 투표여야 한다. id 는 순번이라 찍어볼 수 있다.
    SELECT r.vote_item_id INTO v_item
      FROM public.vote_received r
     WHERE r.id = p_received_id AND r.receiver_id = v_me;
    IF NOT FOUND THEN
        RETURN 'NOT_FOUND';
    END IF;

    -- 한 번뿐이다. 컬럼이 비어 있는지가 곧 그 제약이다.
    IF EXISTS (SELECT 1 FROM public.vote_received
                WHERE id = p_received_id AND reply_text IS NOT NULL) THEN
        RETURN 'ALREADY';
    END IF;

    IF (SELECT heart_balance FROM public.app_user WHERE id = v_me) < v_cost THEN
        RETURN 'NOT_ENOUGH';
    END IF;

    UPDATE public.vote_received
       SET reply_text = v_text, replied_at = now(), answered_at = now(),
           answer_status = 'PRIVATE'
     WHERE id = p_received_id;

    -- 잔액과 원장을 한 문장 간격 안에서 같이 쓴다.
    UPDATE public.app_user
       SET heart_balance = heart_balance - v_cost
     WHERE id = v_me
    RETURNING heart_balance INTO v_after;

    INSERT INTO public.heart_transaction
        (user_id, type_code, delta, balance_after, vote_item_id, memo)
    VALUES (v_me, 'VOTE_REPLY', -v_cost, v_after, v_item, '받은 투표에 답장');

    RETURN 'OK';
END;
$$;


-- ---------------------------------------------------------------------
-- 2. 내가 한 투표 — 답장이 왔으면 함께 보인다
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW public.my_vote_history
WITH (security_invoker = false) AS
SELECT
    v.id AS vote_item_id,
    v.voted_at,
    v.candidate_scope,
    q.text AS question_text,
    c.candidate_user_id AS chosen_user_id,
    u.nickname          AS chosen_nickname,
    r.id                AS received_id,
    r.reply_text,
    r.replied_at
FROM public.vote_item v
JOIN public.question q       ON q.id = v.question_id
JOIN public.vote_candidate c ON c.vote_item_id = v.id AND c.is_chosen
JOIN public.app_user u       ON u.id = c.candidate_user_id
LEFT JOIN public.vote_received r ON r.vote_item_id = v.id
WHERE v.user_id = public.current_app_user_id()
  AND v.voted_at IS NOT NULL;

GRANT SELECT ON public.my_vote_history TO authenticated;


-- ---------------------------------------------------------------------
-- 3. 답장 신고
-- ---------------------------------------------------------------------
-- 차단 화면이 아직 없다. 그동안 최소한 신고는 할 수 있어야 한다.
-- 답장은 익명이 아니므로(받는 쪽은 보낸 사람을 안다) 대상이 분명하다.
--
-- 신고해도 **자동으로 아무 일도 하지 않는다.** 자동 조치는 집단 신고에
-- 취약해 채택하지 않았다([[DECISIONS]]). 기록만 남고 사람이 판단한다.
CREATE OR REPLACE FUNCTION public.report_reply(
    p_vote_item_id bigint,
    p_reason_code  text,
    p_detail       text DEFAULT NULL
)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me     bigint := public.current_app_user_id();
    v_target bigint;
BEGIN
    IF v_me IS NULL THEN
        RAISE EXCEPTION '먼저 프로필을 만들어 주세요' USING ERRCODE = '28000';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM public.report_reason
                    WHERE code = p_reason_code AND target_type = 'USER' AND is_active) THEN
        RAISE EXCEPTION '신고 사유가 올바르지 않습니다' USING ERRCODE = '22023';
    END IF;

    -- **내가 한 투표**에 온 답장만 신고할 수 있다. 보낸 사람이 신고 대상이다.
    SELECT r.receiver_id INTO v_target
      FROM public.vote_item v
      JOIN public.vote_received r ON r.vote_item_id = v.id
     WHERE v.id = p_vote_item_id AND v.user_id = v_me
       AND r.reply_text IS NOT NULL;
    IF NOT FOUND THEN
        RETURN 'NOT_FOUND';
    END IF;

    IF EXISTS (SELECT 1 FROM public.report
                WHERE reporter_id = v_me AND target_type = 'USER'
                  AND target_user_id = v_target) THEN
        RETURN 'ALREADY';
    END IF;

    INSERT INTO public.report (reporter_id, target_type, target_user_id,
                               reason_code, detail_text)
    VALUES (v_me, 'USER', v_target, p_reason_code,
            nullif(btrim(coalesce(p_detail, '')), ''));

    RETURN 'OK';
END;
$$;


-- ---------------------------------------------------------------------
-- 4. 권한
-- ---------------------------------------------------------------------
REVOKE ALL ON FUNCTION public.reply_cost()                          FROM public;
REVOKE ALL ON FUNCTION public.send_reply(bigint, text)              FROM public;
REVOKE ALL ON FUNCTION public.report_reply(bigint, text, text)      FROM public;

GRANT EXECUTE ON FUNCTION public.send_reply(bigint, text)           TO authenticated;
GRANT EXECUTE ON FUNCTION public.report_reply(bigint, text, text)   TO authenticated;

-- vote_received 직접 쓰기는 이미 닫혀 있다(voting.sql). 답장도 RPC 로만 한다.
REVOKE INSERT, UPDATE, DELETE ON public.vote_received FROM authenticated;
