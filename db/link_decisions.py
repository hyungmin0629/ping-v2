"""결정 노드끼리 "이어지는 결정" 절을 붙인다. (위키 2계층 · 교차 참조)

사용법:
    python db/link_decisions.py     # 다시 돌려도 안전하다 (옛 블록을 걷고 새로 쓴다)

새 결정을 추가한 뒤 관계를 맺으려면 아래 PAIRS 에 한 줄 넣고 다시 돌린다.

왜 손으로 정하나:
    같은 표를 건드린다고 관련된 결정이 아니다. heart_transaction 을 언급하는
    결정이 6개인데 그중 둘은 하트 설계고 넷은 그냥 스쳐 지나간다.
    기계로 이으면 노이즈가 생기고, 노이즈가 있는 링크는 아무도 안 따라간다.

    그래서 짝마다 **왜 이어지는지**를 한 줄로 적는다. 그 한 줄을 못 쓰겠으면
    관련된 결정이 아니다.
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DEC = ROOT / "docs" / "decisions"

# (a, b, 왜 이어지는가) — 양쪽에서 같은 문장으로 읽히게 쓴다
PAIRS = [
    # ── 합성 데이터 v3 (2026-08-04) ──────────────────────────────────
    ("daily-rhythm-night-peak", "user-personas",
     "둘 다 **유형을 두되 또렷하지 않게** 흐린다 — 규칙을 벗어나는 사람이 있어야 한다"),
    ("daily-rhythm-night-peak", "growth-curve-two-channels",
     "시각을 정하는 두 축 — 곡선이 **어느 날**인지, 리듬이 **몇 시**인지"),
    ("never-voters-by-friend-count", "expired-session-status",
     "둘 다 **기록이 실제 행동과 어긋난** 경우다. 사고로 생긴 상태를 설계된 상태로 바꿨다"),
    ("never-voters-by-friend-count", "friendship-ended-at",
     "친구 수가 곧 서비스 경험을 가른다 — 맺는 쪽과 끊는 쪽"),
    ("class-size-for-class-scope", "pad-candidates-keep-scope",
     "같은 반 후보가 4명이 안 될 때 무엇을 하는가 — 채우거나(앞), 애초에 모자라지 않게 하거나(뒤)"),
    ("class-size-for-class-scope", "retention-quarter-tier",
     "둘 다 **실측을 그대로 쓰면 분석이 성립하지 않아** 의도적으로 벗어난 값이다"),
    ("class-size-for-class-scope", "school-sequential-adoption",
     "학급 크기가 인기도와 CLASS 스코프를 동시에 좌우한다 — 상한 35명이 그 균형점"),
    ("growth-curve-two-channels", "spring-spike-growth-curve",
     "앞은 곡선을 **어떻게 거는가**(가입·활동 두 갈래), 뒤는 곡선의 **모양**을 정한다"),
    ("spring-spike-growth-curve", "reactivation-cohort",
     "둘 다 봄학기(3월)에 무게를 싣는다 — 신규 유입과 복귀가 같은 달에 겹친다"),
    ("school-sequential-adoption", "spring-spike-growth-curve",
     "가입일을 먼저 뽑고 학교를 나중에 고르는 순서가 **성장 곡선을 보존한다**"),
    ("school-sequential-adoption", "popularity-floor-is-activity",
     "학급 크기가 인기도 쏠림을 좌우한다 — 반이 커지면 학급 안 순위 스프레드가 커진다"),
    ("popularity-floor-is-activity", "activity-by-retention-tier",
     "지목 쏠림의 바닥은 **활동 불균형**이다. 활동 강도를 정한 결정이 인기도를 정한 셈"),
    ("retention-quarter-tier", "activity-by-retention-tier",
     "앞은 구간을 **늘리고**, 뒤는 구간마다 활동 강도를 **정한다**"),
    ("retention-quarter-tier", "user-personas",
     "둘 다 v1 실측을 그대로 쓰지 않는다 — 분석 가능성을 위해 의도적으로 흐리거나 늘렸다"),
    ("sensitive-question-report-weight", "appearance-questions-for-report-rate",
     "카테고리를 연 것만으로는 부족했다. **신고 성향을 심어야** 목적이 달성된다"),
    ("expired-session-status", "integrity-checks-aged",
     "둘 다 **측정이 틀린** 경우다 — 데이터가 아니라 재는 방법이 문제였다"),
    ("generator-emits-updated-at", "backfill-updated-at",
     "같은 문제의 두 해법 — 적재 뒤 고치기(옛것) vs 처음부터 맞게 넣기(새것)"),
    ("generator-emits-updated-at", "row-cap-to-query-cap",
     "둘 다 **규모가 커지자 드러난** 문제다. 작은 샘플에서는 보이지 않았다"),

    # 구 서비스의 분석 불가 지점을 닫는다
    ("heart-unify-point", "heart-balance-after",
     "하트 원장 설계 한 쌍 — 통화를 하나로 합치고, 거래마다 직후 잔액을 남긴다"),
    ("heart-balance-after", "withdrawal-user-id",
     "둘 다 구 서비스에서 **분석이 원천 불가능했던 지점**을 닫는다"),
    ("withdrawal-user-id", "withdraw-keeps-rows",
     "탈퇴를 분석 가능하게 만드는 두 축 — 누가 나갔는지, 그리고 흔적을 지우지 않는 것"),
    ("withdraw-keeps-rows", "friendship-ended-at",
     "지우지 않고 끝난 표시만 남긴다. 같은 판단을 계정과 관계에 각각 적용했다"),
    ("report-sanction-fk", "remove-circular-fk",
     "관계를 DB 에 선언한다. 구 서비스는 FK 39개 중 17개만 걸려 있었다"),

    # 쓰기는 RPC 로만
    ("client-write-minimal", "signup-single-rpc",
     "쓰기를 RPC 하나로 좁힌다는 원칙과, 그 첫 적용"),
    ("client-write-minimal", "profile-edit-rpc",
     "직접 UPDATE 권한을 회수하고 RPC 로 몬다"),
    ("client-write-minimal", "school-info-write-revoked",
     "권한을 아예 주지 않는 것이 **정책 실수를 사고로 만들지 않는 길**이다"),
    ("client-write-minimal", "voter-identity-view-only",
     "읽기도 필요한 만큼만. 유료 정보는 뷰로 가린다"),
    ("voter-identity-view-only", "selectable-hints",
     "\"누가 나를 뽑았나\"가 이 서비스가 파는 정보다. 가리는 방식과 값 매기는 방식"),

    # 개인정보를 안 받는다
    ("anonymous-auth-no-pii", "gender-at-onboarding",
     "개인정보를 안 받는다는 원칙 안에서 성별만 예외로 받는 이유"),
    ("anonymous-auth-no-pii", "friend-invite-code-two-step",
     "전화번호를 안 받으므로 **서로를 찾을 수단이 초대 코드뿐**이다"),
    ("anonymous-auth-no-pii", "supabase-session-pooler",
     "Supabase 를 쓰기로 한 뒤 마주친 접속 제약"),
    ("friend-invite-code-two-step", "friend-recommend-same-school",
     "\"초대 코드로만\"이라는 원칙을 같은 학교 범위에서 **좁게 연다**"),
    ("friend-recommend-same-school", "school-boundary-self-reported",
     "학교 경계를 근거로 삼는 기능과, 그 경계가 자기신고라는 한계"),
    ("friend-invite-code-two-step", "invite-link-querystring",
     "코드를 주고받는 통로. 링크로 만들 때 이 환경의 제약에 걸렸다"),

    # 투표 후보
    ("global-scope-is-friends", "pad-candidates-keep-scope",
     "후보는 친구 안에서만 뽑는다. 모자랄 때 스코프를 낮추지 않는 이유"),
    ("pad-candidates-keep-scope", "candidate-rows-kept",
     "채운 수를 남겨야 나중에 그 투표를 설명할 수 있다"),
    ("shuffle-once-constraint", "candidate-rows-kept",
     "셔플 전후를 모두 남기고, 횟수는 제약으로 막는다"),
    ("shuffle-once-constraint", "ads-payments-stub",
     "셔플에 광고를 붙였는데 MVP 의 그 광고가 스텁이다"),

    # 하트 경제
    ("heart-balance-after", "selectable-hints",
     "하트가 나가는 가장 큰 자리. 원장이 그것을 설명해야 한다"),
    ("selectable-hints", "one-time-reply",
     "하트 소비처 둘. 답장이 두 번째로 생긴 소비처다"),
    ("topup-stub-daily-limit", "ads-payments-stub",
     "MVP 의 스텁 둘 — 결제와 광고"),
    ("topup-stub-daily-limit", "heart-balance-after",
     "충전도 원장을 거친다. 구 서비스는 이게 빠져 잔액이 20억 어긋났다"),
    ("gender-at-onboarding", "selectable-hints",
     "성별을 온보딩에서 받는 이유가 **힌트로 팔기 위해서**다"),
    ("profile-edit-rpc", "gender-at-onboarding",
     "온보딩에서 받은 것을 나중에 고치는 경로"),
    ("one-time-reply", "voter-identity-view-only",
     "지목당한 쪽이 뽑은 쪽에게 말을 건다 — 이건 익명이 아니다"),

    # 적재
    ("watermark-updated-at", "backfill-updated-at",
     "증분 키를 통일하고, 대량 적재가 그것을 망가뜨리는 것을 되돌린다"),
    ("watermark-updated-at", "watermark-lag-5min",
     "워터마크를 무엇으로 삼고, 어디로 옮겨 저장하나"),
    ("bigquery-source-column", "join-requires-source",
     "원천을 컬럼으로 구분한 대가 — **조인마다 그것을 걸어야 한다**"),
    ("bigquery-source-column", "synthetic-real-separation",
     "원천은 나누고 적재는 한 표에. 두 결정이 짝이다"),
    ("no-delete-propagation", "soft-delete-marking",
     "삭제를 전파하지 않되 표시는 한다. 뒤 결정이 앞 결정을 보완한다"),
    ("soft-delete-marking", "friendship-ended-at",
     "지우지 않고 표시하는 방식을 적재층과 스키마에 각각 적용했다"),
    ("synthetic-real-separation", "purge-synthetic-data",
     "합성을 실데이터와 분리해 둔 덕에 **통째로 지울 수 있었다**"),
    ("bigquery-direct-no-gcs", "local-docker-airflow",
     "규모에 맞게 구성을 줄인 판단 둘"),
    ("local-docker-airflow", "airflow-two-services",
     "Airflow 를 이 프로젝트 크기로 줄인다"),

    # 게시판과 신고
    ("no-anonymous-board", "open-named-board",
     "익명이면 안 열고 이름이 붙으면 연다 — **전제가 무엇이었는지** 드러난다"),
    ("open-named-board", "board-school-scope",
     "게시판을 열면서 범위를 학교로 묶는다"),
    ("open-named-board", "report-first-block-later",
     "글을 열면 신고가 함께 필요하다"),
    ("report-first-block-later", "one-time-reply",
     "차단 화면 없이 1:1 텍스트를 열었다. **앞 결정이 미뤄둔 것을 뒤 결정이 앞당긴다**"),
    ("report-sanction-fk", "report-first-block-later",
     "신고를 받는 구조와, 그것을 언제 여는가"),
    ("board-school-scope", "school-boundary-self-reported",
     "범위를 학교로 묶었는데 그 학교가 자기신고다"),

    # 학교 데이터
    ("testers-pick-real-school", "org-borrows-school-info",
     "테스트 조직이 실제 학교의 정보를 빌려 쓰는 구조"),
    ("org-borrows-school-info", "events-on-meal-calendar",
     "빌려 온 학교 데이터를 어느 화면에 어떻게 얹나"),
    ("events-on-meal-calendar", "neis-merge-spans",
     "학사일정을 화면에 올리려면 NEIS 가 주는 모양을 먼저 바꿔야 했다"),
    ("org-borrows-school-info", "school-info-write-revoked",
     "빌려 쓰는 데이터의 읽기 경로와, 그 표의 쓰기 차단"),
    ("student-mvp-adult-testers", "testers-pick-real-school",
     "성인 테스터가 학생용 서비스에서 학교를 어떻게 고르나"),

    # 검사와 품질
    ("integrity-checks-aged", "friendship-ended-at",
     "친구 끊기를 열자 **정합성 검사 3종이 낡은 것으로 드러났다**"),
    ("integrity-checks-aged", "selectable-hints",
     "광고로 여는 무료 힌트가 원장 검사를 낡게 만들었다"),
    ("integrity-checks-aged", "local-db-via-apply",
     "검사가 조용히 안 돌던 사고. 스키마를 만드는 경로가 원인이었다"),
    ("local-db-via-apply", "remove-circular-fk",
     "스키마를 한 경로로만 만든다"),
    ("purge-synthetic-data", "integrity-checks-aged",
     "낡은 것을 지우고 고치는 판단 둘 — 데이터와 검사"),

    # 범위
    ("closed-test-adults", "student-mvp-adult-testers",
     "학생용을 만들고 성인이 검증한다. 그 대상과 방법"),
    ("webapp-first-track", "closed-test-adults",
     "웹앱을 먼저 만든 이유가 **실데이터를 얻는 것**이었다"),
    ("webapp-first-track", "ads-payments-stub",
     "MVP 범위를 어디까지로 자를 것인가"),
    ("invite-link-querystring", "history-based-navigation",
     "이 환경의 Next.js 제약을 우회한 판단 둘"),
    ("drop-admin-user", "client-write-minimal",
     "운영자 여부가 **유저가 UPDATE 하는 표**로 옮겨왔다 — 스스로 켤 수 없어야 한다"),
    ("drop-admin-user", "remove-circular-fk",
     "쓰지 않는 구조를 걷어내 스키마를 줄인 판단 둘"),

    # 합성 데이터 확정
    ("confirm-v4-with-known-limits", "purge-synthetic-data",
     "그때는 **틀려서** 버렸고 이번엔 **부족한 채로 쓴다** — 기준이 "
     "보관 가치가 아니라 '이 데이터로 답할 질문이 남는가'인 것은 같다"),
    ("confirm-v4-with-known-limits", "app-follows-generator",
     "생성이 확정된 **지금이 앱을 맞출 시점이다**"),
    ("confirm-v4-with-known-limits", "integrity-checks-aged",
     "검사는 쓰인 시점의 세계를 안다 — 탈퇴·제재 이후 활동을 **아무도 묻지 않았다**"),
    ("confirm-v4-with-known-limits", "reactivation-cohort",
     "복귀 736명은 `vote_session` 으로만 보인다 — `user_session` 으로 재면 **0명**이다"),
]

BLOCK = "## 이어지는 결정"


def main() -> int:
    nodes = {p.stem for p in DEC.glob("*.md")}
    rel: dict[str, list[tuple[str, str]]] = {}
    bad = 0
    for a, b, why in PAIRS:
        for x in (a, b):
            if x not in nodes:
                print(f"★ 없는 노드: {x}")
                bad += 1
        rel.setdefault(a, []).append((b, why))
        rel.setdefault(b, []).append((a, why))
    if bad:
        return 1

    titles = {}
    for p in DEC.glob("*.md"):
        m = re.search(r"^title:\s*(.+)$", p.read_text(encoding="utf-8"), re.M)
        titles[p.stem] = m.group(1).strip() if m else p.stem

    for slug, links in rel.items():
        p = DEC / f"{slug}.md"
        text = p.read_text(encoding="utf-8")
        # 다시 돌려도 되게 옛 블록을 먼저 걷어낸다.
        # ⚠️ **`\Z` 를 빼면 안 된다.** 꼬리말 구분선이 없는 노드는 블록 뒤에
        #    `\n---\n` 이 없어 걷어내기가 실패하고, 아래에서 끝에 새로 붙이므로
        #    **돌릴 때마다 한 벌씩 쌓인다**(2026-08-05 에 16개 노드가 2~3벌이 됐다).
        #    생성물이라 오류도 안 나고 다음 생성 때 사라지지도 않는다.
        text = re.sub(rf"\n{BLOCK}\n.*?(?=\n---\n|\Z)", "", text, flags=re.S)

        lines = [f"\n{BLOCK}\n"]
        for other, why in sorted(links):
            lines.append(f"- [[{other}|{titles[other]}]]\n  — {why}\n")
        block = "".join(lines)
        # 꼬리말(--- 구분선) 앞에 넣는다.
        # ⚠️ **frontmatter 를 닫는 `---` 를 잡으면 안 된다.** 꼬리말 구분선이
        #    없는 노드에서 rfind 가 frontmatter 의 닫는 줄을 찾아, 블록이
        #    frontmatter **안으로** 들어가 YAML 이 깨진다(2026-08-04 에 9개 노드가
        #    그렇게 깨졌다). frontmatter 가 끝나는 지점부터 찾는다.
        fm_end = text.find("\n---\n", 3) if text.startswith("---\n") else -1
        start = fm_end + 5 if fm_end >= 0 else 0
        idx = text.rfind("\n---\n", start)
        if idx < 0:
            # 꼬리말 구분선이 없는 노드 — 끝에 붙인다
            text = text.rstrip("\n") + "\n" + block
        else:
            text = text[:idx] + block + text[idx:]
        p.write_text(text, encoding="utf-8")

    isolated = sorted(nodes - set(rel))
    print(f"짝 {len(PAIRS)}개 → 노드 {len(rel)}개에 '이어지는 결정' 추가")
    print(f"평균 {sum(len(v) for v in rel.values())/len(rel):.1f}개씩")
    print("아직 안 이어진 노드:", isolated or "없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
