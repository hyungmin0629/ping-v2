-- =====================================================================
-- integrity.sql · 적재 후 정합성 검사
-- =====================================================================
-- 각 행은 (검사명, 심각도, 실패건수) 를 돌려준다.
-- 실패건수가 0이 아니면 문제다.
--
-- FK·NOT NULL·UNIQUE 는 DB가 이미 막으므로 여기서 다시 세지 않는다.
-- 여기서 보는 것은 "제약으로는 표현할 수 없는" 규칙들이다.
-- =====================================================================

-- 1. 하트 원장이 잔액을 설명하는가
--    구 시스템의 가장 큰 결함이 재발했는지 확인하는 검사다.
SELECT '하트 원장 vs 잔액 불일치' AS check_name, 'HIGH' AS severity, count(*) AS failures
FROM (
    SELECT u.id, u.heart_balance,
           (SELECT t.balance_after FROM heart_transaction t
            WHERE t.user_id = u.id ORDER BY t.created_at DESC, t.id DESC LIMIT 1) AS last_balance
    FROM app_user u
) x
WHERE COALESCE(last_balance, 0) <> heart_balance

UNION ALL

-- 2. 원장의 델타 누적이 balance_after 와 맞는가
SELECT '원장 누적합 오류', 'HIGH', count(*)
FROM (
    SELECT id, balance_after,
           sum(delta) OVER (PARTITION BY user_id ORDER BY created_at, id) AS running
    FROM heart_transaction
) x
WHERE balance_after <> running

UNION ALL

-- 3. 잔액이 음수인 시점이 있는가
SELECT '음수 잔액 발생', 'HIGH', count(*)
FROM heart_transaction WHERE balance_after < 0

UNION ALL

-- 4. 하트를 낸 힌트 구매에 대응하는 원장이 있는가
--    구 시스템은 결제가 원장에 안 남아 잔액 재구성이 불가능했다.
--
--    ⚠️ heart_cost = 0 은 뺀다. W14 에서 **광고로 여는 무료 힌트**가 생겼고,
--       하트가 움직이지 않았으므로 원장에 행이 없는 것이 옳다. 원장은 하트의
--       움직임을 적는 곳이지 힌트를 연 사실을 적는 곳이 아니다.
--       (그 사실은 hint_purchase 자신과 ad_impression 이 남긴다)
--       이 조건이 없던 동안 광고로 연 힌트 4건이 위반으로 잡혔다 — 데이터가
--       아니라 검사가 낡은 것이었다.
SELECT '원장 없는 유료 힌트 구매', 'HIGH', count(*)
FROM hint_purchase h
WHERE h.heart_cost > 0
  AND NOT EXISTS (SELECT 1 FROM heart_transaction t WHERE t.hint_purchase_id = h.id)

UNION ALL

-- 5. 성공한 충전에 대응하는 원장이 있는가
SELECT '원장 없는 충전', 'HIGH', count(*)
FROM heart_purchase p
WHERE p.status = 'SUCCESS'
  AND NOT EXISTS (SELECT 1 FROM heart_transaction t WHERE t.purchase_id = p.id)

UNION ALL

-- 6. 시간 순서: 활동이 가입보다 앞설 수 없다
SELECT '가입 이전 활동', 'HIGH', count(*)
FROM vote_item v JOIN app_user u ON u.id = v.user_id
WHERE v.served_at < u.created_at

UNION ALL

SELECT '가입 이전 세션', 'HIGH', count(*)
FROM user_session s JOIN app_user u ON u.id = s.user_id
WHERE s.started_at < u.created_at

UNION ALL

-- 7. 투표는 출제 이후에 이뤄져야 한다
SELECT '출제 이전 투표', 'HIGH', count(*)
FROM vote_item WHERE voted_at IS NOT NULL AND voted_at < served_at

UNION ALL

-- 8. 친구를 5명 맺어본 적이 없는데 서비스가 해금된 유저
--
-- ⚠️ 예전에는 "지금 친구<5인데 해금"이었다. 그건 **설계와 어긋난 검사**였다.
--    refresh_friend_state 는 service_unlocked_at 을 한 번 찍으면 유지한다
--    (이미 연 서비스를 닫지 않는다 — 투표 기록이 쌓였을 수 있으므로).
--    친구가 줄어드는 경로가 관리자 삭제뿐이던 시절에는 안 드러났는데,
--    W19 에서 친구 끊기를 열면서 **정상 이용자가 이 검사에 걸리게 됐다.**
--
--    끊은 관계도 행으로 남으므로(friendship.ended_at) 이제 제대로 물을 수 있다 —
--    "지금 5명인가"가 아니라 "통틀어 5명을 맺어본 적이 있는가".
SELECT '게이트 위반(5명을 맺어본 적 없는데 해금)', 'HIGH', count(*)
FROM app_user u
WHERE u.service_unlocked_at IS NOT NULL
  AND (SELECT count(*) FROM friendship f
        WHERE f.user_low_id = u.id OR f.user_high_id = u.id) < 5

UNION ALL

-- 9. 투표했는데 선택된 후보가 없는 아이템
SELECT '선택 없는 완료 투표', 'HIGH', count(*)
FROM vote_item v
WHERE v.voted_at IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM vote_candidate c WHERE c.vote_item_id = v.id AND c.is_chosen)

UNION ALL

-- 10. 후보가 4명이 아닌 라운드
SELECT '후보 4명이 아닌 라운드', 'MEDIUM', count(*)
FROM (
    SELECT vote_item_id, shuffle_round, count(*) n
    FROM vote_candidate GROUP BY vote_item_id, shuffle_round
) x WHERE n <> 4

UNION ALL

-- 11. 셔플했는데 광고를 끝까지 보지 않은 기록
SELECT '광고 미완료 셔플', 'HIGH', count(*)
FROM vote_shuffle s JOIN ad_impression a ON a.id = s.ad_impression_id
WHERE a.status <> 'COMPLETED'

UNION ALL

-- 12. 후보가 투표자의 친구가 아닌 경우
--     세 스코프 모두 친구 안에서 뽑아야 한다(GLOBAL = 친구 전체)
--
--     ★ ended_at 을 일부러 안 본다. 지금 친구인지가 아니라 **투표 당시 친구였는지**를
--       묻는 검사이기 때문이다. 끊은 관계도 행으로 남으므로(W19) 옛 투표가
--       그대로 설명된다. 여기에 `ended_at IS NULL` 을 붙이면 친구를 끊는 순간
--       그 사람이 나온 옛 투표가 전부 위반으로 잡힌다.
SELECT '친구 아닌 후보', 'HIGH', count(*)
FROM vote_candidate c
JOIN vote_item v ON v.id = c.vote_item_id
WHERE NOT EXISTS (
    SELECT 1 FROM friendship f
    WHERE (f.user_low_id = LEAST(v.user_id, c.candidate_user_id)
       AND f.user_high_id = GREATEST(v.user_id, c.candidate_user_id))
)

UNION ALL

-- 13. CLASS 스코프인데 다른 반 후보가 채운 수보다 많다
--     같은 반 친구가 4명이 안 되면 다른 친구로 채운다(vote_item.padded_count).
--     그래서 "타반 후보가 있다"가 아니라 "채운 것보다 많다"를 결함으로 본다.
SELECT 'CLASS 스코프에 설명 안 되는 타반 후보', 'HIGH', count(*)
FROM (
    SELECT v.id
    FROM vote_item v
    JOIN app_user voter ON voter.id = v.user_id
    JOIN vote_candidate c ON c.vote_item_id = v.id
    JOIN app_user cand ON cand.id = c.candidate_user_id
    WHERE v.candidate_scope = 'CLASS'
      -- 셔플하면 후보가 두 벌(라운드 0·1) 쌓이는데 padded_count 는 **마지막
      -- 라운드**의 값이다. 두 벌을 함께 세면 항상 초과로 잡힌다.
      AND c.shuffle_round = v.shuffle_count
      -- 투표한 뒤 소속을 바꾸면(W11 프로필 수정) 그때는 같은 반이던 후보가
      -- 지금은 타반으로 보인다. 출제 시점의 반을 저장하지 않으므로
      -- 되짚을 수 없다. 프로필이 그 뒤에 바뀐 건은 판정에서 뺀다.
      AND voter.updated_at <= v.served_at
      AND cand.updated_at  <= v.served_at
    GROUP BY v.id, v.padded_count, voter.class_id
    HAVING count(*) FILTER (WHERE cand.class_id <> voter.class_id) > v.padded_count
) t

UNION ALL

-- 14. SCHOOL 스코프인데 다른 학교 후보가 채운 수보다 많다 (13번과 같은 이유)
SELECT 'SCHOOL 스코프에 설명 안 되는 타교 후보', 'HIGH', count(*)
FROM (
    SELECT v.id
    FROM vote_item v
    JOIN app_user voter ON voter.id = v.user_id
    JOIN grade_class vc ON vc.id = voter.class_id
    JOIN vote_candidate c ON c.vote_item_id = v.id
    JOIN app_user cand ON cand.id = c.candidate_user_id
    JOIN grade_class cc ON cc.id = cand.class_id
    WHERE v.candidate_scope = 'SCHOOL'
      -- 13번과 같은 이유다(셔플 라운드, 그 뒤의 소속 변경)
      AND c.shuffle_round = v.shuffle_count
      AND voter.updated_at <= v.served_at
      AND cand.updated_at  <= v.served_at
    GROUP BY v.id, v.padded_count, vc.school_id
    HAVING count(*) FILTER (WHERE cc.school_id <> vc.school_id) > v.padded_count
) t

UNION ALL

-- 15. 자기 자신이 후보로 등장
SELECT '자기 자신이 후보', 'HIGH', count(*)
FROM vote_candidate c JOIN vote_item v ON v.id = c.vote_item_id
WHERE c.candidate_user_id = v.user_id

UNION ALL

-- 16. friend_count 가 실제 친구 수와 다른가
-- friend_count 는 **살아 있는** 관계만 센다(refresh_friend_state 와 같은 기준).
-- 12번과 반대로 여기서는 ended_at 을 봐야 한다.
SELECT 'friend_count 불일치', 'MEDIUM', count(*)
FROM app_user u
WHERE u.friend_count <> (
    SELECT count(*) FROM friendship f
    WHERE (f.user_low_id = u.id OR f.user_high_id = u.id)
      AND f.ended_at IS NULL
)

ORDER BY 3 DESC, 1;
