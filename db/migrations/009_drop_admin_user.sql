-- =====================================================================
-- 009 · admin_user 테이블을 없애고 app_user.is_admin 하나로 접는다
-- =====================================================================
-- 왜:
--   운영 화면을 만들 계획이 없다. 사람 다섯 명짜리 테이블과 enum 하나,
--   FK 여섯 개를 유지할 이유가 그것뿐이었다.
--
-- 잃는 것 — 정확히 알고 지운다:
--   admin_role  운영자를 REVIEWER/MODERATOR/SCHOOL_ADMIN/SUPER 로 나누던 값.
--               권한을 코드로 갈라 쓸 일이 없어졌으니 없앤다. 나중에 필요하면
--               그때가 권한 체계를 다시 설계할 시점이지, 지금 남겨둘 이유가 아니다.
--   school_id   학교별 운영자를 두려던 것. 학교가 5,724개인데 운영자는 없다.
--   is_active   퇴사한 운영자 표시. app_user.status 가 같은 일을 한다.
--
-- 잃지 않는 것:
--   "누가 처리했나"는 그대로 남는다. FK 여섯 개가 app_user 를 가리키게만
--   바뀐다. 컬럼 이름(*_admin_id)도 그대로 둔다 — 가리키는 표가 아니라
--   **그 사람이 어떤 자격으로 한 행위인지**를 말하는 이름이기 때문이다.
--
-- 안전한가:
--   Supabase 의 admin_user 는 0행이고, 여섯 개 참조 컬럼도 전부 NULL 이다
--   (2026-07-31 확인). 옮길 데이터가 없다.
--   ⚠️ 합성 데이터에는 운영자 5명과 그 참조가 있다. 재생성 대상이다.
-- =====================================================================

-- 1. 운영자 표시 ------------------------------------------------------
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS is_admin boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN app_user.is_admin IS
    '운영자 여부. 앱에 이 값을 바꾸는 경로는 없다 — DB 에서 직접 켠다.';

-- 2. FK 를 app_user 로 옮긴다 -----------------------------------------
-- 값이 전부 NULL 이라 제약만 바꾸면 된다. 컬럼 이름은 유지한다.
-- ⚠️ DDL 은 이제 admin_user 를 만들지 않는다. 처음부터 새로 만들면 이 시점에
--    그 표가 아예 없으므로, 있을 때만 옮긴다. 없으면 옮길 것도 없다.
--    (apply.py 는 마이그레이션을 **전부** 다시 적용한다 — 옛 마이그레이션도
--     새 스키마 위에서 돌 수 있어야 한다.)
DO $$
DECLARE
    r record;
BEGIN
    IF to_regclass('public.admin_user') IS NULL THEN
        RETURN;
    END IF;

    FOR r IN
        SELECT conrelid::regclass::text AS tbl, conname, a.attname AS col
          FROM pg_constraint c
          JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
         WHERE c.confrelid = 'public.admin_user'::regclass
           AND c.contype = 'f'
    LOOP
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', r.tbl, r.conname);
        EXECUTE format(
            'ALTER TABLE %s ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES app_user(id)',
            r.tbl, r.conname, r.col);
        RAISE NOTICE '% .% → app_user(id)', r.tbl, r.col;
    END LOOP;
END $$;

-- 3. 지운다 ------------------------------------------------------------
DROP TABLE IF EXISTS admin_user;
DROP TYPE IF EXISTS admin_role;
