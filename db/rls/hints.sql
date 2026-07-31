-- =====================================================================
-- hints.sql · 선택형 힌트 (W14)
-- =====================================================================
-- received.sql 의 순차 4단계(buy_hint)를 대체한다.
--
--   기본 5종 · 각 20하트 · 아무 순서로나
--     GENDER   성별   (광고 30초로도 열 수 있다. 하루 한 번)
--     INITIAL  초성 ┐
--     MEDIAL   중성 ├ 같은 한 글자를 가리킨다. 셋을 다 사면 글자가 완성된다
--     FINAL    종성 ┘
--     CLASS    반
--
--   FULL_NAME  이름 공개 · 100하트 · **기본 5종 중 3개 이상**을 연 뒤에만
--
-- 값 계산은 전부 여기서 한다. 뷰가 아직 안 산 자모를 내보내면 화면에서
-- 숨겨도 소용없다 — 이미 브라우저에 가 있기 때문이다. (hangul.sql)
--
-- 재실행해도 안전하다.
-- =====================================================================

-- 값이 코드 여러 곳에 흩어지면 어긋난다. 한 군데서만 정한다.
CREATE OR REPLACE FUNCTION public.hint_cost(p_type public.hint_type)
RETURNS int LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN p_type = 'FULL_NAME' THEN 100 ELSE 20 END
$$;

CREATE OR REPLACE FUNCTION public.hint_unlock_min()
RETURNS int LANGUAGE sql IMMUTABLE AS $$ SELECT 3 $$;


-- ---------------------------------------------------------------------
-- 1. 내가 받은 투표 — 산 만큼만 보인다
-- ---------------------------------------------------------------------
DROP VIEW IF EXISTS public.my_vote_received;
CREATE VIEW public.my_vote_received
WITH (security_invoker = false) AS
WITH bought AS (
    SELECT h.vote_received_id,
           bool_or(h.hint_type = 'GENDER')    AS has_gender,
           bool_or(h.hint_type = 'INITIAL')   AS has_lead,
           bool_or(h.hint_type = 'MEDIAL')    AS has_vowel,
           bool_or(h.hint_type = 'FINAL')     AS has_tail,
           bool_or(h.hint_type = 'CLASS')     AS has_class,
           bool_or(h.hint_type = 'FULL_NAME') AS has_name,
           count(*) FILTER (WHERE h.hint_type <> 'FULL_NAME') AS basic_count
      FROM public.hint_purchase h
     GROUP BY h.vote_received_id
)
SELECT
    r.id,
    r.question_id,
    q.text                                    AS question_text,
    r.is_read,
    r.read_at,
    r.answer_status,
    r.created_at,

    coalesce(b.has_gender, false)             AS has_gender,
    coalesce(b.has_lead,   false)             AS has_lead,
    coalesce(b.has_vowel,  false)             AS has_vowel,
    coalesce(b.has_tail,   false)             AS has_tail,
    coalesce(b.has_class,  false)             AS has_class,
    coalesce(b.has_name,   false)             AS has_name,
    coalesce(b.basic_count, 0)::int           AS basic_count,
    (coalesce(b.basic_count, 0) >= public.hint_unlock_min()) AS can_unlock_name,

    -- 산 것만 값이 나간다. 안 산 것은 NULL 이다.
    CASE WHEN b.has_gender THEN v.gender END  AS voter_gender,
    CASE WHEN b.has_class  THEN g.grade    END AS voter_grade,
    CASE WHEN b.has_class  THEN g.class_num END AS voter_class_num,
    CASE WHEN b.has_name   THEN v.nickname END AS voter_nickname,

    -- 이름 마스킹. 이름을 샀으면 그대로, 아니면 산 자모만 드러난다.
    CASE WHEN b.has_name THEN v.nickname
         ELSE public.mask_nickname(v.nickname, r.hint_char_index,
                                   coalesce(b.has_lead, false),
                                   coalesce(b.has_vowel, false),
                                   coalesce(b.has_tail, false))
    END                                       AS voter_name_masked,

    -- ⚠️ voter_id 는 이름을 산 뒤에만 나간다. 이게 유료 정보의 핵심이다.
    CASE WHEN b.has_name THEN r.voter_id END  AS voter_id
FROM public.vote_received r
JOIN public.question  q ON q.id = r.question_id
JOIN public.app_user  v ON v.id = r.voter_id
JOIN public.grade_class g ON g.id = v.class_id
LEFT JOIN bought b ON b.vote_received_id = r.id
WHERE r.receiver_id = public.current_app_user_id();

GRANT SELECT ON public.my_vote_received TO authenticated;


-- ---------------------------------------------------------------------
-- 2. 힌트 사기
-- ---------------------------------------------------------------------
-- 광고로 여는 경로(p_ad_impression_id)는 GENDER 에만 열려 있고 하루 한 번이다.
CREATE OR REPLACE FUNCTION public.buy_hint(
    p_received_id bigint,
    p_hint_type   public.hint_type,
    p_ad_impression_id bigint DEFAULT NULL
)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me      bigint := public.current_app_user_id();
    v_nick    text;
    v_cost    int;
    v_basic   int;
    v_order   int;
    v_after   bigint;
    v_hint    bigint;
BEGIN
    IF v_me IS NULL THEN
        RAISE EXCEPTION '먼저 프로필을 만들어 주세요' USING ERRCODE = '28000';
    END IF;

    -- 내가 받은 투표인지 확인한다. id 는 순번이라 찍어볼 수 있다.
    SELECT u.nickname INTO v_nick
      FROM public.vote_received r
      JOIN public.app_user u ON u.id = r.voter_id
     WHERE r.id = p_received_id AND r.receiver_id = v_me;
    IF NOT FOUND THEN
        RETURN 'NOT_FOUND';
    END IF;

    IF EXISTS (SELECT 1 FROM public.hint_purchase
                WHERE vote_received_id = p_received_id AND hint_type = p_hint_type) THEN
        RETURN 'ALREADY';
    END IF;

    SELECT count(*) INTO v_basic FROM public.hint_purchase
     WHERE vote_received_id = p_received_id AND hint_type <> 'FULL_NAME';

    -- 이름은 기본 힌트를 충분히 연 뒤에만 살 수 있다.
    IF p_hint_type = 'FULL_NAME' AND v_basic < public.hint_unlock_min() THEN
        RETURN 'NEED_MORE';
    END IF;

    v_cost := public.hint_cost(p_hint_type);

    -- 광고로 여는 길. 성별만, 하루 한 번, 완료된 광고여야 한다.
    IF p_ad_impression_id IS NOT NULL THEN
        IF p_hint_type <> 'GENDER' THEN
            RETURN 'AD_NOT_ALLOWED';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM public.ad_impression a
             WHERE a.id = p_ad_impression_id AND a.user_id = v_me
               AND a.status = 'COMPLETED' AND a.placement = 'HINT_UNLOCK') THEN
            RETURN 'AD_INVALID';
        END IF;
        IF EXISTS (
            SELECT 1 FROM public.hint_purchase h
             WHERE h.user_id = v_me AND h.ad_impression_id IS NOT NULL
               AND (h.created_at AT TIME ZONE 'Asia/Seoul')::date
                 = (now()        AT TIME ZONE 'Asia/Seoul')::date) THEN
            RETURN 'AD_USED_TODAY';
        END IF;
        v_cost := 0;
    ELSE
        IF (SELECT heart_balance FROM public.app_user WHERE id = v_me) < v_cost THEN
            RETURN 'NOT_ENOUGH';
        END IF;
    END IF;

    -- 자모 힌트를 처음 살 때 어느 글자를 가리킬지 정한다. 한 번 정하면
    -- 바꾸지 않는다 — 닉네임이 바뀌어도 이미 산 힌트가 흔들리면 안 된다.
    IF p_hint_type IN ('INITIAL', 'MEDIAL', 'FINAL') THEN
        UPDATE public.vote_received
           SET hint_char_index = floor(random() * greatest(char_length(v_nick), 1))::smallint
         WHERE id = p_received_id AND hint_char_index IS NULL;
    END IF;

    SELECT count(*) + 1 INTO v_order FROM public.hint_purchase
     WHERE vote_received_id = p_received_id;

    INSERT INTO public.hint_purchase
        (vote_received_id, user_id, hint_type, step, heart_cost, ad_impression_id)
    VALUES
        (p_received_id, v_me, p_hint_type, v_order, v_cost, p_ad_impression_id)
    RETURNING id INTO v_hint;

    -- 하트를 쓴 경우에만 잔액과 원장을 건드린다.
    IF v_cost > 0 THEN
        UPDATE public.app_user
           SET heart_balance = heart_balance - v_cost
         WHERE id = v_me
        RETURNING heart_balance INTO v_after;

        INSERT INTO public.heart_transaction
            (user_id, type_code, delta, balance_after, hint_purchase_id)
        VALUES (v_me, 'HINT_PURCHASE', -v_cost, v_after, v_hint);
    END IF;

    -- reveal_status 는 화면이 쓰지 않지만 분석과 정합성 검사가 본다.
    UPDATE public.vote_received
       SET reveal_status = (CASE WHEN p_hint_type = 'FULL_NAME'
                                 THEN 'REVEALED' ELSE 'PARTIAL' END)::public.reveal_status
     WHERE id = p_received_id
       AND reveal_status <> 'REVEALED';

    RETURN 'OK';
END;
$$;


-- ---------------------------------------------------------------------
-- 3. 광고 시청 기록
-- ---------------------------------------------------------------------
-- MVP 의 광고는 스텁이다(30초 대기). 그래도 기록은 진짜로 남긴다 —
-- "광고를 보고 여는 사람이 얼마나 되나"가 이 기능을 넣은 이유이기 때문이다.
CREATE OR REPLACE FUNCTION public.start_hint_ad()
RETURNS bigint
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE v_me bigint := public.current_app_user_id(); v_id bigint;
BEGIN
    IF v_me IS NULL THEN
        RAISE EXCEPTION '먼저 프로필을 만들어 주세요' USING ERRCODE = '28000';
    END IF;
    INSERT INTO public.ad_impression (user_id, placement, ad_network, ad_unit_id, status)
    VALUES (v_me, 'HINT_UNLOCK', 'STUB', 'mvp-hint-30s', 'STARTED')
    RETURNING id INTO v_id;
    RETURN v_id;
END;
$$;

CREATE OR REPLACE FUNCTION public.complete_hint_ad(p_ad_id bigint)
RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE v_me bigint := public.current_app_user_id();
BEGIN
    UPDATE public.ad_impression
       SET status = 'COMPLETED', completed_at = now()
     WHERE id = p_ad_id AND user_id = v_me AND status = 'STARTED';
    RETURN FOUND;
END;
$$;


-- ---------------------------------------------------------------------
-- 4. 오늘 광고로 열 수 있는가
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW public.my_hint_ad_state
WITH (security_invoker = false) AS
SELECT NOT EXISTS (
    SELECT 1 FROM public.hint_purchase h
     WHERE h.user_id = public.current_app_user_id()
       AND h.ad_impression_id IS NOT NULL
       AND (h.created_at AT TIME ZONE 'Asia/Seoul')::date
         = (now()        AT TIME ZONE 'Asia/Seoul')::date
) AS ad_available;

GRANT SELECT ON public.my_hint_ad_state TO authenticated;


-- ---------------------------------------------------------------------
-- 5. 권한
-- ---------------------------------------------------------------------
REVOKE ALL ON FUNCTION public.hint_cost(public.hint_type)                    FROM public;
REVOKE ALL ON FUNCTION public.hint_unlock_min()                              FROM public;
REVOKE ALL ON FUNCTION public.buy_hint(bigint, public.hint_type, bigint)     FROM public;
REVOKE ALL ON FUNCTION public.start_hint_ad()                                FROM public;
REVOKE ALL ON FUNCTION public.complete_hint_ad(bigint)                       FROM public;

GRANT EXECUTE ON FUNCTION public.buy_hint(bigint, public.hint_type, bigint)  TO authenticated;
GRANT EXECUTE ON FUNCTION public.start_hint_ad()                             TO authenticated;
GRANT EXECUTE ON FUNCTION public.complete_hint_ad(bigint)                    TO authenticated;

-- 옛 순차 힌트 함수는 지운다. 남겨두면 20하트를 우회해 200하트짜리 옛 경로가 돈다.
DROP FUNCTION IF EXISTS public.buy_hint(bigint);

REVOKE INSERT, UPDATE, DELETE ON public.hint_purchase  FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.ad_impression  FROM authenticated;
