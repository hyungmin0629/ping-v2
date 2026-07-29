-- =====================================================================
-- voting.sql · 투표 (W5)
-- =====================================================================
-- 규칙이 있는 조작은 전부 여기 함수로 한다. 클라이언트가 vote_candidate 를
-- 직접 넣을 수 있으면 후보를 자기 마음대로 만들 수 있고, heart_transaction 을
-- 넣을 수 있으면 하트를 무한정 만들 수 있다.
--
-- 후보 규칙 (설계서 2.4):
--   세 스코프 모두 "친구" 안에서의 범위다. 모르는 사람은 어떤 경우에도 뜨지 않는다.
--     CLASS  = 같은 반 친구 / SCHOOL = 같은 학교 친구 / GLOBAL = 친구 전체
--   후보가 4명이 안 되면 스코프를 한 단계 낮추고, GLOBAL 에서도 모자라면
--   그 질문은 내지 않는다. 친구가 5명이어도 같은 반 친구가 2명뿐일 수 있기 때문이다.
--
-- 하트 (generator/config/distribution.yaml · 구 서비스 실측):
--   투표 1건당 5~15개를 투표자와 지목당한 사람 **양쪽**에 지급한다.
--   잔액을 바꾸는 자리에서 원장도 함께 쓴다 — 구 시스템 최대 결함이 불일치였다.
--
-- 재실행해도 안전하다.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. 하트 지급 (내부용)
-- ---------------------------------------------------------------------
-- 잔액과 원장을 한 문장 간격 안에서 같이 쓴다. balance_after 는 갱신된
-- 잔액을 그대로 받아 적으므로 둘이 어긋날 수 없다.
CREATE OR REPLACE FUNCTION public.grant_hearts(
    p_user bigint, p_amount int, p_type text, p_vote_item bigint DEFAULT NULL)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE v_after bigint;
BEGIN
    UPDATE public.app_user
       SET heart_balance = heart_balance + p_amount, updated_at = now()
     WHERE id = p_user
    RETURNING heart_balance INTO v_after;

    INSERT INTO public.heart_transaction
        (user_id, type_code, delta, balance_after, vote_item_id)
    VALUES (p_user, p_type, p_amount, v_after, p_vote_item);
END;
$$;

REVOKE ALL ON FUNCTION public.grant_hearts(bigint, int, text, bigint) FROM public;


-- ---------------------------------------------------------------------
-- 2. 후보 뽑기 (내부용)
-- ---------------------------------------------------------------------
-- 친구 중에서 스코프 조건에 맞는 ACTIVE 유저를 무작위 4명.
-- p_exclude 는 셔플에서 쓴다 — 직전 후보를 뒤로 미뤄 다른 얼굴이 나오게 한다.
-- 뺄 만큼 넉넉하지 않으면 다시 나올 수도 있다(4명을 채우는 쪽이 우선이다).
CREATE OR REPLACE FUNCTION public.pick_candidates(
    p_user bigint, p_scope public.question_scope, p_exclude bigint[] DEFAULT '{}')
RETURNS TABLE (candidate_user_id bigint)
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
    WITH me AS (
        SELECT u.class_id, g.school_id
          FROM public.app_user u
          JOIN public.grade_class g ON g.id = u.class_id
         WHERE u.id = p_user
    ), friends AS (
        SELECT CASE WHEN f.user_low_id = p_user THEN f.user_high_id
                    ELSE f.user_low_id END AS id
          FROM public.friendship f
         WHERE f.user_low_id = p_user OR f.user_high_id = p_user
    )
    SELECT u.id
      FROM friends fr
      JOIN public.app_user u   ON u.id = fr.id AND u.status = 'ACTIVE'
      JOIN public.grade_class g ON g.id = u.class_id
     CROSS JOIN me
     WHERE p_scope = 'GLOBAL'
        OR (p_scope = 'SCHOOL' AND g.school_id = me.school_id)
        OR (p_scope = 'CLASS'  AND u.class_id  = me.class_id)
     ORDER BY (u.id = ANY(p_exclude)), random()
     LIMIT 4
$$;

REVOKE ALL ON FUNCTION public.pick_candidates(bigint, public.question_scope, bigint[]) FROM public;


-- ---------------------------------------------------------------------
-- 3. 실제로 쓸 스코프 결정 (내부용)
-- ---------------------------------------------------------------------
-- 요청 스코프에서 후보가 4명이 안 되면 CLASS → SCHOOL → GLOBAL 로 낮춘다.
-- GLOBAL 에서도 모자라면 NULL — 그 질문은 내지 않는다.
CREATE OR REPLACE FUNCTION public.effective_scope(
    p_user bigint, p_scope public.question_scope)
RETURNS public.question_scope
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE v_scope public.question_scope := p_scope;
BEGIN
    LOOP
        IF (SELECT count(*) FROM public.pick_candidates(p_user, v_scope)) >= 4 THEN
            RETURN v_scope;
        END IF;
        IF    v_scope = 'CLASS'  THEN v_scope := 'SCHOOL';
        ELSIF v_scope = 'SCHOOL' THEN v_scope := 'GLOBAL';
        ELSE  RETURN NULL;
        END IF;
    END LOOP;
END;
$$;

REVOKE ALL ON FUNCTION public.effective_scope(bigint, public.question_scope) FROM public;


-- ---------------------------------------------------------------------
-- 4. 투표 세션 시작
-- ---------------------------------------------------------------------
-- 질문 10개와 각 질문의 후보 4명을 한 번에 만든다.
-- 진행 중인 세션이 있으면 새로 만들지 않고 그것을 돌려준다 — 새로고침이나
-- 중복 클릭으로 반쯤 푼 세션이 버려지지 않게.
CREATE OR REPLACE FUNCTION public.start_vote_session()
RETURNS bigint
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me      bigint := public.current_app_user_id();
    v_session bigint;
    v_item    bigint;
    v_scope   public.question_scope;
    v_pos     smallint := 0;
    r         record;
BEGIN
    IF v_me IS NULL THEN
        RAISE EXCEPTION '먼저 프로필을 만들어 주세요' USING ERRCODE = '28000';
    END IF;

    -- 5명 게이트. 후보 풀의 하한을 보장하는 장치다.
    IF NOT EXISTS (SELECT 1 FROM public.app_user
                    WHERE id = v_me AND service_unlocked_at IS NOT NULL) THEN
        RAISE EXCEPTION '친구를 5명 모으면 투표가 열립니다' USING ERRCODE = '42501';
    END IF;

    SELECT s.id INTO v_session
      FROM public.vote_session s
     WHERE s.user_id = v_me AND s.status = 'IN_PROGRESS'
     ORDER BY s.id DESC LIMIT 1;
    IF FOUND THEN
        RETURN v_session;
    END IF;

    INSERT INTO public.vote_session (user_id, item_count)
    VALUES (v_me, 0) RETURNING id INTO v_session;

    -- 후보가 모자라 건너뛰는 질문이 있으므로 넉넉히 뽑아 훑는다.
    FOR r IN SELECT q.id, q.scope FROM public.question q
              WHERE q.status = 'ACTIVE' ORDER BY random() LIMIT 40
    LOOP
        EXIT WHEN v_pos >= 10;

        v_scope := public.effective_scope(v_me, r.scope);
        CONTINUE WHEN v_scope IS NULL;

        v_pos := v_pos + 1;
        INSERT INTO public.vote_item
            (session_id, user_id, question_id, candidate_scope, position)
        VALUES (v_session, v_me, r.id, v_scope, v_pos)
        RETURNING id INTO v_item;

        INSERT INTO public.vote_candidate (vote_item_id, candidate_user_id, shuffle_round, slot)
        SELECT v_item, c.candidate_user_id, 0, row_number() OVER ()
          FROM public.pick_candidates(v_me, v_scope) c;
    END LOOP;

    IF v_pos = 0 THEN
        RAISE EXCEPTION '후보가 4명 이상 모이는 질문이 없습니다. 친구를 더 모아 주세요'
            USING ERRCODE = 'P0002';
    END IF;

    UPDATE public.vote_session SET item_count = v_pos WHERE id = v_session;
    RETURN v_session;
END;
$$;

REVOKE ALL ON FUNCTION public.start_vote_session() FROM public;
GRANT EXECUTE ON FUNCTION public.start_vote_session() TO authenticated;


-- ---------------------------------------------------------------------
-- 5. 투표 제출
-- ---------------------------------------------------------------------
-- 돌려주는 값은 내가 받은 하트다.
CREATE OR REPLACE FUNCTION public.submit_vote(
    p_item_id bigint, p_candidate_user_id bigint)
RETURNS int
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me       bigint := public.current_app_user_id();
    v_question bigint;
    v_round    smallint;
    v_reward   int;
BEGIN
    SELECT v.question_id, v.shuffle_count INTO v_question, v_round
      FROM public.vote_item v
     WHERE v.id = p_item_id AND v.user_id = v_me AND v.voted_at IS NULL;

    IF NOT FOUND THEN
        RAISE EXCEPTION '이미 투표했거나 없는 문항입니다' USING ERRCODE = 'P0002';
    END IF;

    -- 화면에 떠 있던 4명 중에서만 고를 수 있다. 후보가 아닌 사람의 id 를
    -- 밀어넣어 아무나 지목하는 것을 막는다.
    UPDATE public.vote_candidate
       SET is_chosen = true
     WHERE vote_item_id = p_item_id
       AND shuffle_round = v_round
       AND candidate_user_id = p_candidate_user_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION '후보에 없는 사람입니다' USING ERRCODE = '23514';
    END IF;

    UPDATE public.vote_item SET voted_at = now() WHERE id = p_item_id;

    INSERT INTO public.vote_received (vote_item_id, voter_id, receiver_id, question_id)
    VALUES (p_item_id, v_me, p_candidate_user_id, v_question);

    -- 5~15 개. 투표자와 지목당한 사람 양쪽에 준다(구 서비스 실측).
    v_reward := 5 + floor(random() * 11)::int;
    PERFORM public.grant_hearts(v_me, v_reward, 'VOTE_REWARD', p_item_id);
    PERFORM public.grant_hearts(p_candidate_user_id, 5 + floor(random() * 11)::int,
                                'VOTE_REWARD', p_item_id);

    -- 남은 문항이 없으면 세션을 닫는다
    UPDATE public.vote_session s
       SET status = 'COMPLETED', completed_at = now()
     WHERE s.id = (SELECT session_id FROM public.vote_item WHERE id = p_item_id)
       AND NOT EXISTS (SELECT 1 FROM public.vote_item v
                        WHERE v.session_id = s.id AND v.voted_at IS NULL);

    RETURN v_reward;
END;
$$;

REVOKE ALL ON FUNCTION public.submit_vote(bigint, bigint) FROM public;
GRANT EXECUTE ON FUNCTION public.submit_vote(bigint, bigint) TO authenticated;


-- ---------------------------------------------------------------------
-- 6. 셔플 (문항당 1회)
-- ---------------------------------------------------------------------
-- 1회 제한은 이 함수가 아니라 DB 가 강제한다:
--   vote_shuffle.vote_item_id 가 UNIQUE 이고, vote_item.shuffle_count 에
--   CHECK (0~1) 이 걸려 있다. 함수가 틀려도 두 번은 들어가지 않는다.
--
-- 광고는 MVP 에서 스텁이다(3초 대기는 화면이 처리한다). 그래도 ad_impression
-- 행은 남긴다 — vote_shuffle.ad_impression_id 가 NOT NULL 이라 "광고 없이
-- 셔플한 기록"은 애초에 존재할 수 없는 구조이기 때문이다.
CREATE OR REPLACE FUNCTION public.shuffle_candidates(p_item_id bigint)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me    bigint := public.current_app_user_id();
    v_scope public.question_scope;
    v_ad    bigint;
    v_prev  bigint[];
BEGIN
    SELECT v.candidate_scope INTO v_scope
      FROM public.vote_item v
     WHERE v.id = p_item_id AND v.user_id = v_me
       AND v.voted_at IS NULL AND v.shuffle_count = 0;

    IF NOT FOUND THEN
        RAISE EXCEPTION '셔플할 수 없는 문항입니다 (이미 셔플했거나 투표를 마쳤습니다)'
            USING ERRCODE = 'P0002';
    END IF;

    INSERT INTO public.ad_impression
        (user_id, placement, ad_network, ad_unit_id, status, completed_at)
    VALUES (v_me, 'VOTE_SHUFFLE', 'STUB', 'stub-vote-shuffle', 'COMPLETED', now())
    RETURNING id INTO v_ad;

    INSERT INTO public.vote_shuffle (vote_item_id, ad_impression_id)
    VALUES (p_item_id, v_ad);

    UPDATE public.vote_item SET shuffle_count = 1 WHERE id = p_item_id;

    SELECT array_agg(c.candidate_user_id) INTO v_prev
      FROM public.vote_candidate c
     WHERE c.vote_item_id = p_item_id AND c.shuffle_round = 0;

    INSERT INTO public.vote_candidate (vote_item_id, candidate_user_id, shuffle_round, slot)
    SELECT p_item_id, c.candidate_user_id, 1, row_number() OVER ()
      FROM public.pick_candidates(v_me, v_scope, coalesce(v_prev, '{}')) c;
END;
$$;

REVOKE ALL ON FUNCTION public.shuffle_candidates(bigint) FROM public;
GRANT EXECUTE ON FUNCTION public.shuffle_candidates(bigint) TO authenticated;


-- ---------------------------------------------------------------------
-- 7. 직접 쓰기를 닫는다
-- ---------------------------------------------------------------------
-- RLS 에 INSERT 정책이 없어 이미 막혀 있지만, 투표 기록을 만드는 경로가
-- 위 함수뿐임을 권한으로도 못박는다. 읽기(SELECT)는 그대로 둔다.
REVOKE INSERT, UPDATE, DELETE ON public.vote_session   FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.vote_item      FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.vote_candidate FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.vote_shuffle   FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.vote_received  FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.ad_impression  FROM authenticated;
