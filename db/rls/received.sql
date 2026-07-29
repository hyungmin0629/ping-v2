-- =====================================================================
-- received.sql · 받은 투표 · 힌트 구매 (W6)
-- =====================================================================
-- 이 서비스의 수익 구조가 실제로 도는 자리다.
-- "누가 나를 뽑았는가"(vote_received.voter_id)를 하트로 파는 것이 전부이므로,
-- 그 컬럼이 값을 치르기 전에 새어 나가면 서비스가 성립하지 않는다.
--
-- 힌트 단계 (4단계, 구 서비스 실측 누진 요금):
--   1  GENDER     성별             200
--   2  INITIAL    닉네임 초성      300
--   3  CLASS      상대의 반        500
--   4  FULL_NAME  닉네임 전체     1000
--
--   성별을 먼저 여는 이유: 초성보다 좁히는 폭이 작아 첫 단계로 적당하다.
--   초성은 후보를 몇 명으로 줄여버려서, 그다음 단계를 살 이유가 약해진다.
--
--   온보딩에서 성별을 받기로 하면서(2026-07-29) GENDER 단계를 되살렸다.
--   성별이 비어 있던 동안에는 팔 수 있는 정보가 아니라 3단계로 줄여두었다.
--
-- 하트가 모자라면 구매가 막힌다. 확인은 잔액 검사와 CHECK(heart_balance >= 0)
-- 두 겹으로 한다 — 함수가 틀려도 음수 잔액은 DB 가 거부한다.
--
-- 재실행해도 안전하다.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. 내가 받은 투표 (뷰 갱신)
-- ---------------------------------------------------------------------
-- reveal_status 는 그대로 두고, 산 힌트 단계에 따라 컬럼을 하나씩 더 연다.
-- 뷰가 유일한 통로다. vote_received 테이블 자체는 정책이 없어 직접 못 읽는다.
--
-- CREATE OR REPLACE 로는 컬럼을 추가할 수 없어(순서가 바뀐다) 지우고 다시 만든다.
DROP VIEW IF EXISTS public.my_vote_received;
CREATE VIEW public.my_vote_received
WITH (security_invoker = false) AS
SELECT
    r.id,
    r.question_id,
    r.is_read,
    r.read_at,
    r.reveal_status,
    r.answer_status,
    r.answered_at,
    r.created_at,
    h.steps AS hint_steps,
    -- 완전히 공개된 경우에만 실제 투표자를 알려준다
    CASE WHEN r.reveal_status = 'REVEALED' THEN r.voter_id END        AS voter_id,
    CASE WHEN r.reveal_status = 'REVEALED' THEN v.nickname END        AS voter_nickname,
    -- 1단계: 성별
    CASE WHEN h.steps >= 1 OR r.reveal_status IN ('PARTIAL', 'REVEALED')
         THEN v.gender END                                            AS voter_gender,
    -- 2단계: 초성
    CASE WHEN h.steps >= 2 OR r.reveal_status = 'REVEALED'
         THEN left(v.nickname, 1) END                                 AS voter_initial,
    -- 3단계: 반
    CASE WHEN h.steps >= 3 OR r.reveal_status = 'REVEALED'
         THEN v.class_id END                                          AS voter_class_id
FROM public.vote_received r
JOIN public.app_user v ON v.id = r.voter_id
CROSS JOIN LATERAL (
    SELECT count(*)::int AS steps
      FROM public.hint_purchase p
     WHERE p.vote_received_id = r.id
) h
WHERE r.receiver_id = public.current_app_user_id();

GRANT SELECT ON public.my_vote_received TO authenticated;


-- ---------------------------------------------------------------------
-- 2. 내가 한 투표 (뷰)
-- ---------------------------------------------------------------------
-- 내가 누구를 뽑았는지는 내 기록이라 가릴 이유가 없다.
-- 상대에게는 여전히 비밀이다 — 그쪽에서는 위 my_vote_received 로만 보인다.
CREATE OR REPLACE VIEW public.my_vote_history
WITH (security_invoker = false) AS
SELECT
    v.id AS vote_item_id,
    v.voted_at,
    v.candidate_scope,
    q.text AS question_text,
    c.candidate_user_id AS chosen_user_id,
    u.nickname          AS chosen_nickname
FROM public.vote_item v
JOIN public.question q       ON q.id = v.question_id
JOIN public.vote_candidate c ON c.vote_item_id = v.id AND c.is_chosen
JOIN public.app_user u       ON u.id = c.candidate_user_id
WHERE v.user_id = public.current_app_user_id()
  AND v.voted_at IS NOT NULL;

GRANT SELECT ON public.my_vote_history TO authenticated;


-- ---------------------------------------------------------------------
-- 3. 읽음 처리
-- ---------------------------------------------------------------------
-- ck_read_flag 가 is_read 와 read_at 을 함께 두도록 강제한다.
CREATE OR REPLACE FUNCTION public.mark_received_read(p_received_id bigint)
RETURNS void
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
    UPDATE public.vote_received
       SET is_read = true, read_at = coalesce(read_at, now())
     WHERE id = p_received_id
       AND receiver_id = public.current_app_user_id()
       AND NOT is_read
$$;

REVOKE ALL ON FUNCTION public.mark_received_read(bigint) FROM public;
GRANT EXECUTE ON FUNCTION public.mark_received_read(bigint) TO authenticated;


-- ---------------------------------------------------------------------
-- 4. 힌트 구매
-- ---------------------------------------------------------------------
-- 돌려주는 값은 이번에 산 단계다(1~3). 화면은 이 값을 보고 뷰를 다시 읽는다.
CREATE OR REPLACE FUNCTION public.buy_hint(p_received_id bigint)
RETURNS int
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me      bigint := public.current_app_user_id();
    v_step    int;
    v_cost    int;
    v_type    public.hint_type;
    v_hint    bigint;
    v_balance bigint;
BEGIN
    -- 동시에 두 번 눌러도 한 단계만 사지도록 행을 잠근다
    PERFORM 1 FROM public.vote_received r
      WHERE r.id = p_received_id AND r.receiver_id = v_me
      FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION '내가 받은 투표가 아닙니다' USING ERRCODE = 'P0002';
    END IF;

    SELECT count(*) + 1 INTO v_step
      FROM public.hint_purchase p WHERE p.vote_received_id = p_received_id;

    IF v_step > 4 THEN
        RAISE EXCEPTION '더 살 힌트가 없습니다' USING ERRCODE = 'P0002';
    END IF;

    v_cost := (ARRAY[200, 300, 500, 1000])[v_step];
    v_type := (ARRAY['GENDER', 'INITIAL', 'CLASS', 'FULL_NAME']::public.hint_type[])[v_step];

    SELECT heart_balance INTO v_balance
      FROM public.app_user WHERE id = v_me FOR UPDATE;
    IF v_balance < v_cost THEN
        RAISE EXCEPTION '하트가 부족합니다 (필요 %, 보유 %)', v_cost, v_balance
            USING ERRCODE = '23514';
    END IF;

    INSERT INTO public.hint_purchase (vote_received_id, user_id, hint_type, step, heart_cost)
    VALUES (p_received_id, v_me, v_type, v_step, v_cost)
    RETURNING id INTO v_hint;

    -- 차감과 원장을 함께 쓴다. 원장은 hint_purchase 를 가리켜야 한다
    -- ('원장 없는 힌트 구매'가 정합성 검사 항목이다).
    UPDATE public.app_user
       SET heart_balance = heart_balance - v_cost, updated_at = now()
     WHERE id = v_me
    RETURNING heart_balance INTO v_balance;

    INSERT INTO public.heart_transaction
        (user_id, type_code, delta, balance_after, hint_purchase_id)
    VALUES (v_me, 'HINT_PURCHASE', -v_cost, v_balance, v_hint);

    UPDATE public.vote_received
       -- CASE 의 두 갈래가 모두 문자열 상수라 타입이 text 로 정해진다. 명시적으로 캐스트한다.
       SET reveal_status = (CASE WHEN v_step >= 4 THEN 'REVEALED' ELSE 'PARTIAL' END)::public.reveal_status
     WHERE id = p_received_id;

    RETURN v_step;
END;
$$;

REVOKE ALL ON FUNCTION public.buy_hint(bigint) FROM public;
GRANT EXECUTE ON FUNCTION public.buy_hint(bigint) TO authenticated;


-- ---------------------------------------------------------------------
-- 5. 답변 공개 여부
-- ---------------------------------------------------------------------
-- 지목받은 사람이 "이거 받았다"를 공개할지 정한다.
CREATE OR REPLACE FUNCTION public.set_answer_status(
    p_received_id bigint, p_status public.answer_status)
RETURNS void
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
    UPDATE public.vote_received
       SET answer_status = p_status,
           answered_at = CASE WHEN p_status = 'NONE' THEN NULL ELSE now() END
     WHERE id = p_received_id
       AND receiver_id = public.current_app_user_id()
$$;

REVOKE ALL ON FUNCTION public.set_answer_status(bigint, public.answer_status) FROM public;
GRANT EXECUTE ON FUNCTION public.set_answer_status(bigint, public.answer_status) TO authenticated;


-- ---------------------------------------------------------------------
-- 6. 직접 쓰기를 닫는다
-- ---------------------------------------------------------------------
-- 힌트를 공짜로 만들 수 있으면 수익 구조가 통째로 무너진다.
REVOKE INSERT, UPDATE, DELETE ON public.hint_purchase FROM authenticated;
