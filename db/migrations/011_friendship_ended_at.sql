-- =====================================================================
-- 011 · 친구 끊기 — 지우지 않고 끝난 시각을 남긴다 (W19)
-- =====================================================================
-- 왜 소프트 삭제인가:
--   행을 지우면 "친구였다가 끊었다"는 사실이 통째로 사라진다.
--   친구 끊기는 소셜 서비스에서 **관계 이탈 신호**다 — 이걸 못 보면
--   "왜 떠났나"에 답할 수 없다.
--
--   이 프로젝트가 구 서비스에서 가장 크게 물린 것이 정확히 그 형태였다.
--   탈퇴 기록 70,764건에 유저 식별자가 없어 이탈 분석이 원천 불가능했다.
--   같은 실수를 친구 관계에서 반복하지 않는다.
--
--   판단이 갈릴 때의 기준도 이미 정해져 있다 — "분석할 데이터가 남는가".
--
-- UNIQUE 를 부분 인덱스로 바꾸는 이유:
--   끊은 행이 남아 있으면 (A,B) UNIQUE 때문에 **다시 친구가 될 수 없다.**
--   살아 있는 관계에만 UNIQUE 를 걸어야 한다. 그러면 끊었다 다시 맺기가
--   되고, 덤으로 **몇 번 끊었다 붙었나**가 행 수로 남는다.
--
--   friend_request 도 같은 이유로 바꾼다. 옛 ACCEPTED 행이 남아 있으면
--   다시 요청을 보낼 수 없다. PENDING 인 것만 하나여야 한다.
--
-- 다시 돌려도 안전하다.
-- =====================================================================

-- 1. 끝난 시각 --------------------------------------------------------
ALTER TABLE friendship ADD COLUMN IF NOT EXISTS ended_at timestamptz;

COMMENT ON COLUMN friendship.ended_at IS
    '친구를 끊은 시각. NULL 이면 살아 있는 관계다. 행은 지우지 않는다 — '
    '끊었다는 사실이 관계 이탈 신호이기 때문.';

-- 2. UNIQUE → 살아 있는 관계에만 --------------------------------------
ALTER TABLE friendship DROP CONSTRAINT IF EXISTS uq_friendship;
CREATE UNIQUE INDEX IF NOT EXISTS uq_friendship_active
    ON friendship (user_low_id, user_high_id) WHERE ended_at IS NULL;

-- 끊은 관계도 찾아야 한다(이력 조회·정합성 검사).
CREATE INDEX IF NOT EXISTS idx_friendship_ended ON friendship (ended_at);

-- 3. friend_request 도 같은 처리 --------------------------------------
-- 옛 ACCEPTED/REJECTED 행이 남아 있어도 새 요청을 보낼 수 있어야 한다.
ALTER TABLE friend_request DROP CONSTRAINT IF EXISTS uq_friend_request;
CREATE UNIQUE INDEX IF NOT EXISTS uq_friend_request_pending
    ON friend_request (sender_id, receiver_id) WHERE status = 'PENDING';
