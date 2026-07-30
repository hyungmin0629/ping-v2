-- =====================================================================
-- board.sql · 자유게시판 (W9)
-- =====================================================================
-- 익명 게시판이 아니라 **닉네임이 드러나는 자유게시판**이다.
-- 익명 게시판을 v1 에서 뺐던 이유가 "사고가 나도 책임을 물을 수 없다"였는데,
-- 글쓴이가 붙으면 그 전제가 바뀐다. 댓글도 마찬가지라 익명 번호를 쓰지 않는다
-- (마이그레이션 005). 경위는 [[DECISIONS]].
--
-- 범위는 **같은 학교**다. post.school_id 는 클라이언트가 정하지 않고
-- RPC 가 글쓴이의 소속에서 끌어온다.
--
-- ⚠️ my_info_school_id() 를 쓰지 않는다.
--    그건 급식·시간표를 "어느 학교에서 빌려오는가"이고, 게시판은 "누구와 같이
--    있는가"다. 코드잇 DA 14기 사람이 서울고 게시판을 보면 안 된다.
--
-- 쓰기는 전부 RPC 다. post 에 INSERT 를 열면 author_id 를 남의 것으로 넣거나
-- like_count 를 부풀릴 수 있고, RLS 는 행 단위라 그걸 막지 못한다.
--
-- 재실행해도 안전하다.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. 내 소속 학교
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.my_school_id()
RETURNS bigint
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
AS $$
    SELECT g.school_id
      FROM public.app_user u
      JOIN public.grade_class g ON g.id = u.class_id
     WHERE u.id = public.current_app_user_id()
$$;

REVOKE ALL ON FUNCTION public.my_school_id() FROM public;
GRANT EXECUTE ON FUNCTION public.my_school_id() TO authenticated;


-- ---------------------------------------------------------------------
-- 2. 읽기 — 뷰로만
-- ---------------------------------------------------------------------
-- 테이블에는 SELECT 정책을 만들지 않는다(정책 없음 = 거부).
-- 목록에 글쓴이 닉네임이 필요한데, app_user 는 "본인 행만" 읽을 수 있어서
-- 같은 학교 남의 닉네임이 안 나온다. 그래서 정의자 권한 뷰로 필요한 컬럼만 낸다.

CREATE OR REPLACE VIEW public.board_post
WITH (security_invoker = false) AS
SELECT
    p.id,
    c.code                                   AS category_code,
    c.name                                   AS category_name,
    p.title,
    p.body,
    a.nickname                               AS author_nickname,
    (p.author_id = public.current_app_user_id()) AS is_mine,
    p.like_count,
    p.comment_count,
    p.view_count,
    EXISTS (SELECT 1 FROM public.post_like l
             WHERE l.post_id = p.id
               AND l.user_id = public.current_app_user_id()) AS liked_by_me,
    p.created_at
FROM public.post p
JOIN public.board_category c ON c.id = p.category_id
JOIN public.app_user a       ON a.id = p.author_id
WHERE p.school_id = public.my_school_id()
  AND p.status = 'PUBLISHED';

GRANT SELECT ON public.board_post TO authenticated;

-- 댓글 — 글이 내 학교 것일 때만 보인다.
CREATE OR REPLACE VIEW public.board_comment
WITH (security_invoker = false) AS
SELECT
    m.id,
    m.post_id,
    m.body,
    a.nickname                                   AS author_nickname,
    (m.author_id = public.current_app_user_id()) AS is_mine,
    m.like_count,
    EXISTS (SELECT 1 FROM public.comment_like l
             WHERE l.comment_id = m.id
               AND l.user_id = public.current_app_user_id()) AS liked_by_me,
    m.created_at
FROM public.post_comment m
JOIN public.post p     ON p.id = m.post_id
JOIN public.app_user a ON a.id = m.author_id
WHERE p.school_id = public.my_school_id()
  AND p.status = 'PUBLISHED'
  AND m.status = 'PUBLISHED';

GRANT SELECT ON public.board_comment TO authenticated;


-- ---------------------------------------------------------------------
-- 3. 글쓰기
-- ---------------------------------------------------------------------
-- school_id 와 author_id 는 인자로 받지 않는다. 받으면 남의 이름으로 쓸 수 있다.
CREATE OR REPLACE FUNCTION public.create_post(
    p_title         text,
    p_body          text,
    p_category_code text DEFAULT 'FREE'
)
RETURNS bigint
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me       bigint := public.current_app_user_id();
    v_school   bigint;
    v_category bigint;
    v_title    text   := btrim(coalesce(p_title, ''));
    v_body     text   := btrim(coalesce(p_body, ''));
    v_id       bigint;
BEGIN
    IF v_me IS NULL THEN
        RAISE EXCEPTION '먼저 프로필을 만들어 주세요' USING ERRCODE = '28000';
    END IF;
    IF v_title = '' OR v_body = '' THEN
        RAISE EXCEPTION '제목과 내용을 모두 입력해 주세요' USING ERRCODE = '22023';
    END IF;
    IF length(v_title) > 120 THEN
        RAISE EXCEPTION '제목은 120자까지입니다' USING ERRCODE = '22023';
    END IF;
    -- body 는 text 라 DB 제한이 없다. 화면과 같은 상한을 여기서도 건다 —
    -- 화면만 막으면 API 를 직접 부르는 경로가 남는다.
    IF length(v_body) > 5000 THEN
        RAISE EXCEPTION '내용은 5000자까지입니다' USING ERRCODE = '22023';
    END IF;

    v_school := public.my_school_id();

    SELECT id INTO v_category
      FROM public.board_category
     WHERE code = p_category_code AND is_active;

    IF v_category IS NULL THEN
        RAISE EXCEPTION '없는 게시판입니다' USING ERRCODE = '22023';
    END IF;

    INSERT INTO public.post (school_id, category_id, author_id, title, body)
    VALUES (v_school, v_category, v_me, v_title, v_body)
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;


-- ---------------------------------------------------------------------
-- 4. 댓글
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.create_comment(p_post_id bigint, p_body text)
RETURNS bigint
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me   bigint := public.current_app_user_id();
    v_body text   := btrim(coalesce(p_body, ''));
    v_id   bigint;
BEGIN
    IF v_me IS NULL THEN
        RAISE EXCEPTION '먼저 프로필을 만들어 주세요' USING ERRCODE = '28000';
    END IF;
    IF v_body = '' THEN
        RAISE EXCEPTION '내용을 입력해 주세요' USING ERRCODE = '22023';
    END IF;
    IF length(v_body) > 1000 THEN
        RAISE EXCEPTION '댓글은 1000자까지입니다' USING ERRCODE = '22023';
    END IF;

    -- 남의 학교 글에 댓글을 달 수 없다. 글 id 는 순번이라 찍어볼 수 있으므로
    -- 화면에서 안 보이는 것에 기대지 않고 여기서 막는다.
    IF NOT EXISTS (
        SELECT 1 FROM public.post p
         WHERE p.id = p_post_id
           AND p.school_id = public.my_school_id()
           AND p.status = 'PUBLISHED'
    ) THEN
        RAISE EXCEPTION '없는 글입니다' USING ERRCODE = '22023';
    END IF;

    -- anonymous_seq 는 NULL 이다. 닉네임을 드러내므로 익명 번호를 쓰지 않는다.
    INSERT INTO public.post_comment (post_id, author_id, body)
    VALUES (p_post_id, v_me, v_body)
    RETURNING id INTO v_id;

    UPDATE public.post
       SET comment_count = comment_count + 1
     WHERE id = p_post_id;

    RETURN v_id;
END;
$$;


-- ---------------------------------------------------------------------
-- 5. 좋아요 — 누르면 켜지고 다시 누르면 꺼진다
-- ---------------------------------------------------------------------
-- 집계 컬럼을 RPC 안에서 같은 트랜잭션으로 고친다. 트리거로 하지 않는 이유는
-- 이 프로젝트가 "모든 쓰기는 RPC 하나를 거친다"로 통일돼 있어서다 —
-- 집계가 어긋나면 볼 곳이 한 군데여야 한다.
CREATE OR REPLACE FUNCTION public.toggle_post_like(p_post_id bigint)
RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me      bigint := public.current_app_user_id();
    v_deleted int;
BEGIN
    IF v_me IS NULL THEN
        RAISE EXCEPTION '먼저 프로필을 만들어 주세요' USING ERRCODE = '28000';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.post p
         WHERE p.id = p_post_id
           AND p.school_id = public.my_school_id()
           AND p.status = 'PUBLISHED'
    ) THEN
        RAISE EXCEPTION '없는 글입니다' USING ERRCODE = '22023';
    END IF;

    DELETE FROM public.post_like
     WHERE post_id = p_post_id AND user_id = v_me;
    GET DIAGNOSTICS v_deleted = ROW_COUNT;

    IF v_deleted > 0 THEN
        UPDATE public.post SET like_count = greatest(like_count - 1, 0) WHERE id = p_post_id;
        RETURN false;
    END IF;

    INSERT INTO public.post_like (post_id, user_id) VALUES (p_post_id, v_me);
    UPDATE public.post SET like_count = like_count + 1 WHERE id = p_post_id;
    RETURN true;
END;
$$;

CREATE OR REPLACE FUNCTION public.toggle_comment_like(p_comment_id bigint)
RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me      bigint := public.current_app_user_id();
    v_deleted int;
BEGIN
    IF v_me IS NULL THEN
        RAISE EXCEPTION '먼저 프로필을 만들어 주세요' USING ERRCODE = '28000';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.post_comment m
          JOIN public.post p ON p.id = m.post_id
         WHERE m.id = p_comment_id
           AND p.school_id = public.my_school_id()
           AND p.status = 'PUBLISHED'
           AND m.status = 'PUBLISHED'
    ) THEN
        RAISE EXCEPTION '없는 댓글입니다' USING ERRCODE = '22023';
    END IF;

    DELETE FROM public.comment_like
     WHERE comment_id = p_comment_id AND user_id = v_me;
    GET DIAGNOSTICS v_deleted = ROW_COUNT;

    IF v_deleted > 0 THEN
        UPDATE public.post_comment SET like_count = greatest(like_count - 1, 0)
         WHERE id = p_comment_id;
        RETURN false;
    END IF;

    INSERT INTO public.comment_like (comment_id, user_id) VALUES (p_comment_id, v_me);
    UPDATE public.post_comment SET like_count = like_count + 1 WHERE id = p_comment_id;
    RETURN true;
END;
$$;


-- ---------------------------------------------------------------------
-- 6. 삭제 — 행을 지우지 않고 상태만 바꾼다
-- ---------------------------------------------------------------------
-- 지우면 신고 기록이 가리키던 대상이 사라진다(report.target_post_id 가 FK 다).
-- 사고가 난 글일수록 지워지면 안 된다.
CREATE OR REPLACE FUNCTION public.delete_own_post(p_post_id bigint)
RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE v_me bigint := public.current_app_user_id();
BEGIN
    UPDATE public.post
       SET status = 'DELETED', updated_at = now()
     WHERE id = p_post_id AND author_id = v_me AND status = 'PUBLISHED';
    RETURN FOUND;
END;
$$;

CREATE OR REPLACE FUNCTION public.delete_own_comment(p_comment_id bigint)
RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me   bigint := public.current_app_user_id();
    v_post bigint;
BEGIN
    UPDATE public.post_comment
       SET status = 'DELETED', updated_at = now()
     WHERE id = p_comment_id AND author_id = v_me AND status = 'PUBLISHED'
    RETURNING post_id INTO v_post;

    IF v_post IS NULL THEN
        RETURN false;
    END IF;

    UPDATE public.post SET comment_count = greatest(comment_count - 1, 0) WHERE id = v_post;
    RETURN true;
END;
$$;


-- ---------------------------------------------------------------------
-- 7. 조회수
-- ---------------------------------------------------------------------
-- ⚠️ 새로고침하면 늘어난다. 사람 수가 아니라 열어본 횟수다.
--    정확한 지표가 필요하면 세션 기준으로 다시 설계해야 한다.
CREATE OR REPLACE FUNCTION public.bump_post_view(p_post_id bigint)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
BEGIN
    UPDATE public.post
       SET view_count = view_count + 1
     WHERE id = p_post_id
       AND school_id = public.my_school_id()
       AND status = 'PUBLISHED';
END;
$$;


-- ---------------------------------------------------------------------
-- 8. 신고
-- ---------------------------------------------------------------------
-- 신고해도 **자동으로 내려가지 않는다.** 자동 숨김은 집단 신고에 취약해서
-- 채택하지 않았다([[DECISIONS]]). 기록만 남고 사람이 보고 판단한다.
-- 검토 인력이 없는 상태에서 열기 때문에, 신고가 쌓이는지 작업자가 직접 본다.
CREATE OR REPLACE FUNCTION public.report_content(
    p_target      text,      -- 'POST' | 'COMMENT'
    p_target_id   bigint,
    p_reason_code text,
    p_detail      text DEFAULT NULL
)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
    v_me     bigint := public.current_app_user_id();
    v_target public.report_target;
    v_author bigint;
BEGIN
    IF v_me IS NULL THEN
        RAISE EXCEPTION '먼저 프로필을 만들어 주세요' USING ERRCODE = '28000';
    END IF;
    IF p_target NOT IN ('POST', 'COMMENT') THEN
        RAISE EXCEPTION '신고 대상이 올바르지 않습니다' USING ERRCODE = '22023';
    END IF;
    v_target := p_target::public.report_target;

    -- 사유가 그 대상에 쓸 수 있는 것인지 확인한다.
    IF NOT EXISTS (
        SELECT 1 FROM public.report_reason
         WHERE code = p_reason_code AND target_type = v_target AND is_active
    ) THEN
        RAISE EXCEPTION '신고 사유가 올바르지 않습니다' USING ERRCODE = '22023';
    END IF;

    -- 대상이 내 학교 것인지 확인하고, 글쓴이를 찾는다.
    IF v_target = 'POST' THEN
        SELECT p.author_id INTO v_author
          FROM public.post p
         WHERE p.id = p_target_id
           AND p.school_id = public.my_school_id()
           AND p.status = 'PUBLISHED';
    ELSE
        SELECT m.author_id INTO v_author
          FROM public.post_comment m
          JOIN public.post p ON p.id = m.post_id
         WHERE m.id = p_target_id
           AND p.school_id = public.my_school_id()
           AND m.status = 'PUBLISHED';
    END IF;

    IF v_author IS NULL THEN
        RETURN 'NOT_FOUND';
    END IF;
    IF v_author = v_me THEN
        RETURN 'SELF';
    END IF;

    -- 같은 사람이 같은 대상을 여러 번 신고해도 한 건으로 센다.
    -- 안 막으면 한 사람이 report_count 를 얼마든지 올릴 수 있다.
    IF EXISTS (
        SELECT 1 FROM public.report r
         WHERE r.reporter_id = v_me
           AND r.target_type = v_target
           AND ((v_target = 'POST'    AND r.target_post_id    = p_target_id)
             OR (v_target = 'COMMENT' AND r.target_comment_id = p_target_id))
    ) THEN
        RETURN 'ALREADY';
    END IF;

    INSERT INTO public.report (
        reporter_id, target_type, target_post_id, target_comment_id,
        reason_code, detail_text)
    VALUES (
        v_me, v_target,
        CASE WHEN v_target = 'POST'    THEN p_target_id END,
        CASE WHEN v_target = 'COMMENT' THEN p_target_id END,
        p_reason_code, nullif(btrim(coalesce(p_detail, '')), ''));

    IF v_target = 'POST' THEN
        UPDATE public.post SET report_count = report_count + 1 WHERE id = p_target_id;
    END IF;

    RETURN 'OK';
END;
$$;


-- ---------------------------------------------------------------------
-- 9. 권한
-- ---------------------------------------------------------------------
REVOKE ALL ON FUNCTION public.create_post(text, text, text)              FROM public;
REVOKE ALL ON FUNCTION public.create_comment(bigint, text)               FROM public;
REVOKE ALL ON FUNCTION public.toggle_post_like(bigint)                   FROM public;
REVOKE ALL ON FUNCTION public.toggle_comment_like(bigint)                FROM public;
REVOKE ALL ON FUNCTION public.delete_own_post(bigint)                    FROM public;
REVOKE ALL ON FUNCTION public.delete_own_comment(bigint)                 FROM public;
REVOKE ALL ON FUNCTION public.bump_post_view(bigint)                     FROM public;
REVOKE ALL ON FUNCTION public.report_content(text, bigint, text, text)   FROM public;

GRANT EXECUTE ON FUNCTION public.create_post(text, text, text)            TO authenticated;
GRANT EXECUTE ON FUNCTION public.create_comment(bigint, text)             TO authenticated;
GRANT EXECUTE ON FUNCTION public.toggle_post_like(bigint)                 TO authenticated;
GRANT EXECUTE ON FUNCTION public.toggle_comment_like(bigint)              TO authenticated;
GRANT EXECUTE ON FUNCTION public.delete_own_post(bigint)                  TO authenticated;
GRANT EXECUTE ON FUNCTION public.delete_own_comment(bigint)               TO authenticated;
GRANT EXECUTE ON FUNCTION public.bump_post_view(bigint)                   TO authenticated;
GRANT EXECUTE ON FUNCTION public.report_content(text, bigint, text, text) TO authenticated;

-- 테이블 쓰기는 전부 닫는다. 위 RPC 만이 통로다.
REVOKE INSERT, UPDATE, DELETE ON public.post         FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.post_comment FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.post_like    FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.comment_like FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.report       FROM authenticated;
