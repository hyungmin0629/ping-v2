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
-- 한 글자를 부분만 아는 상태로 그린다
-- ---------------------------------------------------------------------
-- 초성과 중성을 둘 다 알면 **음절로 합친다**(ㅎ + ㅕ → 혀). 종성까지 알면 형.
-- 합칠 수 없으면 아는 자모만 나열한다. 이렇게 해야 사는 순서에 따라
-- 글자가 조금씩 또렷해지는 것이 눈에 보인다.
CREATE OR REPLACE FUNCTION public.hangul_partial(
    p_char    text,
    p_lead    boolean,      -- 초성을 샀는가
    p_vowel   boolean,
    p_tail    boolean
)
RETURNS text
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    v_code int;
    v_l int; v_v int; v_t int;
BEGIN
    IF p_char IS NULL OR p_char = '' THEN
        RETURN '○';
    END IF;

    v_code := ascii(p_char) - 44032;          -- 0xAC00
    -- 한글 음절이 아니면(영문·숫자·기호) 자모가 없다. 산 것이 하나라도
    -- 있으면 글자를 그대로 보여준다 — 가릴 자모가 애초에 없기 때문이다.
    IF v_code < 0 OR v_code > 11171 THEN
        RETURN CASE WHEN p_lead OR p_vowel OR p_tail THEN p_char ELSE '○' END;
    END IF;

    v_l := v_code / 588;
    v_v := (v_code % 588) / 28;
    v_t := v_code % 28;

    IF p_lead AND p_vowel THEN
        -- 종성을 아직 안 샀으면 받침 없이 합친다(혀). 사면 받침이 붙는다(형).
        RETURN chr(44032 + (v_l * 21 + v_v) * 28 + CASE WHEN p_tail THEN v_t ELSE 0 END);
    END IF;

    RETURN coalesce(
        nullif(concat(
            CASE WHEN p_lead  THEN public.hangul_lead(v_l)  END,
            CASE WHEN p_vowel THEN public.hangul_vowel(v_v) END,
            CASE WHEN p_tail  THEN public.hangul_tail(v_t)  END), ''),
        '○');
END;
$$;


-- ---------------------------------------------------------------------
-- 이름 전체를 마스킹한다
-- ---------------------------------------------------------------------
-- 힌트가 가리키는 글자만 부분 공개하고 나머지는 ○ 로 덮는다.
--     김형민 · index 1 · 초성만    →  ○ㅎ○
--     김형민 · index 1 · 초성+중성 →  ○혀○
--     김형민 · index 1 · 셋 다      →  ○형○
CREATE OR REPLACE FUNCTION public.mask_nickname(
    p_nick  text,
    p_index int,
    p_lead  boolean,
    p_vowel boolean,
    p_tail  boolean
)
RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT string_agg(
        CASE WHEN i - 1 = p_index
             THEN public.hangul_partial(substr(p_nick, i, 1), p_lead, p_vowel, p_tail)
             ELSE '○' END, '' ORDER BY i)
      FROM generate_series(1, char_length(coalesce(p_nick, ''))) AS i
$$;

REVOKE ALL ON FUNCTION public.hangul_lead(int)    FROM public;
REVOKE ALL ON FUNCTION public.hangul_vowel(int)   FROM public;
REVOKE ALL ON FUNCTION public.hangul_tail(int)    FROM public;
REVOKE ALL ON FUNCTION public.hangul_partial(text, boolean, boolean, boolean) FROM public;
REVOKE ALL ON FUNCTION public.mask_nickname(text, int, boolean, boolean, boolean) FROM public;
