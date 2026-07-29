-- =====================================================================
-- policies.sql · Row Level Security 정책
-- =====================================================================
-- 왜 필요한가:
--   Supabase 는 브라우저가 DB에 직접 말을 건다. 중간에 판단할 서버가 없다.
--   접속에 쓰이는 anon 키는 웹페이지 소스에 그대로 들어가므로 숨길 수 없다.
--   따라서 "이 사람이 이 행을 봐도 되는가"를 DB가 스스로 판단해야 한다.
--
-- 원칙:
--   1. 모든 테이블에 RLS 를 켠다. 정책이 없으면 아무것도 안 보인다(기본 거부).
--   2. 읽기는 꼭 필요한 것만 연다.
--   3. 쓰기는 거의 열지 않는다. 투표·하트처럼 규칙이 있는 조작은
--      나중에 RPC 함수(SECURITY DEFINER)로 처리한다. 클라이언트가
--      heart_balance 를 직접 UPDATE 할 수 있으면 안 되기 때문이다.
--
-- 가장 중요한 비밀:
--   vote_received.voter_id — "누가 나를 뽑았는가". 이걸 하트로 파는 것이
--   이 서비스의 수익 구조다. 지목당한 사람이 이 컬럼을 그냥 읽을 수 있으면
--   서비스가 성립하지 않는다. RLS 는 행 단위라 컬럼을 가릴 수 없으므로
--   테이블 직접 접근을 막고 뷰로만 노출한다.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. 모든 테이블에 RLS 활성화 (기본 거부)
-- ---------------------------------------------------------------------
DO $$
DECLARE r record;
BEGIN
    FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public'
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.tablename);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', r.tablename);
    END LOOP;
END $$;


-- ---------------------------------------------------------------------
-- 2. 마스터 데이터 — 로그인한 사람은 읽을 수 있다
-- ---------------------------------------------------------------------
-- 학교·학급은 온보딩에서 선택해야 하고, 질문은 투표에 필요하다.
-- 개인정보가 없고 모두에게 동일한 값이라 공개해도 무방하다.
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'region', 'school', 'grade_class',
        'question', 'question_category',
        'withdrawal_reason', 'report_reason',
        'heart_transaction_type', 'heart_product',
        'board_category'
    ]
    LOOP
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR SELECT TO authenticated USING (true)',
            'read_' || t, t);
    END LOOP;
END $$;

-- 학교 부가 서비스 — 자기 학교 것만 읽는다
CREATE POLICY read_own_school_notice ON public.school_notice
    FOR SELECT TO authenticated
    USING (school_id = (
        SELECT g.school_id FROM public.app_user u
        JOIN public.grade_class g ON g.id = u.class_id
        WHERE u.id = public.current_app_user_id()));

CREATE POLICY read_own_school_meal ON public.meal_plan
    FOR SELECT TO authenticated
    USING (school_id = (
        SELECT g.school_id FROM public.app_user u
        JOIN public.grade_class g ON g.id = u.class_id
        WHERE u.id = public.current_app_user_id()));

CREATE POLICY read_own_meal_item ON public.meal_menu_item
    FOR SELECT TO authenticated
    USING (EXISTS (SELECT 1 FROM public.meal_plan m WHERE m.id = meal_plan_id));

CREATE POLICY read_own_school_event ON public.school_event
    FOR SELECT TO authenticated
    USING (school_id = (
        SELECT g.school_id FROM public.app_user u
        JOIN public.grade_class g ON g.id = u.class_id
        WHERE u.id = public.current_app_user_id()));

CREATE POLICY read_own_timetable ON public.timetable
    FOR SELECT TO authenticated
    USING (class_id = (
        SELECT class_id FROM public.app_user WHERE id = public.current_app_user_id()));

CREATE POLICY rw_own_notice_read ON public.school_notice_read
    FOR ALL TO authenticated
    USING (user_id = public.current_app_user_id())
    WITH CHECK (user_id = public.current_app_user_id());


-- ---------------------------------------------------------------------
-- 3. 본인 계정
-- ---------------------------------------------------------------------
-- 자기 행만 읽는다. 친구의 정보는 아래 friend_profile 뷰로만 본다
-- (그냥 열어주면 친구의 heart_balance 까지 보이기 때문).
CREATE POLICY read_own_user ON public.app_user
    FOR SELECT TO authenticated
    USING (auth_user_id = auth.uid());

-- 온보딩(가입)은 여기서 열지 않는다. onboarding.sql 의 complete_onboarding()
-- 으로만 한다 — INSERT 를 열면 heart_balance·is_synthetic 을 같은 문장에
-- 끼워 넣을 수 있고, RLS 는 행 단위라 그걸 막지 못하기 때문이다.

-- 닉네임·소속 변경만 허용. heart_balance 등은 RPC 로만 바뀐다.
-- (컬럼 단위 제한은 RLS 로 불가능하므로 UPDATE 권한 자체를 컬럼으로 제한한다)
CREATE POLICY update_own_user ON public.app_user
    FOR UPDATE TO authenticated
    USING (auth_user_id = auth.uid())
    WITH CHECK (auth_user_id = auth.uid());

REVOKE UPDATE ON public.app_user FROM authenticated;
GRANT UPDATE (nickname, class_id, gender) ON public.app_user TO authenticated;

CREATE POLICY read_own_session ON public.user_session
    FOR SELECT TO authenticated
    USING (user_id = public.current_app_user_id());

CREATE POLICY insert_own_session ON public.user_session
    FOR INSERT TO authenticated
    WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY insert_own_withdrawal ON public.user_withdrawal
    FOR INSERT TO authenticated
    WITH CHECK (user_id = public.current_app_user_id());


-- ---------------------------------------------------------------------
-- 4. 소셜
-- ---------------------------------------------------------------------
-- 내가 보냈거나 받은 요청만 보인다
CREATE POLICY read_own_friend_request ON public.friend_request
    FOR SELECT TO authenticated
    USING (sender_id = public.current_app_user_id()
        OR receiver_id = public.current_app_user_id());

-- 요청 보내기·수락·거절은 여기서 열지 않는다. friends.sql 의 함수로만 한다 —
-- app_user.id 가 1부터 이어지는 정수라, INSERT 를 열면 receiver_id 를
-- 바꿔가며 전체 가입자에게 요청을 뿌릴 수 있다. 상대를 지목하는 수단은
-- 초대 코드 하나여야 한다.

-- 내가 낀 친구 관계만 보인다
CREATE POLICY read_own_friendship ON public.friendship
    FOR SELECT TO authenticated
    USING (user_low_id = public.current_app_user_id()
        OR user_high_id = public.current_app_user_id());

CREATE POLICY rw_own_block ON public.block_record
    FOR ALL TO authenticated
    USING (user_id = public.current_app_user_id())
    WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY read_own_recommendation ON public.friend_recommendation
    FOR SELECT TO authenticated
    USING (user_id = public.current_app_user_id());


-- ---------------------------------------------------------------------
-- 5. 투표 — 내가 투표자인 것만
-- ---------------------------------------------------------------------
CREATE POLICY read_own_vote_session ON public.vote_session
    FOR SELECT TO authenticated
    USING (user_id = public.current_app_user_id());

CREATE POLICY read_own_vote_item ON public.vote_item
    FOR SELECT TO authenticated
    USING (user_id = public.current_app_user_id());

-- 후보는 내 아이템에 딸린 것만
CREATE POLICY read_own_vote_candidate ON public.vote_candidate
    FOR SELECT TO authenticated
    USING (EXISTS (
        SELECT 1 FROM public.vote_item v
        WHERE v.id = vote_item_id AND v.user_id = public.current_app_user_id()));

CREATE POLICY read_own_shuffle ON public.vote_shuffle
    FOR SELECT TO authenticated
    USING (EXISTS (
        SELECT 1 FROM public.vote_item v
        WHERE v.id = vote_item_id AND v.user_id = public.current_app_user_id()));

CREATE POLICY read_own_ad ON public.ad_impression
    FOR SELECT TO authenticated
    USING (user_id = public.current_app_user_id());


-- ---------------------------------------------------------------------
-- 6. 하트 — 읽기만. 쓰기는 RPC 로만.
-- ---------------------------------------------------------------------
-- 클라이언트가 heart_transaction 을 직접 INSERT 할 수 있으면
-- 하트를 무한정 만들어낼 수 있다. 그래서 INSERT 정책을 두지 않는다.
CREATE POLICY read_own_heart_tx ON public.heart_transaction
    FOR SELECT TO authenticated
    USING (user_id = public.current_app_user_id());

CREATE POLICY read_own_purchase ON public.heart_purchase
    FOR SELECT TO authenticated
    USING (user_id = public.current_app_user_id());

CREATE POLICY read_own_hint ON public.hint_purchase
    FOR SELECT TO authenticated
    USING (user_id = public.current_app_user_id());


-- ---------------------------------------------------------------------
-- 7. 신고 · 제재
-- ---------------------------------------------------------------------
CREATE POLICY insert_own_report ON public.report
    FOR INSERT TO authenticated
    WITH CHECK (reporter_id = public.current_app_user_id());

CREATE POLICY read_own_report ON public.report
    FOR SELECT TO authenticated
    USING (reporter_id = public.current_app_user_id());

-- 자기가 받은 제재는 볼 수 있어야 한다(왜 막혔는지 알아야 하므로)
CREATE POLICY read_own_sanction ON public.sanction
    FOR SELECT TO authenticated
    USING (user_id = public.current_app_user_id());


-- ---------------------------------------------------------------------
-- 8. 정책을 두지 않는 테이블 (= 클라이언트 접근 완전 차단)
-- ---------------------------------------------------------------------
--   admin_user          운영자 명단
--   sanction_policy     자동 제재 임계값 — 알면 회피할 수 있다
--   question_request    검수 과정. MVP 화면 없음
--   external_sync_log   내부 운영 로그
--   vote_received       ★ voter_id 가 유료 비밀이라 직접 접근 금지. 아래 뷰로만.
--   post, post_comment, post_like, comment_like   게시판 v1 미개통


-- ---------------------------------------------------------------------
-- 9. 뷰 — 컬럼을 가려야 하는 경우
-- ---------------------------------------------------------------------
-- RLS 는 행 단위라 컬럼을 숨길 수 없다. 컬럼 제한이 필요하면 뷰로 만든다.
-- 아래 뷰들은 security_invoker=false(정의자 권한)로 동작해 기반 테이블의
-- RLS 를 우회하되, 뷰 안의 WHERE 로 스스로 범위를 제한한다.

-- 9-1. 친구 프로필 — 닉네임과 소속만. 하트 잔액 등은 나가지 않는다.
CREATE OR REPLACE VIEW public.friend_profile
WITH (security_invoker = false) AS
SELECT u.id, u.nickname, u.class_id, u.status
FROM public.app_user u
WHERE u.id = public.current_app_user_id()
   OR public.is_friend(public.current_app_user_id(), u.id);

GRANT SELECT ON public.friend_profile TO authenticated;

-- 9-2. 초대 코드 조회 — 코드를 아는 사람만 그 유저를 찾을 수 있다.
--      전체 유저를 훑어볼 수는 없다(코드를 모르면 결과가 비어 있다).
CREATE OR REPLACE FUNCTION public.find_by_invite_code(code text)
RETURNS TABLE (id bigint, nickname varchar, class_id bigint)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
AS $$
    SELECT u.id, u.nickname, u.class_id
    FROM public.app_user u
    WHERE u.invite_code = upper(code)
      AND u.status = 'ACTIVE'
      AND u.id <> public.current_app_user_id()
$$;

REVOKE ALL ON FUNCTION public.find_by_invite_code(text) FROM public;
GRANT EXECUTE ON FUNCTION public.find_by_invite_code(text) TO authenticated;

-- 9-3. 내가 받은 투표 — voter_id 를 공개 상태에 따라 가린다.
--      이것이 이 서비스의 핵심 비밀 보호 장치다.
CREATE OR REPLACE VIEW public.my_vote_received
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
    -- 완전히 공개된 경우에만 실제 투표자를 알려준다
    CASE WHEN r.reveal_status = 'REVEALED' THEN r.voter_id END AS voter_id,
    -- 부분 공개(힌트 구매)에서는 단서만 준다
    CASE WHEN r.reveal_status IN ('PARTIAL', 'REVEALED')
         THEN (SELECT left(v.nickname, 1) FROM public.app_user v WHERE v.id = r.voter_id)
    END AS voter_initial
FROM public.vote_received r
WHERE r.receiver_id = public.current_app_user_id();

GRANT SELECT ON public.my_vote_received TO authenticated;


-- ---------------------------------------------------------------------
-- 10. anon 역할에는 아무것도 주지 않는다
-- ---------------------------------------------------------------------
-- 익명 로그인을 거치면 authenticated 역할이 된다.
-- 로그인 이전(anon)에는 어떤 데이터도 필요 없다.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon;
