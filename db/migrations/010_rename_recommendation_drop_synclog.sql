-- =====================================================================
-- 010 · friend_recommendation 이름 바로잡기 + external_sync_log 제거
-- =====================================================================
-- 1) friend_recommendation → rejected_friend_recommendations
--
--    이름이 하는 일과 달랐다. 추천은 이 표에 들어오지 않는다 —
--    friend_suggestion 뷰가 그때그때 계산한다. 이 표에 행이 생기는 경로는
--    dismiss_suggestion() 하나뿐이고, 그건 "안 볼래"를 눌렀을 때다.
--    즉 이 표는 **거절 기록**이지 추천 기록이 아니었다.
--
--    ⚠️ score 는 이제 항상 0 이다. 추천 점수를 매기던 자리인데 거절만
--       들어오므로 채울 사람이 없다. 지금 지우지는 않는다 — 추천을 미리
--       계산해 저장하는 날이 오면 되살아날 자리이고, 0 이 거짓말을 하지는
--       않는다. 분석에서 이 컬럼을 쓰지 말 것.
--
-- 2) external_sync_log 삭제
--
--    외부 동기화 이력을 남기려던 표다. 만든 적은 있으나 **쓰는 코드를
--    한 번도 붙이지 않았다** — 수집기 셋(neis_schools/meals/events) 어느
--    것도 이 표에 넣지 않는다. 0행으로 반년 가까이 있었다.
--
--    지우는 이유는 "안 쓰니까"가 아니라, 빈 표가 ERD 에 남아 있으면
--    **동기화 이력이 남고 있다고 읽히기 때문**이다. 없는 편이 정직하다.
--    필요해지면 그때 만든다 — 그때는 넣는 코드와 함께 만든다.
--
-- 다시 돌려도 안전하다. 이름을 이미 바꿨으면 건너뛴다.
-- =====================================================================

-- 1. 이름 -------------------------------------------------------------
DO $$
BEGIN
    IF to_regclass('public.friend_recommendation') IS NOT NULL
       AND to_regclass('public.rejected_friend_recommendations') IS NULL THEN

        ALTER TABLE public.friend_recommendation
            RENAME TO rejected_friend_recommendations;

        -- 제약·인덱스 이름은 RENAME 을 따라오지 않는다. 옛 이름이 남으면
        -- 오류를 읽을 때 어느 표인지 헷갈린다.
        ALTER TABLE public.rejected_friend_recommendations
            RENAME CONSTRAINT uq_recommendation TO uq_rejected_recommendation;
        ALTER TABLE public.rejected_friend_recommendations
            RENAME CONSTRAINT ck_no_self_recommend TO ck_no_self_reject;
        ALTER INDEX IF EXISTS idx_recommend_user
            RENAME TO idx_rejected_recommend_user;
        ALTER INDEX IF EXISTS idx_friend_recommendation_updated
            RENAME TO idx_rejected_friend_recommendations_updated;
    END IF;
END $$;

COMMENT ON TABLE public.rejected_friend_recommendations IS
    '친구 추천에서 "안 볼래"를 누른 기록. 추천 자체는 friend_suggestion 뷰가 계산한다.';

-- 트리거는 표 이름을 이름에 담고 있어 갈아 끼운다(마이그레이션 004 가 만든 것).
-- 새 이름 쪽도 먼저 지운다 — 처음부터 새로 만들면 004 가 이미 새 이름으로
-- 만들어 두므로, 안 지우면 여기서 "이미 있다"로 깨진다.
DROP TRIGGER IF EXISTS trg_friend_recommendation_updated
    ON public.rejected_friend_recommendations;
DROP TRIGGER IF EXISTS trg_rejected_friend_recommendations_updated
    ON public.rejected_friend_recommendations;
CREATE TRIGGER trg_rejected_friend_recommendations_updated
    BEFORE UPDATE ON public.rejected_friend_recommendations
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- 2. external_sync_log -------------------------------------------------
DROP TABLE IF EXISTS public.external_sync_log;
DROP TYPE  IF EXISTS sync_resource;
DROP TYPE  IF EXISTS sync_status;
