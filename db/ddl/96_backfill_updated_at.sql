-- =====================================================================
-- 96_backfill_updated_at.sql · 대량 적재 후 워터마크를 실제 시각으로
-- =====================================================================
-- 95_resync_sequences.sql 과 같은 자리에 있다 — **대량 적재 직후 한 번** 돌린다.
--
-- 왜 필요한가:
--   마이그레이션 004 가 심은 updated_at 의 기본값은 now() 다.
--   COPY 로 786만 행을 부어 넣으면 그 786만 행의 updated_at 이 전부
--   "적재한 순간"이 된다. 3개월치 데이터인데 하루에 뭉친다.
--
--   BigQuery raw 테이블은 updated_at 으로 파티션을 나눈다. 전부 한 파티션에
--   들어가면 파티션 가지치기가 통째로 무력해지고, 쿼리마다 786만 행을 다 읽는다.
--   무료 등급(월 1TB)에서 이건 실제로 아픈 비용이다.
--
--   그래서 각 행이 원래 가진 시각(created_at / served_at / started_at ...)으로
--   되돌린다. 원천에 시각이 없는 행만 적재 시각으로 남는다.
--
-- 실유저 DB 에 돌려도 안전하다 — 이미 자연 시각이 들어간 행은 값이 그대로다.
-- 재실행해도 안전하다.
--
-- ⚠️ 트리거를 잠시 끄고 돌린다. 켜둔 채로 UPDATE 하면 트리거가 방금 넣은 값을
--    다시 now() 로 덮어써서, 이 파일이 아무 일도 하지 않은 것처럼 끝난다.
-- =====================================================================

DO $$
DECLARE
    t        text;
    src_col  text;
    n        bigint;
    -- 앞에 있는 것이 우선. created_at 이 있으면 그것을 쓴다.
    priority text[] := ARRAY[
        'created_at', 'served_at', 'started_at', 'published_at',
        'synced_at', 'read_at', 'starts_at'
    ];
    -- 원래부터 updated_at 이 있던 테이블. 여기 값은 **진짜 수정 이력**이라
    -- created_at 으로 덮으면 데이터를 잃는다. 004 가 심은 것만 손댄다.
    keep     text[] := ARRAY['app_user', 'school', 'post', 'post_comment'];
BEGIN
    FOR t IN
        SELECT c.table_name
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.column_name = 'updated_at'
          AND NOT (c.table_name = ANY(keep))
        ORDER BY c.table_name
    LOOP
        SELECT c.column_name INTO src_col
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.table_name = t
          AND c.column_name = ANY(priority)
        ORDER BY array_position(priority, c.column_name)
        LIMIT 1;

        IF src_col IS NULL THEN
            CONTINUE;   -- vote_candidate · meal_menu_item — 아래에서 따로 본다
        END IF;

        -- 트리거가 없는 테이블도 있다(full 적재 대상은 004 의 손이 닿지 않았다).
        IF EXISTS (
            SELECT 1 FROM pg_trigger
            WHERE tgrelid = format('public.%I', t)::regclass
              AND tgname = 'trg_' || t || '_updated'
        ) THEN
            EXECUTE format('ALTER TABLE public.%I DISABLE TRIGGER trg_%s_updated', t, t);
            EXECUTE format(
                'UPDATE public.%I SET updated_at = %I WHERE %I IS NOT NULL AND updated_at <> %I',
                t, src_col, src_col, src_col);
            GET DIAGNOSTICS n = ROW_COUNT;
            EXECUTE format('ALTER TABLE public.%I ENABLE TRIGGER trg_%s_updated', t, t);
        ELSE
            EXECUTE format(
                'UPDATE public.%I SET updated_at = %I WHERE %I IS NOT NULL AND updated_at <> %I',
                t, src_col, src_col, src_col);
            GET DIAGNOSTICS n = ROW_COUNT;
        END IF;

        IF n > 0 THEN
            RAISE NOTICE '%  ← %  (% 행)', t, src_col, n;
        END IF;
    END LOOP;
END $$;


-- vote_candidate — 시각 컬럼이 없다 ------------------------------------
-- 가장 큰 테이블(합성 379만 행)인데 자기 시각이 없어서 위 반복문이 건너뛴다.
-- 부모인 vote_item 의 출제 시각을 물려받는다. 후보는 출제와 동시에 만들어지므로
-- 이게 실제 생성 시각이다.
ALTER TABLE vote_candidate DISABLE TRIGGER trg_vote_candidate_updated;

UPDATE vote_candidate c
   SET updated_at = i.served_at
  FROM vote_item i
 WHERE i.id = c.vote_item_id
   AND c.updated_at <> i.served_at;

ALTER TABLE vote_candidate ENABLE TRIGGER trg_vote_candidate_updated;


-- meal_menu_item 도 같은 사정이다. 부모는 meal_plan.
ALTER TABLE meal_menu_item DISABLE TRIGGER trg_meal_menu_item_updated;

UPDATE meal_menu_item m
   SET updated_at = p.created_at
  FROM meal_plan p
 WHERE p.id = m.meal_plan_id
   AND m.updated_at <> p.created_at;

ALTER TABLE meal_menu_item ENABLE TRIGGER trg_meal_menu_item_updated;
