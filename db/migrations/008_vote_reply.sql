-- =====================================================================
-- 008_vote_reply.sql · 받은 투표에 1회성 답장 (W15)
-- =====================================================================
-- 나를 뽑은 사람에게 짧은 말을 **한 번** 보낸다. 20하트, 30자.
-- 힌트를 열었든 안 열었든 보낼 수 있다 — 누군지 몰라도 고맙다고 할 수는 있다.
--
-- 왜 vote_received 에 붙이나:
--   답장은 받은 투표 한 건에 **최대 하나**다. 별도 테이블을 만들면 "하나만"을
--   UNIQUE 로 강제해야 하는데, 컬럼으로 두면 NULL 여부가 곧 그 제약이다.
--   1:N 이 될 여지가 생기면 그때 테이블로 뽑는다.
--
-- answer_status 는 이미 있다(NONE/PUBLIC/PRIVATE). 답장은 뽑은 사람에게만
-- 가므로 PRIVATE 로 표시한다. 원래 그 컬럼이 하려던 일이 이것이다.
--
-- ⚠️ **자유 텍스트가 사람에게 직접 간다.** design-spec 2.2 는 이런 기능 앞에
--    차단 화면이 먼저 있어야 한다고 적어두었다. 30자·1회성이라 위험이 훨씬
--    작지만 0은 아니다. 그래서 받은 답장을 신고하는 길을 함께 연다
--    (db/rls/replies.sql 의 report_user).
--
-- 재실행해도 안전하다.
-- =====================================================================

ALTER TABLE vote_received
    ADD COLUMN IF NOT EXISTS reply_text varchar(30),
    ADD COLUMN IF NOT EXISTS replied_at timestamptz;

COMMENT ON COLUMN vote_received.reply_text IS
    '지목당한 사람이 뽑은 사람에게 보내는 한 번뿐인 답장(30자). NULL 이면 아직 안 보냈다';

-- 답장 값은 한 번 정해지면 바뀌지 않는다. 보낸 시각이 없으면 내용도 없어야 한다.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_reply_pair') THEN
        ALTER TABLE vote_received ADD CONSTRAINT ck_reply_pair CHECK (
            (reply_text IS NULL AND replied_at IS NULL)
         OR (reply_text IS NOT NULL AND replied_at IS NOT NULL));
    END IF;
END $$;

-- 하트 거래 유형. 원장은 type_code 로 의미를 읽으므로 새 소비처를 등록한다.
-- 구 스키마는 delta 값만 보고 의미를 역추론해야 했다 — 그 자리를 만들지 않는다.
INSERT INTO heart_transaction_type (code, label, is_credit)
VALUES ('VOTE_REPLY', '답장 보내기', false)
ON CONFLICT (code) DO NOTHING;
