-- =====================================================================
-- 006_hint_select.sql · 힌트를 골라서 사는 구조로 (W14)
-- =====================================================================
-- 힌트가 순차 4단계(성별→초성→반→공개, 200·300·500·1000)에서
-- **선택형 5개 + 해금형 1개**로 바뀐다.
--
--   기본 5종 · 각 20하트 · 순서 없음
--     GENDER   성별          (광고 30초로도 열 수 있다. 하루 한 번)
--     INITIAL  랜덤 글자 초성
--     MEDIAL   랜덤 글자 중성
--     FINAL    랜덤 글자 종성
--     CLASS    반
--
--   FULL_NAME  이름 공개 · 100하트 · **기본 5종 중 3개 이상**을 연 뒤에만
--
-- 초성·중성·종성은 **같은 한 글자**를 가리킨다. 셋을 다 사면 그 글자가
-- 완성된다(○ㅎ○ → ○혀○ → ○형○). 글자마다 따로 뽑으면 조각이 흩어져
-- 읽히지 않는다. 어느 글자인지는 vote_received.hint_char_index 에 한 번
-- 정해 두고 바꾸지 않는다 — 닉네임을 바꿔도(W11) 이미 산 힌트가 흔들리면 안 된다.
--
-- 재실행해도 안전하다.
-- =====================================================================

-- 1. 중성·종성 힌트 유형 ------------------------------------------------
-- ALTER TYPE ... ADD VALUE 는 같은 트랜잭션 안에서 그 값을 쓸 수 없다.
-- 그래서 값 추가만 여기서 하고, 쓰는 쪽은 db/rls/received.sql 에 둔다.
ALTER TYPE hint_type ADD VALUE IF NOT EXISTS 'MEDIAL';
ALTER TYPE hint_type ADD VALUE IF NOT EXISTS 'FINAL';

-- 광고로 힌트를 여는 자리. 기존 두 값(VOTE_SHUFFLE, HEART_REWARD)과 구분한다.
ALTER TYPE ad_placement ADD VALUE IF NOT EXISTS 'HINT_UNLOCK';


-- 2. 힌트 구매 --------------------------------------------------------
DO $$
BEGIN
    -- 순서가 의미를 잃었다. 같은 단계 번호를 두 번 쓸 수 없다는 제약이
    -- 오히려 걸림돌이 된다. 대신 **같은 유형을 두 번 살 수 없게** 바꾼다.
    ALTER TABLE hint_purchase DROP CONSTRAINT IF EXISTS uq_hint_step;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_hint_kind') THEN
        ALTER TABLE hint_purchase
            ADD CONSTRAINT uq_hint_kind UNIQUE (vote_received_id, hint_type);
    END IF;

    -- step 은 "몇 번째로 열었나"로 뜻이 바뀐다. 단계가 아니라 순서다.
    -- 분석에는 여전히 쓸모가 있다 — 사람들이 어떤 힌트부터 사는지가 보인다.
    ALTER TABLE hint_purchase DROP CONSTRAINT IF EXISTS hint_purchase_step_check;
    ALTER TABLE hint_purchase ADD CONSTRAINT ck_hint_order CHECK (step BETWEEN 1 AND 6);

    -- 광고로 연 힌트는 0하트다. 기존 CHECK 는 > 0 이라 들어가지 못한다.
    ALTER TABLE hint_purchase DROP CONSTRAINT IF EXISTS hint_purchase_heart_cost_check;
    ALTER TABLE hint_purchase ADD CONSTRAINT ck_hint_cost CHECK (heart_cost >= 0);
END $$;

-- 광고로 열었으면 그 광고를 가리킨다. 하트로 샀으면 NULL 이다.
-- 어느 쪽으로 열렸는지가 남아야 "광고를 보고 여는 사람이 얼마나 되나"를 센다.
ALTER TABLE hint_purchase
    ADD COLUMN IF NOT EXISTS ad_impression_id bigint REFERENCES ad_impression(id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_hint_ad
    ON hint_purchase(ad_impression_id) WHERE ad_impression_id IS NOT NULL;

COMMENT ON COLUMN hint_purchase.step IS
    '몇 번째로 연 힌트인가(1~6). 누진 단계가 아니라 순서다 — 마이그레이션 006';


-- 3. 어느 글자를 가리키는가 ---------------------------------------------
ALTER TABLE vote_received
    ADD COLUMN IF NOT EXISTS hint_char_index smallint;

COMMENT ON COLUMN vote_received.hint_char_index IS
    '초성·중성·종성 힌트가 가리키는 닉네임 글자 위치(0부터). 처음 살 때 정해지고 바뀌지 않는다';
