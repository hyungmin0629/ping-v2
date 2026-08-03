-- =====================================================================
-- 90_seed_master.sql · 마스터/룩업 테이블 기초 데이터
-- =====================================================================
-- 여기 담기는 것은 "서비스 정의"에 해당하는 값들이다.
-- 합성 데이터(유저·투표·활동)는 별도 생성 스크립트가 담당한다.
-- 재실행해도 안전하도록 ON CONFLICT DO NOTHING 을 쓴다.
-- =====================================================================

-- 탈퇴 사유 -----------------------------------------------------------
-- 구 스키마는 자유 varchar 라 '기타 이유'와 '기타'가 별도로 쌓였다.
-- 여기서는 코드를 고정하고, 세부 사정은 user_withdrawal.reason_text 로 받는다.
INSERT INTO withdrawal_reason (code, label, sort_order) VALUES
    ('NO_FRIENDS',    '함께 할 친구가 없어서',   1),
    ('BORING_CONTENT','재밌는 질문이 없어서',    2),
    ('TOO_MANY_BUGS', '오류가 많아서',           3),
    ('PRIVACY',       '개인정보가 걱정돼서',     4),
    ('NOT_USING',     '더 이상 사용하지 않아서', 5),
    ('OTHER',         '기타',                    9)
ON CONFLICT (code) DO NOTHING;

-- 하트 거래 유형 -------------------------------------------------------
-- is_credit = true 는 적립, false 는 차감.
INSERT INTO heart_transaction_type (code, label, is_credit) VALUES
    ('SIGNUP_GRANT',  '가입 지급',       true),
    ('VOTE_REWARD',   '투표 참여 적립',  true),
    ('AD_REWARD',     '광고 시청 보상',  true),
    ('TOPUP',         '하트 충전',       true),
    ('EVENT_GRANT',   '이벤트 지급',     true),
    ('ADMIN_ADJUST',  '운영자 조정',     true),
    ('REFUND',        '환불 회수',       false),
    ('HINT_PURCHASE', '힌트 구매',       false)
ON CONFLICT (code) DO NOTHING;

-- 충전 상품 -----------------------------------------------------------
-- 구 서비스의 실제 상품 구성을 참고했다.
-- 다만 v1 클로즈드 테스트에서는 실결제를 붙이지 않으므로 정의만 둔다.
INSERT INTO heart_product (product_code, heart_amount, price_krw, label) VALUES
    ('heart.200',   200,   900,  NULL),
    ('heart.777',   777,   1900, '가장 많이 선택'),
    ('heart.1000',  1000,  2900, NULL),
    ('heart.4000',  4000,  9900, '최고 가성비')
ON CONFLICT (product_code) DO NOTHING;

-- 질문 카테고리 --------------------------------------------------------
-- 외모/신체 카테고리는 정의는 두되 is_active = false 로 막아둔다.
-- 구 서비스에서 신고 상위 5개 질문을 이 카테고리가 독점했기 때문이다.
INSERT INTO question_category (code, name, is_sensitive, sort_order, is_active) VALUES
    ('PERSONALITY',  '성격',      false, 1, true),
    ('RELATIONSHIP', '관계',      false, 2, true),
    ('TALENT',       '재능',      false, 3, true),
    ('HUMOR',        '유머',      false, 4, true),
    ('SCHOOL_LIFE',  '학교생활',  false, 5, true),
    ('FUTURE',       '미래',      false, 6, true),
    ('TASTE',        '취향',      false, 7, true),
    ('APPEARANCE',   '외모·신체', true,  9, true)
ON CONFLICT (code) DO NOTHING;

-- 신고 사유 -----------------------------------------------------------
INSERT INTO report_reason (code, label, target_type) VALUES
    ('U_HARASSMENT',   '괴롭힘·비하',       'USER'),
    ('U_IMPERSONATION','사칭',              'USER'),
    ('U_SPAM',         '스팸·광고',         'USER'),
    ('U_INAPPROPRIATE','부적절한 행동',     'USER'),
    ('Q_OFFENSIVE',    '불쾌한 질문',       'QUESTION'),
    ('Q_APPEARANCE',   '외모 비하 소지',    'QUESTION'),
    ('Q_SEXUAL',       '선정적 내용',       'QUESTION'),
    ('Q_ETC',          '기타',              'QUESTION'),
    ('P_ABUSE',        '욕설·비방',         'POST'),
    ('P_SEXUAL',       '선정적 내용',       'POST'),
    ('P_SPAM',         '스팸·광고',         'POST'),
    ('C_ABUSE',        '욕설·비방',         'COMMENT'),
    ('C_SPAM',         '스팸·광고',         'COMMENT')
ON CONFLICT (code) DO NOTHING;

-- 자동 제재 정책 -------------------------------------------------------
-- 구 시스템은 253회 신고받은 유저도 정상 상태였다.
-- 임계값을 데이터로 못 박아 정책이 감사 가능하게 한다.
INSERT INTO sanction_policy (name, target_type, threshold_count, window_days, action_type, action_days) VALUES
    ('유저 신고 5회 → 경고',      'USER',    5,  30, 'WARNING', NULL),
    ('유저 신고 10회 → 7일 정지', 'USER',    10, 30, 'SUSPEND', 7),
    ('유저 신고 20회 → 영구 정지','USER',    20, 90, 'BAN',     NULL),
    ('게시글 신고 5회 → 숨김',    'POST',    5,  7,  'MUTE',    NULL),
    ('댓글 신고 5회 → 숨김',      'COMMENT', 5,  7,  'MUTE',    NULL);

-- 게시판 카테고리 ------------------------------------------------------
-- v1 미개통이지만 마스터는 미리 넣어둔다.
INSERT INTO board_category (code, name, description, sort_order) VALUES
    ('FREE',    '자유게시판', '아무 이야기나',           1),
    ('CAREER',  '진로',       '진학·직업 고민',          2),
    ('LOVE',    '연애',       '연애 상담과 잡담',        3),
    ('HOBBY',   '취미',       '관심사 공유',             4),
    ('COUNSEL', '고민상담',   '털어놓고 싶은 이야기',    5)
ON CONFLICT (code) DO NOTHING;
