-- =====================================================================
-- onboarding.sql · 온보딩 RPC (W3)
-- =====================================================================
-- 왜 RPC 인가:
--   온보딩은 app_user 행을 만드는 일이다. 그런데 브라우저에 INSERT 를 열어주면
--   같은 문장에 heart_balance 나 is_synthetic 을 끼워 넣을 수 있다.
--   RLS 는 행 단위라 "이 컬럼만 넣어라"를 막지 못하고, 컬럼 단위 INSERT 권한을
--   따로 주는 방법도 있지만 그러면 초대 코드를 클라이언트가 만들어야 한다
--   — 중복 재시도와 코드 규칙이 브라우저로 새어나간다.
--
--   그래서 쓰기는 이 함수 하나로만 연다. 정한 컬럼 외에는 손댈 수 없고,
--   초대 코드 생성·중복 재시도·가입 하트 지급이 한 트랜잭션 안에서 끝난다.
--
-- 가입 하트를 여기서 같이 주는 이유:
--   구 서비스 최대 결함이 "원장과 잔액 불일치"였다. 잔액을 만드는 순간
--   원장도 같이 만들어야 어긋날 여지가 없다. 지급액 300 은 구 서비스 실측
--   최빈값이다(generator/config/distribution.yaml · signup_grant).
--
-- 재실행해도 안전하다.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. 초대 코드 생성
-- ---------------------------------------------------------------------
-- 헷갈리는 글자(0/O, 1/I/L)를 뺀 32글자에서 8자를 뽑는다.
-- DDL 의 ck_invite_code 제약(^[A-HJ-NP-Z2-9]{6,8}$)과 같은 문자 집합이다.
-- 코드를 불러주거나 받아 적는 상황을 전제하기 때문이다.
CREATE OR REPLACE FUNCTION public.gen_invite_code()
RETURNS text
LANGUAGE sql VOLATILE SET search_path = ''
AS $$
    SELECT string_agg(
        substr('ABCDEFGHJKLMNPQRSTUVWXYZ23456789',
               1 + floor(random() * 32)::int, 1), '')
    FROM generate_series(1, 8)
$$;

-- 아무도 직접 부를 필요가 없다. 아래 complete_onboarding 안에서만 쓴다.
REVOKE ALL ON FUNCTION public.gen_invite_code() FROM public;


-- ---------------------------------------------------------------------
-- 2. 온보딩 완료
-- ---------------------------------------------------------------------
-- 닉네임과 소속을 받아 내 계정을 만들고, 만들어진 행을 그대로 돌려준다.
-- 자기 행이므로 전체 컬럼을 돌려줘도 새는 정보가 없다(read_own_user 와 같은 범위).
CREATE OR REPLACE FUNCTION public.complete_onboarding(
    p_nickname text,
    p_class_id bigint,
    p_gender   public.gender_type DEFAULT NULL
)
RETURNS public.app_user
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_auth uuid := auth.uid();
    v_nick text := btrim(p_nickname);
    v_row  public.app_user;
BEGIN
    IF v_auth IS NULL THEN
        RAISE EXCEPTION '로그인이 필요합니다' USING ERRCODE = '28000';
    END IF;

    -- 이미 온보딩한 계정이면 기존 행을 그대로 준다.
    -- 화면이 두 번 호출하거나 새로고침 중에 다시 불려도 계정이 둘로 갈라지지 않는다.
    SELECT * INTO v_row FROM public.app_user u WHERE u.auth_user_id = v_auth;
    IF FOUND THEN
        RETURN v_row;
    END IF;

    IF char_length(v_nick) < 2 OR char_length(v_nick) > 20 THEN
        RAISE EXCEPTION '닉네임은 2~20자여야 합니다' USING ERRCODE = '22023';
    END IF;

    -- 성별은 필수다. 힌트로 파는 정보라 비어 있으면 살 수 있는 힌트가
    -- 한 단계 사라진다. 파라미터의 기본값은 예전 호출 형태를 위해 남겨두고
    -- 값 검사는 여기서 한다.
    IF p_gender IS NULL THEN
        RAISE EXCEPTION '성별을 선택해 주세요' USING ERRCODE = '22023';
    END IF;

    -- FK 도 잡아주지만, 화면에 보여줄 말이 되는 메시지가 필요하다.
    IF NOT EXISTS (SELECT 1 FROM public.grade_class g WHERE g.id = p_class_id) THEN
        RAISE EXCEPTION '없는 학급입니다' USING ERRCODE = '23503';
    END IF;

    -- 초대 코드 중복은 32^8 분의 1 수준이라 사실상 안 나지만,
    -- 나면 가입이 실패하는 자리라 재시도를 붙여둔다.
    FOR i IN 1..10 LOOP
        BEGIN
            INSERT INTO public.app_user
                (auth_user_id, nickname, invite_code, class_id, gender, is_synthetic)
            VALUES
                (v_auth, v_nick, public.gen_invite_code(), p_class_id, p_gender, false)
            RETURNING * INTO v_row;
            EXIT;
        EXCEPTION WHEN unique_violation THEN
            -- 같은 계정으로 동시에 두 번 들어온 경우다. 먼저 들어간 쪽을 쓴다.
            SELECT * INTO v_row FROM public.app_user u WHERE u.auth_user_id = v_auth;
            IF FOUND THEN
                RETURN v_row;
            END IF;
            v_row := NULL;   -- 초대 코드 충돌 → 다시 뽑는다
        END;
    END LOOP;

    IF v_row.id IS NULL THEN
        RAISE EXCEPTION '초대 코드를 만들지 못했습니다. 다시 시도해 주세요';
    END IF;

    -- 가입 하트: 잔액과 원장을 같은 트랜잭션에서 함께 만든다.
    UPDATE public.app_user
       SET heart_balance = 300, updated_at = now()
     WHERE id = v_row.id
    RETURNING * INTO v_row;

    INSERT INTO public.heart_transaction (user_id, type_code, delta, balance_after)
    VALUES (v_row.id, 'SIGNUP_GRANT', 300, 300);

    RETURN v_row;
END;
$$;

REVOKE ALL ON FUNCTION public.complete_onboarding(text, bigint, public.gender_type) FROM public;
GRANT EXECUTE ON FUNCTION public.complete_onboarding(text, bigint, public.gender_type) TO authenticated;


-- ---------------------------------------------------------------------
-- 3. 직접 INSERT 를 닫는다
-- ---------------------------------------------------------------------
-- 위 함수가 유일한 가입 경로다. 정책만 지우면 테이블 권한이 남아 있으므로
-- 권한도 같이 회수한다. (policies.sql 의 insert_own_user 를 대체한다)
DROP POLICY IF EXISTS insert_own_user ON public.app_user;
REVOKE INSERT ON public.app_user FROM authenticated;
