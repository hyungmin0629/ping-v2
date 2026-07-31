-- =====================================================================
-- hangul.sql · 한글 자모 분해·조합 (W14)
-- =====================================================================
-- 힌트가 "랜덤 글자의 초성/중성/종성"을 하나씩 연다. 그 계산을 화면에 두면
-- **아직 사지 않은 자모가 브라우저로 나간다.** 가려야 할 것을 보낸 뒤
-- 화면에서 숨기는 것은 가린 것이 아니다.
--
-- 한글 음절은 U+AC00 부터 규칙적으로 배열돼 있다.
--     코드 = (초성×21 + 중성)×28 + 종성 + 0xAC00
-- 그래서 나누기와 나머지만으로 분해되고, 거꾸로 조합도 된다.
--
-- 재실행해도 안전하다.
-- =====================================================================

-- 자모 표. 순서가 유니코드 배열 순서 그대로여야 한다.
CREATE OR REPLACE FUNCTION public.hangul_lead(i int)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT (ARRAY['ㄱ','ㄲ','ㄴ','ㄷ','ㄸ','ㄹ','ㅁ','ㅂ','ㅃ','ㅅ','ㅆ','ㅇ',
                  'ㅈ','ㅉ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ'])[i + 1]
$$;

CREATE OR REPLACE FUNCTION public.hangul_vowel(i int)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT (ARRAY['ㅏ','ㅐ','ㅑ','ㅒ','ㅓ','ㅔ','ㅕ','ㅖ','ㅗ','ㅘ','ㅙ','ㅚ',
                  'ㅛ','ㅜ','ㅝ','ㅞ','ㅟ','ㅠ','ㅡ','ㅢ','ㅣ'])[i + 1]
$$;

-- 0번은 받침 없음이다. 빈 문자열을 돌려준다.
CREATE OR REPLACE FUNCTION public.hangul_tail(i int)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT (ARRAY['','ㄱ','ㄲ','ㄳ','ㄴ','ㄵ','ㄶ','ㄷ','ㄹ','ㄺ','ㄻ','ㄼ','ㄽ',
                  'ㄾ','ㄿ','ㅀ','ㅁ','ㅂ','ㅄ','ㅅ','ㅆ','ㅇ','ㅈ','ㅊ','ㅋ',
                  'ㅌ','ㅍ','ㅎ'])[i + 1]
$$;


-- ---------------------------------------------------------------------
-- 자모 하나만 드러낸 이름
-- ---------------------------------------------------------------------
-- 힌트 하나가 **글자 하나의 자모 하나**를 연다. 나머지는 전부 ○ 다.
-- 세 힌트(초·중·종성)는 서로 다른 글자를 가리키므로 합치지 않고 따로 그린다.
--
--     mask_jamo('김형민', 1, 'lead')   →  ○ㅎ○
--     mask_jamo('김형민', 2, 'vowel')  →  ○○ㅣ
--     mask_jamo('김형민', 0, 'tail')   →  ㅁ○○
CREATE OR REPLACE FUNCTION public.jamo_of(p_char text, p_part text)
RETURNS text
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE v_code int;
BEGIN
    IF p_char IS NULL OR p_char = '' THEN
        RETURN NULL;
    END IF;
    v_code := ascii(p_char) - 44032;              -- 0xAC00
    -- 한글 음절이 아니면(영문·숫자) 자모가 없다. 글자를 그대로 보여준다 —
    -- 가릴 자모가 없는데 ○ 로 덮으면 산 사람이 아무것도 못 받는다.
    IF v_code < 0 OR v_code > 11171 THEN
        RETURN p_char;
    END IF;

    RETURN CASE p_part
        WHEN 'lead'  THEN public.hangul_lead(v_code / 588)
        WHEN 'vowel' THEN public.hangul_vowel((v_code % 588) / 28)
        -- 받침이 없는 글자다. 그것도 정보이므로 그렇게 알린다.
        WHEN 'tail'  THEN coalesce(nullif(public.hangul_tail(v_code % 28), ''), '_')
    END;
END;
$$;

CREATE OR REPLACE FUNCTION public.mask_jamo(p_nick text, p_index int, p_part text)
RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT string_agg(
        CASE WHEN i - 1 = p_index
             THEN coalesce(public.jamo_of(substr(p_nick, i, 1), p_part), '○')
             ELSE '○' END, '' ORDER BY i)
      FROM generate_series(1, char_length(coalesce(p_nick, ''))) AS i
$$;


-- ---------------------------------------------------------------------
-- 어느 글자를 뽑을까
-- ---------------------------------------------------------------------
-- 아무 글자나 뽑으면 종성 힌트가 "받침 없음"만 돌려주는 일이 잦다.
-- 20하트를 받고 파는 정보이므로 **줄 것이 있는 글자를 먼저** 고른다.
-- 전부 받침이 없으면 그냥 무작위로 고른다 — 그때는 "받침이 없다"가 진짜 정보다.
CREATE OR REPLACE FUNCTION public.pick_hint_char(p_nick text, p_part text)
RETURNS smallint
LANGUAGE sql VOLATILE AS $$
    WITH scored AS (
        SELECT i - 1 AS idx,
               (p_part <> 'tail'
                OR public.jamo_of(substr(p_nick, i, 1), 'tail') <> '_') AS useful
          FROM generate_series(1, char_length(coalesce(p_nick, ''))) AS i
    )
    SELECT coalesce(
        (SELECT idx FROM scored WHERE useful ORDER BY random() LIMIT 1),
        (SELECT idx FROM scored ORDER BY random() LIMIT 1),
        0)::smallint
$$;

REVOKE ALL ON FUNCTION public.hangul_lead(int)  FROM public;
REVOKE ALL ON FUNCTION public.hangul_vowel(int) FROM public;
REVOKE ALL ON FUNCTION public.hangul_tail(int)  FROM public;
REVOKE ALL ON FUNCTION public.jamo_of(text, text)        FROM public;
REVOKE ALL ON FUNCTION public.mask_jamo(text, int, text) FROM public;
REVOKE ALL ON FUNCTION public.pick_hint_char(text, text) FROM public;

-- 006 시절의 "한 글자를 조금씩 완성" 함수들. 쓰는 곳이 없다.
DROP FUNCTION IF EXISTS public.mask_nickname(text, int, boolean, boolean, boolean);
DROP FUNCTION IF EXISTS public.hangul_partial(text, boolean, boolean, boolean);
