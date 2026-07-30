-- =====================================================================
-- withdraw.sql · 계정 삭제 (W12)
-- =====================================================================
-- 행을 지우지 않는다. status 를 WITHDRAWN 으로 바꾸고 사유를 남긴다.
--
-- 왜 지우지 않는가:
--   구 서비스의 탈퇴 테이블은 70,764건(가입자의 10.5%)인데 유저 식별자가 없어
--   **누가 탈퇴했는지 특정할 수 없었다.** 탈퇴 사유를 유저 속성과 교차분석하는
--   것이 원천 봉쇄됐고, 사유의 57%가 "기타"라 실질 정보도 거의 없었다.
--   그 구멍을 닫으려고 user_withdrawal.user_id 를 NOT NULL FK 로 두고
--   자유 서술까지 받도록 설계했다([[DECISIONS]]). 지우면 그 설계가 무의미해진다.
--
--   "언제 왜 그만뒀는가"는 이 프로젝트가 얻으려는 데이터 그 자체다.
--
-- 그럼 이용자에게는 무엇이 달라지나:
--   * 친구 목록·추천·투표 후보에서 사라진다 (전부 status = 'ACTIVE' 를 본다)
--   * 게시판에 남긴 글의 이름이 "탈퇴한 사용자" 로 바뀐다 (board.sql)
--   * 로그인 연결이 끊겨 그 브라우저로 다시 들어올 수 없다
--
-- 글 자체는 지우지 않는다. 댓글이 달린 글을 지우면 남의 대화까지 사라진다.
--
-- 재실행해도 안전하다.
-- =====================================================================

CREATE OR REPLACE FUNCTION public.withdraw_account(
    p_reason_code text,
    p_reason_text text DEFAULT NULL
)
RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE v_me bigint := public.current_app_user_id();
BEGIN
    IF v_me IS NULL THEN
        RAISE EXCEPTION '로그인이 필요합니다' USING ERRCODE = '28000';
    END IF;

    -- 사유는 마스터에 있는 값만 받는다. 자유 문자열로 두면 구 서비스처럼
    -- "기타 이유"와 "기타"가 따로 쌓인다.
    IF NOT EXISTS (SELECT 1 FROM public.withdrawal_reason
                    WHERE code = p_reason_code AND is_active) THEN
        RAISE EXCEPTION '탈퇴 사유를 골라 주세요' USING ERRCODE = '22023';
    END IF;

    -- 두 번 눌러도 기록이 둘로 갈라지지 않는다.
    INSERT INTO public.user_withdrawal (user_id, reason_code, reason_text)
    VALUES (v_me, p_reason_code, nullif(btrim(coalesce(p_reason_text, '')), ''));

    -- auth_user_id 를 끊는다. 그 브라우저로 다시 들어오면 새 계정이 된다.
    -- (auth_user_id 는 nullable 이다 — 더미 친구가 같은 구조를 쓴다)
    UPDATE public.app_user
       SET status = 'WITHDRAWN', auth_user_id = NULL
     WHERE id = v_me;

    RETURN true;
END;
$$;

REVOKE ALL ON FUNCTION public.withdraw_account(text, text) FROM public;
GRANT EXECUTE ON FUNCTION public.withdraw_account(text, text) TO authenticated;

-- 탈퇴 사유 목록은 화면이 읽어야 한다. 마스터 데이터라 공개해도 무방하다.
DROP POLICY IF EXISTS read_withdrawal_reason ON public.withdrawal_reason;
CREATE POLICY read_withdrawal_reason ON public.withdrawal_reason
    FOR SELECT TO authenticated USING (is_active);

-- 탈퇴 기록 자체는 열지 않는다. 남이 언제 왜 그만뒀는지는 볼 것이 아니다.
REVOKE INSERT, UPDATE, DELETE ON public.user_withdrawal FROM authenticated;


-- ---------------------------------------------------------------------
-- 남는 것 — 알고 두는 한계
-- ---------------------------------------------------------------------
-- 친구 관계(friendship)는 지우지 않는다. 지우면 상대의 friend_count 가 5 아래로
-- 떨어져 **남의 투표가 닫힌다.** 탈퇴한 사람은 friend_profile 에서 이미 사라지므로
-- 화면에는 안 보이고, 상대의 friend_count 만 실제보다 크게 남는다.
-- 이 값은 게이트 판정에만 쓰이고 게이트는 한 번 열리면 유지되므로 영향이 없다.
--
-- 정합성 검사의 "게이트 위반(친구<5인데 해금)" 이 이것 때문에 걸리지는 않는다
-- — friend_count 는 줄지 않기 때문이다.
