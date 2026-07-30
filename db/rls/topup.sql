-- =====================================================================
-- topup.sql · 하트 충전 (W13)
-- =====================================================================
-- ⚠️ **결제가 없다.** 누르면 그 자리에서 하트가 들어온다.
--    실결제(인앱결제)는 계정 개설과 심사가 필요해 MVP 범위 밖이다([[DECISIONS]]).
--    스키마는 실결제를 전제로 설계돼 있으므로 나중에 SDK 를 붙일 때
--    구조를 바꿀 필요가 없다 — 지금은 그 자리에 스텁이 들어간다.
--
-- 그래서 **가짜 매출이 진짜처럼 쌓이지 않게** 해야 한다.
--   store_transaction_id 에 'MVP-STUB-' 접두어를 남긴다.
--   매출을 볼 때 이 접두어로 거른다. 안 남기면 나중에 실결제가 섞였을 때
--   무엇이 진짜였는지 되짚을 방법이 없다.
--
-- 하루 한 번 제한:
--   결제가 없으므로 막지 않으면 하트가 무한이 된다. 그러면 힌트 가격도
--   하트 경제도 관찰할 수 없다 — 이 프로젝트가 보려는 것이 그것이다.
--   **어떤 상품을 골랐든** 그날은 더 살 수 없다. 한국 시간 날짜 기준이다.
--
-- 재실행해도 안전하다.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. 상품 라벨
-- ---------------------------------------------------------------------
-- 금액과 수량은 구 서비스 실측이라 그대로 둔다. 화면에 띄우는 라벨만 맞춘다.
UPDATE heart_product SET label = NULL       WHERE product_code = 'heart.777';
UPDATE heart_product SET label = '최고 인기'  WHERE product_code = 'heart.1000';
UPDATE heart_product SET label = '최고 가성비' WHERE product_code = 'heart.4000';


-- ---------------------------------------------------------------------
-- 2. 오늘 살 수 있는가
-- ---------------------------------------------------------------------
-- 날짜 계산을 화면에 두지 않는다. 브라우저 시간대는 이용자가 바꿀 수 있고,
-- 그러면 하루 한 번 제한이 시간대를 옮기는 것만으로 뚫린다.
CREATE OR REPLACE VIEW public.my_topup_state
WITH (security_invoker = false) AS
SELECT
    (SELECT max(p.created_at) FROM public.heart_purchase p
      WHERE p.user_id = public.current_app_user_id()
        AND p.status = 'SUCCESS')                             AS last_purchased_at,
    NOT EXISTS (
        SELECT 1 FROM public.heart_purchase p
         WHERE p.user_id = public.current_app_user_id()
           AND p.status = 'SUCCESS'
           AND (p.created_at AT TIME ZONE 'Asia/Seoul')::date
             = (now()        AT TIME ZONE 'Asia/Seoul')::date
    )                                                          AS can_purchase;

GRANT SELECT ON public.my_topup_state TO authenticated;


-- ---------------------------------------------------------------------
-- 3. 충전
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.purchase_hearts(p_product_code text)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me       bigint := public.current_app_user_id();
    v_product  public.heart_product;
    v_purchase bigint;
    v_after    bigint;
BEGIN
    IF v_me IS NULL THEN
        RAISE EXCEPTION '먼저 프로필을 만들어 주세요' USING ERRCODE = '28000';
    END IF;

    SELECT * INTO v_product FROM public.heart_product
     WHERE product_code = p_product_code AND is_active;
    IF NOT FOUND THEN
        RETURN 'NOT_FOUND';
    END IF;

    -- 하루 한 번. 상품을 가리지 않는다 — 제일 싼 것을 골라도 그날은 끝이다.
    IF EXISTS (
        SELECT 1 FROM public.heart_purchase p
         WHERE p.user_id = v_me AND p.status = 'SUCCESS'
           AND (p.created_at AT TIME ZONE 'Asia/Seoul')::date
             = (now()        AT TIME ZONE 'Asia/Seoul')::date
    ) THEN
        RETURN 'ALREADY_TODAY';
    END IF;

    -- 결제가 없으므로 곧바로 성공으로 남긴다.
    -- store_transaction_id 의 접두어가 이것이 스텁이라는 유일한 표시다.
    INSERT INTO public.heart_purchase
        (user_id, product_id, platform, store_transaction_id, status,
         price_krw, heart_amount, completed_at)
    VALUES
        (v_me, v_product.id, 'WEB',
         'MVP-STUB-' || gen_random_uuid()::text, 'SUCCESS',
         v_product.price_krw, v_product.heart_amount, now())
    RETURNING id INTO v_purchase;

    -- 잔액과 원장을 한 문장 간격 안에서 같이 쓴다. 구 시스템 최대 결함이
    -- 원장에 남지 않은 충전이었다 — 그 자리를 만들지 않는다.
    UPDATE public.app_user
       SET heart_balance = heart_balance + v_product.heart_amount
     WHERE id = v_me
    RETURNING heart_balance INTO v_after;

    INSERT INTO public.heart_transaction
        (user_id, type_code, delta, balance_after, purchase_id, memo)
    VALUES
        (v_me, 'TOPUP', v_product.heart_amount, v_after, v_purchase,
         'MVP 스텁 충전 — 실결제 아님');

    RETURN 'OK';
END;
$$;

REVOKE ALL ON FUNCTION public.purchase_hearts(text) FROM public;
GRANT EXECUTE ON FUNCTION public.purchase_hearts(text) TO authenticated;

-- 충전 기록은 RPC 로만 만든다. 열어주면 결제 없이 행을 만들어 하트를 얻는다.
REVOKE INSERT, UPDATE, DELETE ON public.heart_purchase FROM authenticated;
