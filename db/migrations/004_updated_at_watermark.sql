-- =====================================================================
-- 004_updated_at_watermark.sql · 증분 적재용 워터마크 컬럼
-- =====================================================================
-- 왜 필요한가:
--   BigQuery 증분 적재는 "지난 적재 이후 바뀐 행"을 골라내야 한다.
--   그런데 이 스키마의 시간 컬럼은 테이블마다 이름도 의미도 다르다 —
--   created_at / served_at / started_at / synced_at 이 섞여 있고,
--   vote_candidate 와 meal_menu_item 은 시간 컬럼이 아예 없다.
--
--   더 위험한 것은 **행이 생성된 뒤에 바뀌는 값**이다.
--   vote_received.reveal_status 는 힌트를 살 때마다 바뀌지만 그 변경을
--   기록하는 시간 컬럼이 없다. created_at 으로 증분을 뜨면 이 변경이
--   BigQuery 에 영영 도달하지 않는다. 조용히 틀린 데이터가 된다.
--
--   그래서 증분 대상 테이블 전부에 updated_at 하나를 심고 트리거로 갱신한다.
--   적재 규칙이 테이블당 한 줄이 아니라 **전체가 한 줄**이 된다:
--       WHERE updated_at > (지난 워터마크)
--
--   마스터·참조 테이블(region, school, question, ...)은 대상이 아니다.
--   작고 거의 안 변해서 매번 통째로 갈아끼우는 편이 싸다 (pipeline/tables.yaml).
--
-- 재실행해도 안전하다.
-- =====================================================================

-- 갱신 함수 -----------------------------------------------------------
-- search_path 를 고정한다. 고정하지 않으면 호출자의 search_path 를 따라가
-- 같은 이름의 다른 객체를 잡을 수 있다(Supabase 린터도 이걸 경고한다).
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.set_updated_at() IS
    'UPDATE 시 updated_at 을 now() 로 밀어준다. 증분 적재의 워터마크';


-- 증분 대상 테이블에 컬럼 + 인덱스 + 트리거 ------------------------------
-- 인덱스가 없으면 "증분"이라면서 매번 전체를 훑는다.
-- 합성 데이터 786만 행에서는 그 차이가 그대로 드러난다.
DO $$
DECLARE
    t text;
    targets text[] := ARRAY[
        -- 유저 · 세션
        'app_user', 'user_session', 'user_withdrawal',
        -- 친구 · 차단
        'friend_request', 'friendship', 'friend_recommendation', 'block_record',
        -- 질문 요청
        'question_request',
        -- 투표
        'vote_session', 'vote_item', 'vote_candidate', 'vote_shuffle', 'vote_received',
        -- 광고 · 힌트
        'ad_impression', 'hint_purchase',
        -- 하트
        'heart_purchase', 'heart_transaction',
        -- 신고 · 제재
        'report', 'sanction',
        -- 게시판 (v2 이지만 테이블은 있다)
        'post', 'post_comment', 'post_like', 'comment_like',
        -- 학교 정보 (NEIS 동기화)
        'meal_plan', 'meal_menu_item', 'timetable',
        'school_notice', 'school_notice_read', 'school_event', 'external_sync_log'
    ];
BEGIN
    FOREACH t IN ARRAY targets LOOP
        EXECUTE format(
            'ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now()', t);

        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS %I ON public.%I (updated_at)', 'idx_' || t || '_updated', t);

        EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_updated ON public.%I', t, t);
        EXECUTE format(
            'CREATE TRIGGER trg_%s_updated BEFORE UPDATE ON public.%I
               FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()', t, t);
    END LOOP;
END $$;
