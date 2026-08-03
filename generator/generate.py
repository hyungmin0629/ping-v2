"""
합성 데이터 생성기

생성 순서에 제약이 있다:
  1. 조직(지역·학교·학급)  → 유저를 배치할 곳이 먼저 있어야 한다
  2. 유저                   → 친구를 맺을 대상이 있어야 한다
  3. 친구 그래프            → GLOBAL 스코프가 "친구 전체"이므로 후보 풀의 토대
  4. 질문                   → 출제할 것이 있어야 한다
  5. 투표(후보는 친구에서)  → 3번이 없으면 후보를 못 뽑는다
  6. 하트 원장              → 투표·힌트가 확정된 뒤에야 잔액을 순서대로 계산할 수 있다

특히 6번이 까다롭다. heart_transaction.balance_after 는 유저별로
시간순으로 누적해야 하고, balance_after >= 0 CHECK 제약이 걸려 있어서
잔액이 모자라면 힌트를 살 수 없다. 그래서 유저별 타임라인을 만들어
연대순으로 걸으면서 잔액을 시뮬레이션한다.

사용법:
    python generator/generate.py
    python generator/generate.py --users 1000 --months 1   # 작게 테스트
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "generator" / "config"
CONFIG_PATH = CONFIG_DIR / "distribution.yaml"
OUT_DIR = ROOT / "data" / "synthetic"

KST = timezone(timedelta(hours=9))

SIDO = [
    ("서울특별시", ["강남구", "송파구", "노원구", "은평구", "관악구", "마포구"]),
    ("부산광역시", ["해운대구", "부산진구", "사하구", "북구"]),
    ("인천광역시", ["서구", "남동구", "부평구"]),
    ("대구광역시", ["수성구", "달서구", "북구"]),
    ("경기도", ["수원시", "성남시", "고양시", "용인시", "화성시", "남양주시", "광명시", "광주시"]),
    ("충청남도", ["천안시", "아산시", "서산시"]),
    ("전라남도", ["여수시", "순천시", "고흥군", "화순군"]),
    ("경상북도", ["상주시", "안동시", "구미시"]),
    ("경상남도", ["거제시", "거창군", "사천시"]),
    ("강원특별자치도", ["춘천시", "원주시", "강릉시"]),
]

SURNAMES = "김이박최정강조윤장임한오서신권황안송류전홍고문양손배백허유남심노하곽성차주우구"
GIVEN = [
    "민준", "서연", "지호", "하윤", "예준", "지우", "주원", "서윤", "지훈", "채원",
    "건우", "수아", "현우", "하은", "도윤", "지아", "시우", "유진", "준서", "다은",
    "은우", "소율", "정우", "예은", "승현", "가은", "연우", "지윤", "시윤", "나윤",
]

# 닉네임 — 실명이 아니라 유저가 직접 정하는 별명이다.
# 개인정보를 받지 않으므로 이름 마스킹이 아니라 자유 별명이 맞다.
NICK_ADJ = [
    "졸린", "배고픈", "심심한", "행복한", "느긋한", "바쁜", "조용한", "신난",
    "귀찮은", "설레는", "포근한", "엉뚱한", "재빠른", "다정한", "웃긴", "차분한",
    "용감한", "수줍은", "엉큼한", "부지런한", "나른한", "상냥한",
]
NICK_NOUN = [
    "감자", "고양이", "너구리", "펭귄", "수달", "토끼", "곰돌이", "다람쥐",
    "붕어빵", "김밥", "떡볶이", "마카롱", "복숭아", "딸기", "포도", "귤",
    "구름", "바람", "별빛", "달빛", "파도", "노을",
]

# 헷갈리는 글자(0/O, 1/I/L) 제외 — DDL 의 ck_invite_code 와 맞춰야 한다
CODE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

SUBJECTS = ["국어", "수학", "영어", "과학", "사회", "역사", "체육", "음악", "미술", "정보", "도덕", "기술가정"]

# NEIS 교육청 코드. 실제로 쓰이는 값이라 형식을 맞춘다.
NEIS_OFFICE_CODES = ["B10", "C10", "D10", "E10", "F10", "G10", "H10", "I10",
                     "J10", "K10", "M10", "N10", "P10", "R10", "S10", "T10"]

# 급식 — 끼니 하나가 여러 요리로 쪼개진다. "인기 메뉴" 분석이 가능해지는 구조.
DISHES = {
    "밥": ["쌀밥", "잡곡밥", "흑미밥", "볶음밥", "비빔밥", "카레라이스", "김치볶음밥"],
    "국": ["미역국", "된장국", "김치찌개", "부대찌개", "콩나물국", "떡국", "육개장", "순두부찌개"],
    "주찬": ["제육볶음", "돈까스", "닭갈비", "고등어구이", "불고기", "탕수육", "치킨텐더",
             "함박스테이크", "오징어볶음", "달걀말이"],
    "부찬": ["시금치나물", "감자조림", "어묵볶음", "콩자반", "멸치볶음", "브로콜리무침",
             "마카로니샐러드", "잡채"],
    "김치": ["배추김치", "깍두기", "총각김치"],
    "후식": ["요구르트", "사과", "바나나", "귤", "식혜", "푸딩", "초코우유"],
}
ALLERGY_CODES = ["1.난류", "2.우유", "5.대두", "6.밀", "9.새우", "13.호두", "16.닭고기", "18.돼지고기"]

EVENT_TITLES = {
    "HOLIDAY":    ["여름방학", "겨울방학", "개교기념일", "재량휴업일", "봄방학"],
    "EXAM":       ["1학기 중간고사", "1학기 기말고사", "2학기 중간고사", "2학기 기말고사", "모의고사"],
    "CEREMONY":   ["입학식", "졸업식", "체육대회", "학교축제", "개학식", "종업식"],
    "FIELD_TRIP": ["수학여행", "현장체험학습", "진로체험의 날", "봉사활동"],
    "ETC":        ["학부모 상담주간", "동아리 발표회", "안전교육", "정기 대청소"],
}

NOTICE_TITLES = [
    "급식 메뉴 변경 안내", "동절기 등교시간 조정", "교내 분실물 보관 안내",
    "방과후학교 신청 안내", "학생증 재발급 절차", "교복 공동구매 안내",
    "도서관 이용시간 변경", "체육관 보수공사 안내", "학교폭력 예방교육 실시",
    "예방접종 확인서 제출", "졸업앨범 촬영 일정", "겨울방학 특강 모집",
]

# 게시판 — 학교 게시판에 실제로 올라올 법한 제목·본문 조각
POST_TITLES = [
    "오늘 급식 어땠어?", "시험 얼마 안 남았다", "체육대회 종목 뭐가 좋을까",
    "야자 하는 사람 있어?", "이번 축제 기대된다", "수학 진도 너무 빠르지 않아?",
    "매점에 새로 들어온 거 봤어?", "동아리 추천 좀", "다들 몇시에 자?",
    "선생님 진짜 좋으신 듯", "버스 너무 막힌다", "교복 하복 언제부터야",
    "수행평가 망했다", "방학 계획 있어?", "급식실 줄 너무 길어",
]
POST_BODIES = [
    "다들 어떻게 생각하는지 궁금해서 올려봐.", "나만 그런가 싶어서 물어봐.",
    "진심으로 조언 구합니다.", "그냥 답답해서 써봤어. 읽어줘서 고마워.",
    "혹시 아는 사람 있으면 알려줘.", "요즘 계속 이 생각만 든다.",
    "별거 아닌데 얘기하고 싶었어.", "어제부터 계속 고민중이야.",
]
COMMENT_BODIES = [
    "나도 그래", "ㅋㅋㅋㅋ 인정", "헐 진짜?", "나는 좀 다르게 생각해",
    "공감된다", "그거 나도 궁금했어", "화이팅", "고마워 도움됐어",
    "음... 잘 모르겠다", "맞말이다", "나만 그런 게 아니었네", "다음에 같이 하자",
]
# =====================================================================
# 페르소나 — **분류가 아니라 생성 편의다**
# =====================================================================
# 유저를 6종으로 나누는 것이 목적이 아니다. 목적은 행동 트레잇들이
# **서로 묶여서** 움직이게 하는 것이다. 지금까지는 글쓰기와 투표가 독립이라
# "글도 쓰고 투표도 많이 하는 사람"이 우연으로만 생겼다.
#
# ⚠️ 결과 데이터에 6덩어리가 또렷하게 남으면 실패다. 분석자가 클러스터링해서
#    우리가 넣은 6개를 그대로 되찾는 데이터는 발견할 것이 없다.
#    그래서 배정을 세 가지로 흐린다 — 혼합·트레잇 교차·무배정(_make_traits).
#
# 배수는 **상대값**이다. 절대 확률이 아니라 "모집단 평균의 몇 배인가"이고,
# 유저를 다 만든 뒤 실측 평균으로 나눠 정규화한다(_normalize_traits).
# 그래야 지금까지 맞춰 둔 read_rate·author_ratio 같은 값이 안 깨진다.

TRAITS = ("vote_freq", "read", "hint", "reply", "friends",
          "post", "comment", "pay", "reported", "retain")

PERSONAS: dict[str, tuple[float, dict[str, float]]] = {
    "관망형":   (0.30, dict(vote_freq=0.4, read=1.2, hint=0.5, reply=0.4, friends=0.7,
                            post=0.3, comment=0.4, pay=0.4, reported=0.6, retain=0.5)),
    "투표형":   (0.28, dict(vote_freq=1.5, read=1.0, hint=1.1, reply=0.8, friends=0.9,
                            post=0.4, comment=0.6, pay=1.0, reported=0.8, retain=1.3)),
    "소셜형":   (0.15, dict(vote_freq=0.9, read=1.0, hint=0.9, reply=1.5, friends=2.0,
                            post=0.8, comment=1.0, pay=0.8, reported=1.0, retain=1.3)),
    "게시판형": (0.12, dict(vote_freq=0.6, read=0.9, hint=0.7, reply=1.0, friends=0.9,
                            post=2.6, comment=2.2, pay=0.7, reported=1.2, retain=1.2)),
    "고관여형": (0.12, dict(vote_freq=2.2, read=1.3, hint=1.9, reply=1.8, friends=1.5,
                            post=1.8, comment=1.7, pay=2.6, reported=1.0, retain=2.6)),
    "악성형":   (0.03, dict(vote_freq=1.2, read=0.8, hint=1.3, reply=1.4, friends=0.7,
                            post=1.4, comment=1.3, pay=0.9, reported=8.0, retain=0.9)),
}

# 배정을 흐리는 세 장치
MIX_RATIO = 0.25        # 두 유형을 6:4 로 섞는다
CROSS_RATIO = 0.08      # 트레잇 하나를 다른 유형에서 통째로 가져온다
FREE_RATIO = 0.04       # 유형 없이 전 트레잇 독립 무작위
# 개인 편차. **트레잇마다 따로** 흔든다.
# ⚠️ vote_freq 와 retain 은 σ 를 크게 준다. 세션 수가 이 둘의 **곱**이라
#    편차가 작으면 유형 간 차이가 63배까지 벌어져 "관망형인데 자주 오는 사람"이
#    한 명도 안 나온다(실제로 그랬다).
TRAIT_SIGMA = 0.55
TRAIT_SIGMA_BY = {"vote_freq": 0.90, "retain": 0.80}


def scaled_prob(p: float, m: float) -> float:
    """
    확률에 배수를 건다. 그냥 곱하면 1을 넘으므로 오즈비로 건다.
    p=0.55, m=2 → 0.71 (1.10 이 아니다)
    """
    if p <= 0:
        return 0.0
    if p >= 1:
        return 1.0
    o = p / (1 - p) * m
    return o / (1 + o)


REPLY_TEXTS = [
    "고마워 :)", "누군지 알 것 같은데?", "헐 진심 고마워", "나도 너 뽑았어",
    "부끄럽다 진짜", "덕분에 기분 좋아졌어", "누구야 대체 ㅋㅋ", "잘 지내지?",
    "이런 거 처음 받아봐", "고맙다 진짜로", "궁금해 죽겠네", "오늘 하루 행복했어",
]

# 원장에 남는 메모. 앱이 남기는 문구와 맞춘다(db/rls/replies.sql).
TX_MEMOS = {
    "VOTE_REPLY": "받은 투표에 답장",
    "ADMIN_ADJUST": "운영자 보정 지급",
    "EVENT_GRANT": "이벤트 지급",
}

REPORT_DETAILS = [
    "계속 비슷한 글을 올려요", "보기 불편합니다", "특정인을 지목하는 것 같아요",
    "광고성 내용입니다", "욕설이 포함돼 있어요", "사실이 아닌 내용입니다", "",
]

QUESTION_TEMPLATES = {
    "PERSONALITY": [
        "가장 잘 웃는 사람은?", "화를 제일 안 낼 것 같은 사람은?", "고민을 털어놓고 싶은 사람은?",
        "제일 차분한 사람은?", "생각이 깊어 보이는 사람은?", "먼저 다가와 줄 것 같은 사람은?",
        "낯을 제일 안 가릴 것 같은 사람은?", "은근히 고집 있어 보이는 사람은?",
    ],
    "RELATIONSHIP": [
        "처음 보는 사람과 가장 빨리 친해질 것 같은 사람은?", "모든 사람과 잘 지낼 것 같은 사람은?",
        "싸워도 먼저 화해할 것 같은 사람은?", "비밀을 가장 잘 지켜줄 사람은?",
        "10년 뒤에도 연락하고 있을 것 같은 사람은?", "내가 힘들 때 제일 먼저 연락할 사람은?",
    ],
    "TALENT": [
        "숨겨진 댄싱 머신이라고 생각하는 사람은?", "노래를 제일 잘할 것 같은 사람은?",
        "그림을 잘 그릴 것 같은 사람은?", "운동 신경이 좋을 것 같은 사람은?",
        "손재주가 좋을 것 같은 사람은?", "요리를 잘할 것 같은 사람은?",
    ],
    "HUMOR": [
        "같이 있으면 제일 웃긴 사람은?", "예능에 나가면 잘할 것 같은 사람은?",
        "드립력이 제일 좋은 사람은?", "표정이 제일 다양한 사람은?", "몰래카메라에 잘 속을 것 같은 사람은?",
    ],
    "SCHOOL_LIFE": [
        "지각을 제일 안 할 것 같은 사람은?", "수업 시간에 제일 집중하는 사람은?",
        "급식을 제일 맛있게 먹는 사람은?", "축제에서 공연을 제일 잘할 것 같은 사람은?",
        "학생회장을 할 것 같은 사람은?", "필기를 제일 잘할 것 같은 사람은?",
        "쉬는 시간에 제일 바빠 보이는 사람은?",
    ],
    "FUTURE": [
        "앞으로의 인생을 가장 재미있게 살 것 같은 사람은?", "나중에 크게 성공할 것 같은 사람은?",
        "해외에서 살고 있을 것 같은 사람은?", "자기 사업을 할 것 같은 사람은?",
        "제일 먼저 결혼할 것 같은 사람은?", "유명해질 것 같은 사람은?",
    ],
    "TASTE": [
        "음악 취향이 제일 좋을 것 같은 사람은?", "영화를 제일 많이 봤을 것 같은 사람은?",
        "반려동물과 가장 잘 지낼 것 같은 사람은?", "여행을 제일 좋아할 것 같은 사람은?",
        "카페 투어를 즐길 것 같은 사람은?",
    ],
    # ⚠️ 민감 카테고리(is_sensitive = true). 2026-08-03 에 켰다 —
    #    **신고율을 재기 위해서다.** 민감 질문이 하나도 없으면 is_sensitive
    #    플래그가 아무것도 구분하지 못하고 신고 파이프라인도 검증되지 않는다.
    #    비하로 읽힐 문장은 넣지 않는다. 칭찬 방향의 외모·스타일 질문만 쓴다.
    "APPEARANCE": [
        "스타일이 제일 좋은 사람은?", "패션 감각이 뛰어난 사람은?",
        "웃는 모습이 제일 예쁜 사람은?", "분위기가 제일 좋은 사람은?",
        "헤어스타일이 제일 잘 어울리는 사람은?", "목소리가 제일 좋은 사람은?",
        "교복이 제일 잘 어울리는 사람은?", "첫인상이 제일 좋았던 사람은?",
    ],
}

WITHDRAW_TEXTS = [
    "쓸 일이 없어졌어요", "친구들이 안 해서요", "질문이 반복돼서 재미없어요",
    "알림이 너무 자주 와요", "생각보다 할 게 없네요", "다른 앱 쓰고 있어요",
]


# =====================================================================
# 유틸
# =====================================================================

def load_config(path: Path) -> dict:
    """
    설정을 읽는다. 두 가지 형식을 받는다.

    - distribution.yaml (v1)  — 키를 그대로 쓴다
    - synthetic-v2.yaml (v2)  — `meta` 키가 있으면 v2 로 보고 내부 형식으로 옮긴다

    v2 는 **distribution.yaml 을 바탕에 깔고 덮어쓴다.** v2 에 없는 항목
    (answer_public_rate 등)이 생성기에서 그대로 쓰이기 때문이다. 바탕이 없으면
    KeyError 가 나는데, 그건 "설정에 없다"가 아니라 "옮기는 표를 안 썼다"는 뜻이라
    조용히 기본값으로 때우면 안 된다.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if "meta" not in raw:
        return raw

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    v2 = raw

    cfg["seed"] = v2["meta"]["seed"]
    cfg["months"] = v2["period"]["months"]
    cfg["start_date"] = v2["period"]["start_date"]
    cfg["end_date"] = v2["period"]["end_date"]

    cfg["users"]["count"] = v2["scale"]["users"]
    # 학교는 **활성 학교 수**를 쓴다. 마스터 5,724개에 유저를 뿌리면 학급당
    # 1명이 되어 친구 그래프가 성립하지 않는다(설정 파일의 경고와 같은 이유).
    cfg["schools"]["count"] = v2["schools"]["active_count"]
    for k in ("middle_ratio", "classes_per_school", "students_per_class"):
        if k in v2["schools"]:
            cfg["schools"][k] = v2["schools"][k]

    # 첫 국면의 가입 비중이 옛 signup_spike_ratio 자리를 대신한다
    phases = v2.get("growth", {}).get("phases") or []
    if phases:
        cfg["users"]["signup_spike_ratio"] = phases[0]["signup_share"]

    u = v2.get("users", {})
    cfg["users"]["gender_ratio_f"] = u.get("gender_ratio_f", cfg["users"]["gender_ratio_f"])
    cfg["withdrawal"]["rate"] = u.get("withdrawal_rate", cfg["withdrawal"]["rate"])
    cfg["withdrawal"]["free_text_rate"] = u.get("withdrawal_free_text_rate",
                                                cfg["withdrawal"]["free_text_rate"])
    if "withdrawal_reason_weights" in u:
        cfg["withdrawal"]["reason_weights"] = u["withdrawal_reason_weights"]

    # v1 에 있던 절(節)은 덮어쓰고, v2 에서 새로 생긴 절은 통째로 옮긴다.
    # ⚠️ 새 절을 여기 안 적으면 그 생성기가 조용히 아무것도 안 만든다 —
    #    에러가 안 나서 표가 비어 있는 것으로만 드러난다. 실제로 한 번 겪었다.
    for section in ("retention", "friends", "sessions", "questions", "voting",
                    "received", "hearts", "board", "moderation", "school_info",
                    "text", "anomalies", "growth", "incremental_batch", "gates"):
        if section in v2:
            cfg.setdefault(section, {}).update(v2[section])

    cfg["_v2"] = v2
    return cfg


def make_nickname(rng: random.Random, taken: set[str]) -> str:
    """유저가 정하는 별명. 실명·마스킹이 아니다."""
    for _ in range(60):
        nick = f"{rng.choice(NICK_ADJ)}{rng.choice(NICK_NOUN)}"
        if nick not in taken:
            taken.add(nick)
            return nick
    # 조합이 소진되면 뒤에 숫자를 붙인다 (실제 서비스의 중복 처리와 같은 방식)
    while True:
        nick = f"{rng.choice(NICK_ADJ)}{rng.choice(NICK_NOUN)}{rng.randint(2, 999)}"
        if nick not in taken:
            taken.add(nick)
            return nick


def make_invite_code(rng: random.Random, taken: set[str]) -> str:
    """친구 추가의 유일한 수단. 전역 유일해야 한다."""
    while True:
        code = "".join(rng.choice(CODE_CHARS) for _ in range(6))
        if code not in taken:
            taken.add(code)
            return code


def masked_name(rng: random.Random) -> str:
    """
    실명 계열 마스킹. 김민수 → 김*수

    유저에게는 쓰지 않는다(유저는 nickname). 시간표의 교사명처럼
    실명을 다뤄야 하는 곳에서만 쓴다. 해당 데이터는 NEIS 연동(P3)에서 생성되므로
    현재는 호출되는 곳이 없다.
    """
    sur = rng.choice(SURNAMES)
    given = rng.choice(GIVEN)
    if len(given) <= 1:
        return f"{sur}*"
    return f"{sur}*{given[-1]}"


def masked_school(rng: random.Random, sigungu: str, is_middle: bool, n: int) -> str:
    base = sigungu.rstrip("시군구") or sigungu
    kind = "중학교" if is_middle else "고등학교"
    name = f"{base}{n}{kind}"
    return name[0] + "*" + name[2:]


def weighted_choice(rng: random.Random, mapping: dict) -> str:
    keys = list(mapping.keys())
    weights = [mapping[k] for k in keys]
    return rng.choices(keys, weights=weights, k=1)[0]


def rand_dt(rng: random.Random, start: datetime, end: datetime) -> datetime:
    if end <= start:
        return start
    delta = int((end - start).total_seconds())
    return start + timedelta(seconds=rng.randint(0, delta))


def iso(dt: datetime | None) -> str:
    return dt.isoformat() if dt else ""


class Writer:
    """CSV 출력. 테이블별로 파일 하나."""

    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._files: dict[str, object] = {}
        self._writers: dict[str, csv.writer] = {}
        self.counts: dict[str, int] = {}

    def write(self, table: str, header: list[str], row: list):
        if table not in self._writers:
            f = open(self.out_dir / f"{table}.csv", "w", newline="", encoding="utf-8")
            self._files[table] = f
            w = csv.writer(f)
            w.writerow(header)
            self._writers[table] = w
            self.counts[table] = 0
        self._writers[table].writerow(row)
        self.counts[table] += 1

    def close(self):
        for f in self._files.values():
            f.close()


# =====================================================================
# 도메인 객체 (생성 중에만 메모리에 들고 있는 최소 정보)
# =====================================================================

@dataclass
class User:
    id: int
    class_id: int
    school_id: int
    created_at: datetime
    gender: str
    activity_days: int              # 가입 후 며칠간 활동하는가 (리텐션)
    is_power: bool
    no_activity: bool = False       # 앱을 한 번도 안 열었다 (당일만 쓴 유저와 다르다)
    tier: str = "no_activity"       # 잔존 구간. 활동 강도가 여기서 갈린다
    persona: str = ""               # 정답지용 라벨. **DB 에 넣지 않는다**
    traits: dict = field(default_factory=dict)   # 트레잇 배수 (모집단 평균 1.0)
    # 힌트를 사는 성향. 0 이면 아무리 많이 받아도 안 산다.
    # ⚠️ 이게 없으면 힌트 횟수가 **받은 투표 수만으로** 결정되어,
    #    "힌트를 잘 사는 사람"이라는 유형 자체가 데이터에 존재하지 않는다.
    hint_appetite: float = 0.0
    locked: bool = False            # 친구 5명 게이트를 못 넘는 유저
    is_hub: bool = False            # 친구가 아주 많은 유저
    fame: float = 1.0               # 학급 안에서의 인기도 가중치 (지목받을 확률)
    friends: set[int] = field(default_factory=set)
    unlocked_at: datetime | None = None
    # 하트 타임라인: (시각, 유형코드, 델타, 참조컬럼, 참조id)
    ledger: list[tuple] = field(default_factory=list)


# =====================================================================
# 생성기
# =====================================================================

class Generator:
    def __init__(self, cfg: dict, out_dir: Path):
        self.cfg = cfg
        self.rng = random.Random(cfg["seed"])
        self.w = Writer(out_dir)
        self.start = datetime.fromisoformat(cfg["start_date"]).replace(tzinfo=KST)
        self.end = self.start + timedelta(days=30 * cfg["months"])

        self.regions: list[tuple] = []
        self.schools: list[dict] = []
        self.classes: list[dict] = []
        self.users: list[User] = []
        self.by_class: dict[int, list[int]] = {}
        self.by_school: dict[int, list[int]] = {}
        self.questions: list[dict] = []
        self.categories: dict[str, int] = {}
        # 원장 계산이 끝나야 확정되는 행들 — 잔액이 모자라면 구매 자체가 성립하지 않으므로
        # 즉시 쓰지 않고 모아뒀다가 결과를 반영해서 쓴다
        self.pending_hints: dict[int, list] = {}      # hint_id -> row
        self.hint_to_recv: dict[int, int] = {}        # hint_id -> vote_received id
        self.pending_received: list[list] = []
        self.accepted_hints: set[int] = set()
        self.replied_receives: list[tuple] = []
        # 게시판·신고가 서로를 참조하므로 만든 것을 들고 있어야 한다
        self.posts: list[tuple] = []      # (id, school_id, author_id, created_at)
        self.comments: list[tuple] = []   # (id, post_id, author_id, created_at)
        self._calib: dict = {}          # (확률, 트레잇) -> 보정 계수
        self._reward_vals: list[int] | None = None
        self._reward_wts: list[float] = []

    # -- 1. 조직 ------------------------------------------------------
    def gen_org(self):
        rid = 0
        for sido, gus in SIDO:
            for gu in gus:
                rid += 1
                self.regions.append((rid, sido, gu))
                self.w.write("region", ["id", "sido", "sigungu", "created_at"],
                             [rid, sido, gu, iso(self.start)])

        sc = self.cfg["schools"]
        cls_id = 0
        for sid in range(1, sc["count"] + 1):
            region = self.rng.choice(self.regions)
            is_mid = self.rng.random() < sc["middle_ratio"]
            n_classes = self.rng.randint(*sc["classes_per_school"])
            school = {
                "id": sid,
                "region_id": region[0],
                "is_middle": is_mid,
                "name": masked_school(self.rng, region[2], is_mid, sid),
                "class_ids": [],
            }
            max_grade = 3
            for grade in range(1, max_grade + 1):
                for cnum in range(1, (n_classes // max_grade) + 1):
                    cls_id += 1
                    self.classes.append({"id": cls_id, "school_id": sid, "grade": grade,
                                         "class_num": cnum, "is_middle": is_mid})
                    school["class_ids"].append(cls_id)
                    # label 은 "N학년 M반"으로 조립되는 기본 표기를 **덮어쓸 때만** 채운다.
                    # 고교 2·3학년의 계열 표기가 실제로 그런 경우다. 나머지는 비운다.
                    label = ""
                    if not is_mid and grade >= 2 and self.rng.random() < 0.35:
                        label = f"{grade}-{cnum} {self.rng.choice(['인문', '자연'])}"
                    self.w.write("grade_class",
                                 ["id", "school_id", "grade", "class_num", "label", "created_at"],
                                 [cls_id, sid, grade, cnum, label, iso(self.start)])
            self.schools.append(school)

        # student_count 는 유저 배정 후 갱신되므로 일단 0으로 두고 마지막에 다시 쓴다
        # info_school_id: 급식·학사일정을 어느 학교 것으로 가져오는가. 보통 자기 자신을
        #   가리키지만, 조직(코드잇 DA 14기처럼)은 남의 학교 공개 데이터를 빌려 쓴다.
        for s in self.schools:
            borrows = self.rng.random() < 0.10 and len(self.schools) > 1
            info_id = s["id"]
            if borrows:
                info_id = self.rng.choice([x["id"] for x in self.schools if x["id"] != s["id"]])
            self.w.write("school",
                         ["id", "name_masked", "region_id", "school_type", "neis_school_code",
                          "neis_office_code", "info_school_id", "student_count",
                          "created_at", "updated_at"],
                         [s["id"], s["name"], s["region_id"],
                          "MIDDLE" if s["is_middle"] else "HIGH",
                          f"N{s['id']:06d}",
                          self.rng.choice(NEIS_OFFICE_CODES), info_id,
                          0, iso(self.start), iso(self.start)])

    # -- 2. 유저 ------------------------------------------------------
    def gen_users(self):
        uc = self.cfg["users"]
        ret = self.cfg["retention"]
        spike_end = self.start + timedelta(days=14)

        # 리텐션 구간을 미리 뽑아둔다. 구간 이름을 유저에 남겨야 한다 —
        # 활동 강도가 구간마다 다르기 때문이다(gen_votes 에서 쓴다).
        buckets = [
            ("no_activity", ret["no_activity"], (0, 0)),
            ("same_day_only", ret["same_day_only"], (0, 0)),
            ("within_week", ret["within_week"], (1, 6)),
            ("within_month", ret["within_month"], (7, 29)),
            ("long_term", ret["long_term"], (30, 30 * self.cfg["months"])),
        ]

        # 학교를 하나씩 골라 학급 정원을 채우는 방식으로 배정한다.
        # 균등 분산하면 학급당 1명꼴이 되어 친구 그래프가 성립하지 않는다.
        sc = self.cfg["schools"]
        lo_cap, hi_cap = sc["students_per_class"]
        seats: list[int] = []
        school_order = list(self.schools)
        self.rng.shuffle(school_order)
        for s in school_order:
            if len(seats) >= uc["count"]:
                break
            for cid in s["class_ids"]:
                seats.extend([cid] * self.rng.randint(lo_cap, hi_cap))
        if len(seats) < uc["count"]:
            seats.extend(self.rng.choices(seats or [c["id"] for c in self.classes],
                                          k=uc["count"] - len(seats)))
        seats = seats[:uc["count"]]
        class_by_id = {c["id"]: c for c in self.classes}

        for uid in range(1, uc["count"] + 1):
            cls = class_by_id[seats[uid - 1]]
            if self.rng.random() < uc["signup_spike_ratio"]:
                created = rand_dt(self.rng, self.start, spike_end)
            else:
                created = rand_dt(self.rng, spike_end, self.end - timedelta(days=1))

            label, traits = self._make_traits()
            u = User(
                id=uid,
                class_id=cls["id"],
                school_id=cls["school_id"],
                created_at=created,
                gender="F" if self.rng.random() < uc["gender_ratio_f"] else "M",
                activity_days=0,
                persona=label,
                traits=traits,
                is_power=self.rng.random() < self.cfg["voting"]["power_user_ratio"],
            )
            self.users.append(u)
            self.by_class.setdefault(cls["id"], []).append(uid)
            self.by_school.setdefault(cls["school_id"], []).append(uid)

        self._normalize_traits()

        # 잔존 구간은 **순위로** 배정한다. retain 트레잇이 높은 사람이 오래 남되,
        # 구간별 인원은 실측 비율(4.1/28.4/35.5/27.8/4.2)과 정확히 같다.
        # 확률로 뽑으면 실측 분포가 조용히 틀어진다.
        order = sorted(self.users, key=lambda x: x.traits["retain"])
        n = len(order)
        cut = 0
        for name, weight, span in buckets:
            take = round(weight * n) if name != "long_term" else n - cut
            for u in order[cut:cut + take]:
                u.tier = name
                u.activity_days = self.rng.randint(*span) if span[1] > 0 else 0
                # ⚠️ no_activity 와 same_day_only 는 둘 다 days=0 이지만 **다른 상태**다.
                #    앞은 앱을 한 번도 안 열었고, 뒤는 가입 당일 하루를 썼다.
                u.no_activity = name == "no_activity"
                u.hint_appetite = self._hint_appetite(u)
            cut += take

    # -- 3. 친구 그래프 -----------------------------------------------
    def gen_friends(self):
        fc = self.cfg["friends"]
        lo, hi = fc["per_user"]
        med = fc["per_user_median"]
        edges: set[tuple[int, int]] = set()

        # 누가 고립되고 누가 허브인지 **먼저** 정한다.
        # ⚠️ 친구 관계는 양방향이다. 고립 유저의 목표치만 낮추면 남들이 그를 골라
        #    친구가 계속 붙어서 고립이 사라진다(실제로 그래서 해금률이 100%가 됐다).
        #    그래서 고립 유저는 **남의 후보 풀에서도 빼야** 한다.
        hub_lo, hub_hi = fc.get("hub_per_user", [150, 600])
        targets: dict[int, int] = {}
        for u in self.users:
            if self.rng.random() < fc["locked_user_ratio"]:
                u.locked = True
                targets[u.id] = self.rng.randint(0, 4)
            elif self.rng.random() < fc.get("hub_ratio", 0.0):
                u.is_hub = True
                targets[u.id] = self.rng.randint(hub_lo, hub_hi)
            else:
                targets[u.id] = max(0, int(self.rng.triangular(lo, hi, med)
                                           * u.traits["friends"]))

        # 남이 친구로 걸 수 있는 사람 = 고립으로 정해지지 않은 사람
        open_by_class = {k: [i for i in v if not self.users[i - 1].locked]
                         for k, v in self.by_class.items()}
        open_by_school = {k: [i for i in v if not self.users[i - 1].locked]
                          for k, v in self.by_school.items()}
        open_all = [u.id for u in self.users if not u.locked]

        for u in self.users:
            need = targets[u.id] - len(u.friends)
            attempts = 0
            while need > 0 and attempts < need * 12 + 40:
                attempts += 1
                r = self.rng.random()
                if u.is_hub:
                    # 허브는 한 학교 정원(수백 명)을 넘어야 하므로 학교 밖까지 뻗는다.
                    # 같은 반 비율을 그대로 적용하면 반 정원에 막혀 목표치에 못 닿는다.
                    pool = open_by_school.get(u.school_id, []) if r < 0.45 else open_all
                elif r < fc["same_class_ratio"]:
                    pool = open_by_class.get(u.class_id, [])
                elif r < fc["same_school_ratio"]:
                    pool = open_by_school.get(u.school_id, [])
                else:
                    pool = open_all
                # 고립 유저 본인은 자기 목표치까지는 아무나 고를 수 있다
                if u.locked:
                    pool = pool or open_all
                if not pool:
                    break
                cand = self.rng.choice(pool)
                if cand == u.id or cand in u.friends:
                    continue
                other = self.users[cand - 1]
                # 상대가 고립으로 정해졌으면 그 사람의 목표치를 넘겨선 안 된다
                if other.locked and len(other.friends) >= targets[other.id]:
                    continue
                key = (min(u.id, cand), max(u.id, cand))
                if key in edges:
                    continue
                edges.add(key)
                u.friends.add(cand)
                other.friends.add(u.id)
                need -= 1

        # 친구 요청 + 성사된 관계
        fr_id = 0
        fs_id = 0
        for lo_id, hi_id in sorted(edges):
            a, b = self.users[lo_id - 1], self.users[hi_id - 1]
            base = max(a.created_at, b.created_at)
            created = rand_dt(self.rng, base, min(base + timedelta(days=10), self.end))
            # MVP에서 친구 추가는 초대 코드가 주된 경로다.
            # CONTACT_SYNC 는 전화번호를 받아야 하므로 쓰지 않는다.
            source = self.rng.choices(["INVITE_CODE", "RECOMMEND", "SEARCH"], [0.7, 0.2, 0.1])[0]
            sender, receiver = (lo_id, hi_id) if self.rng.random() < 0.5 else (hi_id, lo_id)

            fr_id += 1
            responded = created + timedelta(minutes=self.rng.randint(1, 60 * 48))
            self.w.write("friend_request",
                         ["id", "sender_id", "receiver_id", "status", "source", "created_at", "responded_at"],
                         [fr_id, sender, receiver, "ACCEPTED", source, iso(created), iso(responded)])
            fs_id += 1
            # 친구를 끊어도 행을 지우지 않고 ended_at 을 찍는다(W19).
            # 지우면 관계 이탈 신호가 분석에서 사라진다.
            ended = ""
            if self.rng.random() < fc.get("unfriend_rate", 0.0):
                gap = (self.end - responded).days
                if gap > 1:
                    ended = iso(responded + timedelta(days=self.rng.randint(1, gap)))
                    a.friends.discard(b.id)
                    b.friends.discard(a.id)
            self.w.write("friendship",
                         ["id", "user_low_id", "user_high_id", "source", "created_at", "ended_at"],
                         [fs_id, lo_id, hi_id, source, iso(responded), ended])

        # 성사되지 않은 요청(대기·거절)도 만들어 상태 분포를 맞춘다
        acc_rate = fc["request_accept_rate"]
        extra = int(fs_id * (1 - acc_rate) / max(acc_rate, 1e-9))
        pend_share = fc["request_pending_rate"] / max(fc["request_pending_rate"] + fc["request_reject_rate"], 1e-9)
        made = 0
        guard = 0
        seen: set[tuple[int, int]] = set(edges)
        while made < extra and guard < extra * 20:
            guard += 1
            s = self.rng.randint(1, len(self.users))
            r_ = self.rng.randint(1, len(self.users))
            if s == r_:
                continue
            key = (min(s, r_), max(s, r_))
            if key in seen:
                continue
            seen.add(key)
            a, b = self.users[s - 1], self.users[r_ - 1]
            base = max(a.created_at, b.created_at)
            if base >= self.end:
                continue
            created = rand_dt(self.rng, base, self.end)
            is_pending = self.rng.random() < pend_share
            fr_id += 1
            made += 1
            self.w.write("friend_request",
                         ["id", "sender_id", "receiver_id", "status", "source", "created_at", "responded_at"],
                         [fr_id, s, r_, "PENDING" if is_pending else "REJECTED",
                          self.rng.choice(["INVITE_CODE", "RECOMMEND"]), iso(created),
                          "" if is_pending else iso(created + timedelta(hours=self.rng.randint(1, 72)))])

        # 친구 수 확정 + 게이트 해금 시점
        for u in self.users:
            if len(u.friends) >= 5:
                u.unlocked_at = u.created_at + timedelta(hours=self.rng.randint(1, 72))

    # -- 4. 질문 ------------------------------------------------------
    def gen_questions(self):
        qc = self.cfg["questions"]

        # 운영자 — 질문 검수·신고 처리의 주체.
        # 원래는 admin_user 테이블에서 뽑았다(migration 009 에서 없앰).
        # 이제 유저 중 일부에 표시한다 — 운영자도 계정이 있어야 한다는 뜻이다.
        # 가장 먼저 가입한 다섯 명을 쓴다.
        self.admin_ids = [u.id for u in self.users[:5]]
        self.reviewer_ids = self.admin_ids[1:3]
        self.moderator_ids = self.admin_ids[3:5]
        # 90_seed_master.sql 이 넣는 카테고리 id 순서와 맞춘다.
        # APPEARANCE 는 여덟 번째다 — 시드에서도 마지막 줄이다.
        codes = ["PERSONALITY", "RELATIONSHIP", "TALENT", "HUMOR", "SCHOOL_LIFE", "FUTURE", "TASTE"]
        for i, code in enumerate(codes, start=1):
            self.categories[code] = i
        self.categories["APPEARANCE"] = len(codes) + 1

        # 민감 카테고리는 켤 때만 섞는다(012 에서 실서비스 카테고리를 열었다).
        # 비율만큼만 넣는다 — 전체에 고루 뿌리면 서비스 성격이 달라진다.
        pool = [(c, t) for c in codes for t in QUESTION_TEMPLATES[c]]
        if qc.get("include_appearance"):
            n_app = max(1, round(len(pool) * qc.get("appearance_ratio", 0.06)))
            app = QUESTION_TEMPLATES["APPEARANCE"]
            pool += [("APPEARANCE", app[i % len(app)]) for i in range(n_app)]
            codes = codes + ["APPEARANCE"]

        qid = 0
        self.rng.shuffle(pool)
        while qid < qc["count"]:
            for code, text in pool:
                if qid >= qc["count"]:
                    break
                qid += 1
                scope = weighted_choice(self.rng, qc["scope_ratio"])
                is_user = self.rng.random() < qc["user_submitted_ratio"]
                suffix = "" if qid <= len(pool) else f" ({qid // len(pool) + 1})"
                self.questions.append({"id": qid, "scope": scope})
                self.w.write("question",
                             ["id", "text", "scope", "category_id", "status", "source",
                              "report_count", "created_by_admin_id", "created_at"],
                             [qid, text + suffix, scope, self.categories[code], "ACTIVE",
                              "USER_SUBMITTED" if is_user else "OFFICIAL", 0,
                              # 공식 질문은 운영자가 넣는다. 유저 제안은 넣은 사람이 없다.
                              "" if is_user else self.rng.choice(self.admin_ids),
                              iso(self.start)])

        # 질문 요청(검수 이력)
        approved = [q for q in self.questions if self.rng.random() < 0.3]
        for i in range(1, qc["request_count"] + 1):
            u = self.rng.choice(self.users)
            created = rand_dt(self.rng, u.created_at, self.end)
            r = self.rng.random()
            if r < qc["request_approve_rate"] and approved:
                q = approved.pop()
                status, pub = "APPROVED", q["id"]
                reject = ""
            elif r < qc["request_approve_rate"] + 0.35:
                status, pub, reject = "REJECTED", "", "기존 질문과 유사함"
            else:
                status, pub, reject = "PENDING", "", ""
            reviewed = "" if status == "PENDING" else iso(created + timedelta(days=self.rng.randint(1, 5)))
            self.w.write("question_request",
                         ["id", "user_id", "text", "proposed_scope", "proposed_category_id",
                          "status", "reject_reason", "reviewed_by_admin_id", "reviewed_at",
                          "published_question_id", "created_at"],
                         [i, u.id, f"이런 질문 어때요 #{i}",
                          weighted_choice(self.rng, qc["scope_ratio"]),
                          self.rng.randint(1, 7), status, reject,
                          "" if status == "PENDING" else self.rng.choice(self.reviewer_ids),
                          reviewed, pub, iso(created)])

    def _make_traits(self) -> tuple[str, dict[str, float]]:
        """
        한 유저의 트레잇 배수를 만든다. 라벨은 정답지용이며 DB 에 넣지 않는다.

        세 가지로 배정을 흐린다 —
          혼합    두 유형을 6:4 로 섞어 경계를 없앤다
          교차    트레잇 하나를 다른 유형에서 가져온다
                  → **관망형인데 댓글만 게시판형인 사람**이 여기서 나온다
          무배정  유형 자체가 없는 사람
        그리고 마지막에 트레잇마다 **따로** 개인 편차를 곱한다. 한 배수로
        전부 흔들면 유형 내부 순서가 그대로라 클러스터가 살아남는다.
        """
        names = list(PERSONAS)
        shares = [PERSONAS[n][0] for n in names]
        r = self.rng.random()

        if r < FREE_RATIO:
            base = {t: self.rng.uniform(0.3, 2.2) for t in TRAITS}
            label = "무배정"
        else:
            p1 = self.rng.choices(names, shares)[0]
            if self.rng.random() < MIX_RATIO:
                p2 = self.rng.choices(names, shares)[0]
                w = 0.6
                base = {t: PERSONAS[p1][1][t] * w + PERSONAS[p2][1][t] * (1 - w)
                        for t in TRAITS}
                label = f"{p1}+{p2}" if p2 != p1 else p1
            else:
                base = dict(PERSONAS[p1][1])
                label = p1
            if self.rng.random() < CROSS_RATIO:
                t = self.rng.choice(TRAITS)
                other = self.rng.choices(names, shares)[0]
                base[t] = PERSONAS[other][1][t]
                label += f"/{t}←{other}"

        return label, {t: base[t] * self.rng.lognormvariate(
                              0, TRAIT_SIGMA_BY.get(t, TRAIT_SIGMA))
                       for t in TRAITS}

    def _normalize_traits(self):
        """
        트레잇의 **모집단 평균을 정확히 1.0 으로** 맞춘다.

        해석적으로 계산하지 않고 실측 평균으로 나눈다 — 개인 편차의 분포가
        무엇이든 정확히 보존되기 때문이다. 이걸 안 하면 read_rate·author_ratio
        처럼 힘들게 맞춰 둔 값들이 조용히 어긋난다(에러는 안 난다).
        """
        n = len(self.users)
        for t in TRAITS:
            m = sum(u.traits[t] for u in self.users) / n
            if m <= 0:
                continue
            for u in self.users:
                u.traits[t] /= m

    def pchance(self, p: float, u: User, trait: str) -> float:
        """
        확률 p 에 그 사람의 트레잇을 걸되, **모집단 평균은 정확히 p 로 유지**한다.

        ⚠️ 트레잇 평균이 1.0 이어도 오즈비 변환을 거치면 평균이 내려간다
           (변환이 볼록해서다). 실제로 열람률이 55.5% → 39.2% 로 샜다.
           설정값을 손으로 올려 맞추면 트레잇 분포가 바뀔 때마다 다시 틀어지므로,
           **보정 계수를 이분법으로 풀어** 캐시한다.
        """
        if p <= 0 or p >= 1:
            return p
        ckey = (round(p, 6), trait)
        k = self._calib.get(ckey)
        if k is None:
            ms = [x.traits[trait] for x in self.users]
            lo, hi = 1e-3, 1e3
            for _ in range(50):
                mid = (lo * hi) ** 0.5
                avg = sum(scaled_prob(p, mid * m) for m in ms) / len(ms)
                if avg < p:
                    lo = mid
                else:
                    hi = mid
            k = (lo * hi) ** 0.5
            self._calib[ckey] = k
        return scaled_prob(p, k * u.traits[trait])

    def _hint_appetite(self, u: User) -> float:
        """
        힌트를 사는 성향. **유저마다 다르다.**

        일부는 아무리 많이 받아도 안 산다 — 궁금하지 않거나 하트를 아낀다.
        나머지 안에서도 편차가 크고, 그 편차를 페르소나의 hint 트레잇이 민다.
        """
        rc = self.cfg["received"]
        buy = self.pchance(rc.get("hint_buyer_ratio", 1.0), u, "hint")
        if self.rng.random() >= buy:
            return 0.0
        lo, hi = rc.get("hint_appetite_range", [0.1, 0.9])
        # 낮은 쪽이 두텁다 — 가끔 사는 사람이 늘 사는 사람보다 많다
        base = lo + (hi - lo) * self.rng.random() ** 1.8
        return min(scaled_prob(base, u.traits["hint"]), 0.95)

    def _vote_reward(self) -> int:
        """
        투표 보상 하트. 확률표로 뽑는다.
        v1 실측(5~15 균등)을 그대로 쓰면 적립이 소비의 8배가 된다 —
        v1 은 힌트가 200~1,000하트였고 W14 에서 20하트로 내렸기 때문이다.
        """
        w = self.cfg["hearts"].get("vote_reward_weights")
        if not w:
            return self.rng.randint(*self.cfg["hearts"]["vote_reward"])
        if self._reward_vals is None:
            self._reward_vals = [int(k) for k in w]
            self._reward_wts = [float(w[k]) for k in w]
        return self.rng.choices(self._reward_vals, self._reward_wts)[0]

    # -- 5. 투표 ------------------------------------------------------
    def gen_votes(self):
        v = self.cfg["voting"]
        rc = self.cfg["received"]
        h = self.cfg["hearts"]

        by_scope: dict[str, list[dict]] = {"CLASS": [], "SCHOOL": [], "GLOBAL": []}
        for q in self.questions:
            by_scope[q["scope"]].append(q)

        sess_id = item_id = cand_id = ad_id = shuf_id = recv_id = hint_id = 0
        by_tier = v.get("sessions_per_month_by_tier") or {}

        # 인기도 — 학급 안에서 정해진다. 반의 스타가 전교에서 무명일 수 있게.
        # Zipf 꼴 가중치를 학급별로 매기고, 일부는 아예 0 으로 둔다.
        pop = v.get("popularity", {})
        if pop.get("enabled"):
            alpha = pop.get("zipf_alpha", 1.6)
            never = pop.get("never_picked_ratio", 0.0)
            for members in self.by_class.values():
                order = list(members)
                self.rng.shuffle(order)
                for rank, uid in enumerate(order, start=1):
                    self.users[uid - 1].fame = rank ** (-alpha)
            for u in self.users:
                if self.rng.random() < never:
                    u.fame = 0.0

        def pick(pool: list[int], k: int, recent: set[int]) -> list[int]:
            """
            후보 k명을 뽑는다. 최근 노출자는 되도록 뺀다.

            ⚠️ 여기에는 인기도를 걸지 않는다. 후보 선정과 당첨 양쪽에 걸면
               가중치가 제곱돼 상위 10%가 60%를 넘어간다(실제로 그랬다).
               **후보에 오르는 것은 공평하고, 뽑히는 것이 인기도로 갈린다.**
               이게 서비스 동작과도 맞다 — 후보는 친구 중에서 무작위로 나온다.
            """
            avail = [c for c in pool if c not in recent]
            if len(avail) < k:
                avail = list(pool)
            if len(avail) <= k:
                return list(avail)
            return self.rng.sample(avail, k)

        for u in self.users:
            if not u.unlocked_at or u.no_activity or len(u.friends) < 5:
                continue
            # 세션 수 = (그 구간의 월 빈도) × (활동 기간이 몇 달인가).
            # 기간에 비례해야 1개월 샘플이 12개월치를 담지 않는다(EDA 문제 ②).
            # 빈도 자체는 **잔존 구간마다 다르다** — 오래 남은 사람이 자주 온다.
            rng_t = by_tier.get(u.tier)
            if not rng_t or rng_t[1] <= 0:
                continue
            months = max(self.cfg["months"], 1)
            span_months = min((u.activity_days + 1) / 30.0, months)
            per_month = self.rng.uniform(*rng_t)
            n_sess = max(1, round(per_month * max(span_months, 1 / 30.0)
                                  * u.traits["vote_freq"]))
            if u.is_power:
                n_sess = int(n_sess * v["power_user_multiplier"])
            active_end = min(u.unlocked_at + timedelta(days=u.activity_days + 1), self.end)
            recent_seen: set[int] = set()

            friend_ids = list(u.friends)
            same_class = [f for f in friend_ids if self.users[f - 1].class_id == u.class_id]
            same_school = [f for f in friend_ids if self.users[f - 1].school_id == u.school_id]

            for _ in range(n_sess):
                started = rand_dt(self.rng, u.unlocked_at, active_end)
                sess_id += 1
                # 세션을 끝까지 안 채우고 나가는 사람이 있어야 퍼널이 성립한다.
                # 이탈은 앞쪽에 몰린다 — 3문항 안에서 나가는 게 대부분이다.
                n_items = v["items_per_session"]
                if self.rng.random() < scaled_prob(
                        v.get("session_abandon_rate", 0.0),
                        1.0 / max(u.traits["vote_freq"], 0.2)):
                    if self.rng.random() < v.get("abandon_early_share", 0.6):
                        n_items = self.rng.randint(1, 3)
                    else:
                        n_items = self.rng.randint(4, v["items_per_session"] - 1)
                completed = 0

                session_rows = []
                for pos in range(1, n_items + 1):
                    scope = self.rng.choices(["CLASS", "SCHOOL", "GLOBAL"], [0.35, 0.35, 0.30])[0]
                    pool = {"CLASS": same_class, "SCHOOL": same_school, "GLOBAL": friend_ids}[scope]
                    if len(pool) < 4:
                        pool = friend_ids
                        scope = "GLOBAL"
                    if len(pool) < 4 or not by_scope[scope]:
                        continue
                    q = self.rng.choice(by_scope[scope])
                    item_id += 1
                    served = started + timedelta(seconds=pos * self.rng.randint(8, 40))
                    if served > self.end:
                        break

                    did_shuffle = self.rng.random() < self.pchance(
                        v["shuffle_rate"], u, "hint")
                    rounds = [0, 1] if did_shuffle else [0]
                    chosen_uid = None
                    voted = self.rng.random() < v["complete_rate"]

                    for rnd in rounds:
                        picks = pick(pool, 4, recent_seen)
                        if len(picks) < 4:
                            picks = self.rng.sample(pool, 4)
                        recent_seen.update(picks)
                        if len(recent_seen) > 60:
                            recent_seen.clear()
                        # 뽑히는 사람도 인기도로 정해진다. 후보에 올라가는 것과
                        # 실제로 뽑히는 것 둘 다 가중돼야 멱법칙이 나온다.
                        winner = None
                        if voted and rnd == rounds[-1]:
                            fw = [max(self.users[c - 1].fame, 1e-9) for c in picks]
                            winner = self.rng.choices(picks, fw)[0]
                        for slot, cu in enumerate(picks, start=1):
                            cand_id += 1
                            is_chosen = False
                            if winner is not None and cu == winner and chosen_uid is None:
                                chosen_uid = cu
                                is_chosen = True
                            session_rows.append(("vote_candidate",
                                ["id", "vote_item_id", "candidate_user_id", "shuffle_round", "slot", "is_chosen"],
                                [cand_id, item_id, cu, rnd, slot, str(is_chosen).lower()]))
                        # 마지막 라운드에서 아무도 안 골렸으면 강제로 하나 고른다
                        if voted and rnd == rounds[-1] and chosen_uid is None:
                            chosen_uid = picks[0]
                            for row in reversed(session_rows):
                                if row[0] == "vote_candidate" and row[2][1] == item_id and row[2][3] == rnd and row[2][4] == 1:
                                    row[2][5] = "true"
                                    break

                    if did_shuffle:
                        ad_id += 1
                        ad_ok = self.rng.random() < v["ad_complete_rate"]
                        ad_start = served - timedelta(seconds=self.rng.randint(20, 60))
                        session_rows.append(("ad_impression",
                            ["id", "user_id", "placement", "ad_network", "ad_unit_id", "status",
                             "started_at", "completed_at"],
                            [ad_id, u.id, "VOTE_SHUFFLE", "admob", "ca-app-shuffle-01",
                             "COMPLETED" if ad_ok else "ABANDONED", iso(ad_start),
                             iso(served) if ad_ok else ""]))
                        if ad_ok:
                            shuf_id += 1
                            session_rows.append(("vote_shuffle",
                                ["id", "vote_item_id", "ad_impression_id", "created_at"],
                                [shuf_id, item_id, ad_id, iso(served)]))
                            # 셔플 광고에는 보상이 없다. 광고는 후보를 바꾸려고 보는 것이지
                            # 하트를 벌려고 보는 것이 아니다. 보상을 주면 순수 유입이 되어
                            # 나가는 곳 없이 잔액만 불어난다.
                            if h.get("ad_reward", 0) > 0:
                                u.ledger.append((ad_start, "AD_REWARD", h["ad_reward"],
                                                 "ad_impression_id", ad_id))

                    voted_at = served + timedelta(seconds=self.rng.randint(3, 25)) if voted else None
                    # 후보가 모자라면 스코프를 낮추지 않고 친구 전체에서 채운다.
                    # 채운 수를 남기지 않으면 "이 표가 진짜 같은 반에서 나온 것인가"를
                    # 나중에 물을 수 없다.
                    padded = 0
                    if scope != "GLOBAL" and self.rng.random() < v.get("padded_item_ratio", 0.0):
                        padded = self.rng.choices([1, 2, 3], [0.62, 0.28, 0.10])[0]
                    session_rows.append(("vote_item",
                        ["id", "session_id", "user_id", "question_id", "candidate_scope",
                         "position", "shuffle_count", "padded_count", "served_at", "voted_at"],
                        [item_id, sess_id, u.id, q["id"], scope, pos,
                         1 if did_shuffle else 0, padded, iso(served), iso(voted_at)]))

                    if voted and chosen_uid:
                        completed += 1
                        recv_id += 1
                        receiver = self.users[chosen_uid - 1]
                        # 열람도 건별 동전던지기가 아니라 사람의 성향이다
                        read = self.rng.random() < self.pchance(
                            rc["read_rate"], receiver, "read")
                        read_at = voted_at + timedelta(hours=self.rng.randint(1, 72)) if read else None
                        if read_at and read_at > self.end:
                            read, read_at = False, None

                        ans, ans_at, reveal = "NONE", None, "HIDDEN"
                        if read:
                            rr = self.rng.random()
                            if rr < rc["answer_public_rate"]:
                                ans = "PUBLIC"
                            elif rr < rc["answer_public_rate"] + rc["answer_private_rate"]:
                                ans = "PRIVATE"
                            if ans != "NONE":
                                ans_at = read_at + timedelta(minutes=self.rng.randint(1, 600))
                            # 건별 확률이 아니라 **그 사람의 성향**으로 정해진다
                            if self.rng.random() < receiver.hint_appetite:
                                reveal = "PARTIAL"

                        # reveal_status 는 힌트가 실제로 성사됐는지에 달려 있다.
                        # 잔액 부족으로 구매가 무산될 수 있으므로 원장 계산 후에 확정한다.
                        # 1회성 답장(W15) — 지목당한 쪽이 뽑은 쪽에게 30자 한 번.
                        # 힌트를 사야만 보낼 수 있는 게 아니다. 두 경로의 비율이 다르다.
                        reply, replied = "", None
                        if read:
                            rate = (rc.get("reply_rate_with_hint", 0.0) if reveal == "PARTIAL"
                                    else rc.get("reply_rate_no_hint", 0.0))
                            if self.rng.random() < self.pchance(
                                    rate, receiver, "reply"):
                                cand = read_at + timedelta(hours=self.rng.randint(1, 96))
                                if cand <= self.end:
                                    reply = self.rng.choice(REPLY_TEXTS)
                                    replied = cand
                                    # 앱과 같은 유형·참조를 쓴다(db/rls/replies.sql)
                                    receiver.ledger.append(
                                        (cand, "VOTE_REPLY", -20, "vote_item_id", item_id))
                        self.pending_received.append(
                            [recv_id, item_id, u.id, chosen_uid, q["id"],
                             str(read).lower(), iso(read_at), reveal, ans, iso(ans_at),
                             iso(voted_at), reply, iso(replied)])
                        if reply:
                            self.replied_receives.append((recv_id, chosen_uid, u.id, replied))

                        # 투표 적립: 투표자 + 지목당한 사람 양쪽
                        u.ledger.append((voted_at, "VOTE_REWARD",
                                         self._vote_reward(), "vote_item_id", item_id))
                        if h["reward_both_sides"]:
                            receiver.ledger.append((voted_at, "VOTE_REWARD",
                                                    self._vote_reward(), "vote_item_id", item_id))

                        # 힌트 구매 (W14 골라 사는 5+1). 잔액 확인은 원장 계산 단계에서.
                        #
                        # 옛 누진 요금(200·300·500·1000)이 아니다. 기본 5종은 각 20하트이고
                        # 순서가 없다. FULL_NAME 은 100하트인데 **기본 3개 이상**을 연 뒤에만
                        # 살 수 있다(db/rls/hints.sql 과 같은 규칙).
                        # step 은 이제 단계가 아니라 "몇 번째로 열었나"다.
                        if reveal == "PARTIAL" and read_at:
                            basic_cost = h.get("hint_basic_cost", 20)
                            name_cost = h.get("hint_fullname_cost", 100)
                            ad_ratio = h.get("hint_gender_by_ad_ratio", 0.30)

                            # 몇 개나 여는가 — 대부분 한두 개에서 멈춘다
                            n_basic = self.rng.choices([1, 2, 3, 4, 5],
                                                       [0.52, 0.26, 0.13, 0.06, 0.03])[0]
                            kinds = self.rng.sample(
                                ["GENDER", "INITIAL", "MEDIAL", "FINAL", "CLASS"], n_basic)

                            # 초성·중성·종성은 **같은 한 글자**를 가리킨다. 글자마다
                            # 따로 뽑으면 조각이 흩어져 이름이 읽히지 않는다.
                            char_idx = self.rng.randint(0, 2)

                            # step 은 **실제로 기록된** 힌트만 센다. 기간 끝을 넘어
                            # 무산된 것까지 세면 "기본 3개 이상"을 부풀려 FULL_NAME 이
                            # 자격 없이 팔린다(실제로 그렇게 1건 새어나갔다).
                            step = 0
                            for kind in kinds:
                                at = read_at + timedelta(
                                    minutes=(step + 1) * self.rng.randint(1, 30))
                                if at > self.end:
                                    break
                                step += 1
                                hint_id += 1
                                # 성별은 광고 30초로도 열린다 → heart_cost = 0 인 행이 생긴다.
                                # 정합성 검사 4번이 이 행을 위반으로 잡지 않도록 고쳐져 있다.
                                by_ad = kind == "GENDER" and self.rng.random() < ad_ratio
                                cost = 0 if by_ad else basic_cost
                                hint_ad_id = ""
                                if by_ad:
                                    # 광고로 열었으면 그 광고를 가리켜야 한다. 안 그러면
                                    # "광고로 여는 사람이 얼마나 되나"를 셀 수 없다.
                                    ad_id += 1
                                    hint_ad_id = ad_id
                                    session_rows.append(("ad_impression",
                                        ["id", "user_id", "placement", "ad_network",
                                         "ad_unit_id", "status", "started_at", "completed_at"],
                                        [ad_id, chosen_uid, "HINT_UNLOCK", "admob",
                                         "ca-app-hint-01", "COMPLETED",
                                         iso(at - timedelta(seconds=32)), iso(at)]))
                                self.pending_hints[hint_id] = [
                                    hint_id, recv_id, chosen_uid, kind, step, cost,
                                    iso(at), hint_ad_id,
                                    char_idx if kind in ("INITIAL", "MEDIAL", "FINAL") else ""]
                                self.hint_to_recv[hint_id] = recv_id
                                if not by_ad:
                                    receiver.ledger.append(
                                        (at, "HINT_PURCHASE", -cost, "hint_purchase_id", hint_id))
                                else:
                                    # 광고로 연 힌트는 원장에 안 남는다. 하트가 움직이지
                                    # 않았기 때문이다. 대신 구매 자체는 성사로 친다.
                                    self.accepted_hints.add(hint_id)

                            # 이름 공개는 기본 3개 이상을 연 뒤에만
                            if step >= 3 and self.rng.random() < 0.18:
                                at = read_at + timedelta(
                                    minutes=(step + 1) * self.rng.randint(1, 30))
                                if at <= self.end:
                                    step += 1
                                    hint_id += 1
                                    self.pending_hints[hint_id] = [
                                        hint_id, recv_id, chosen_uid, "FULL_NAME", step,
                                        name_cost, iso(at), "", ""]
                                    self.hint_to_recv[hint_id] = recv_id
                                    receiver.ledger.append(
                                        (at, "HINT_PURCHASE", -name_cost,
                                         "hint_purchase_id", hint_id))

                if not session_rows:
                    sess_id -= 1
                    continue

                status = "COMPLETED" if completed >= n_items * 0.8 else "IN_PROGRESS"
                last = started + timedelta(minutes=self.rng.randint(2, 20))
                self.w.write("vote_session",
                             ["id", "user_id", "status", "item_count", "started_at", "completed_at"],
                             [sess_id, u.id, status, n_items, iso(started),
                              iso(last) if status == "COMPLETED" else ""])
                for table, header, row in session_rows:
                    self.w.write(table, header, row)

        self._hint_rows_exist = hint_id > 0

    # -- 6. 하트 원장 --------------------------------------------------
    def gen_ledger(self):
        """
        유저별 타임라인을 시간순으로 걸으며 balance_after 를 누적한다.
        잔액이 모자라면 힌트 구매를 건너뛴다(CHECK balance_after >= 0).
        """
        h = self.cfg["hearts"]
        tx_id = 0
        pur_id = 0
        skipped_hints = 0
        capped = 0
        # vote_received 별로 **성사된** 기본 힌트 수. 광고로 연 것은 원장을 안 타고
        # 이미 성사돼 있으므로 여기서 미리 센다.
        accepted_basics: Counter[int] = Counter()
        for hid in self.accepted_hints:
            row = self.pending_hints.get(hid)
            if row and row[3] != "FULL_NAME":
                accepted_basics[row[1]] += 1

        for u in self.users:
            balance = 0
            admin_id = self.rng.choice(self.admin_ids)
            events = [(u.created_at, "SIGNUP_GRANT", h["signup_grant"], None, None)]

            # 운영자 보정·이벤트 지급. 문의를 받아 손으로 넣어주는 자리라 드물다.
            # 드물어도 있어야 한다 — 없으면 admin_id·memo 를 쓰는 경로가 통째로 빈다.
            if self.rng.random() < h.get("admin_adjust_rate", 0.02):
                at = rand_dt(self.rng, u.created_at, self.end)
                events.append((at, "ADMIN_ADJUST", self.rng.choice([50, 100, 200, 300]), None, None))
            if self.rng.random() < h.get("event_grant_rate", 0.05):
                at = rand_dt(self.rng, u.created_at, self.end)
                events.append((at, "EVENT_GRANT", self.rng.choice([50, 100]), None, None))

            # 충전. 결제자 중 일부는 헤비과금러다 — 결제 횟수도 상품도 다르다.
            # 균등하게 두면 매출 분석에서 "상위 몇 %가 매출의 몇 %"를 못 묻는다.
            if self.rng.random() < self.pchance(h["topup_rate"], u, "pay"):
                is_whale = self.rng.random() < self.pchance(
                    h.get("whale_ratio", 0.0), u, "pay")
                repeat = h.get("whale_repeat", h["topup_repeat"]) if is_whale else h["topup_repeat"]
                pw = h.get("whale_product_weights") if is_whale else h.get("product_weights")
                weights = ([pw["cheapest"], pw["second"], pw["third"], pw["largest"]]
                           if pw else [0.25, 0.25, 0.25, 0.25])
                for _ in range(self.rng.randint(*repeat)):
                    at = rand_dt(self.rng, u.created_at, self.end)
                    pid = self.rng.choices([1, 2, 3, 4], weights)[0]
                    amount = [200, 777, 1000, 4000][pid - 1]
                    price = [900, 1900, 2900, 9900][pid - 1]
                    pur_id += 1
                    ok = self.rng.random() < 0.9983          # 실측 실패율 0.17%
                    # 결제 플랫폼은 접속 플랫폼 분포를 따른다. v1 은 앱이라 iOS/AOS
                    # 였지만 ping-v2 는 웹앱이라 스토어 결제가 아니다.
                    self.w.write("heart_purchase",
                                 ["id", "user_id", "product_id", "platform", "store_transaction_id",
                                  "status", "failure_reason", "price_krw", "heart_amount",
                                  "created_at", "completed_at"],
                                 [pur_id, u.id, pid,
                                  weighted_choice(self.rng, self.cfg["sessions"]["platform_ratio"]),
                                  f"tx-{pur_id:09d}", "SUCCESS" if ok else "FAILED",
                                  "" if ok else "결제 승인 거부", price, amount,
                                  iso(at), iso(at + timedelta(seconds=3)) if ok else ""])
                    if ok:
                        events.append((at, "TOPUP", amount, "purchase_id", pur_id))

            events.extend(u.ledger)
            events.sort(key=lambda e: e[0])

            earned_today: dict[object, int] = {}
            for at, code, delta, ref_col, ref_id in events:
                # 하루 적립 상한. 파워유저가 투표만으로 무한히 쌓는 것을 막는다.
                # 상한은 **버는 쪽에만** 건다 — 충전(TOPUP)까지 막으면 결제가 사라진다.
                if delta > 0 and code in ("VOTE_REWARD", "AD_REWARD"):
                    cap = h.get("daily_earn_cap")
                    if cap:
                        day = at.date()
                        room = cap - earned_today.get(day, 0)
                        if room <= 0:
                            capped += 1
                            continue
                        delta = min(delta, room)
                        earned_today[day] = earned_today.get(day, 0) + delta
                if delta < 0 and balance + delta < 0:
                    skipped_hints += 1
                    continue                      # 잔액 부족 → 구매 성립 안 함
                if ref_col == "hint_purchase_id":
                    # ⚠️ 이름 공개는 **기본 3개 이상**을 연 뒤에만 살 수 있다.
                    # 자격은 gen_votes 에서 확인했지만, 그 사이 기본 힌트가 잔액
                    # 부족으로 무산되면 자격이 사라진다. 여기서 다시 본다 —
                    # 앞 단계에서 통과한 것이 뒤 단계에서 깨지는 자리다.
                    row = self.pending_hints.get(ref_id)
                    if row and row[3] == "FULL_NAME" and accepted_basics[row[1]] < 3:
                        skipped_hints += 1
                        continue
                    self.accepted_hints.add(ref_id)
                    if row and row[3] != "FULL_NAME":
                        accepted_basics[row[1]] += 1
                balance += delta
                tx_id += 1
                self.w.write("heart_transaction",
                             ["id", "user_id", "type_code", "delta", "balance_after",
                              "vote_item_id", "hint_purchase_id", "purchase_id",
                              "ad_impression_id", "admin_id", "memo", "created_at"],
                             [tx_id, u.id, code, delta, balance,
                              ref_id if ref_col == "vote_item_id" else "",
                              ref_id if ref_col == "hint_purchase_id" else "",
                              ref_id if ref_col == "purchase_id" else "",
                              ref_id if ref_col == "ad_impression_id" else "",
                              admin_id if code == "ADMIN_ADJUST" else "",
                              TX_MEMOS.get(code, ""), iso(at)])
            u.final_balance = balance

        self.skipped_hints = skipped_hints
        self.capped_rewards = capped

        # 성사된 힌트 구매만 기록한다. 원장 없는 구매는 존재해선 안 된다.
        revealed = set()
        for hid in sorted(self.accepted_hints):
            row = self.pending_hints.get(hid)
            if not row:
                continue
            self.w.write("hint_purchase",
                         ["id", "vote_received_id", "user_id", "hint_type", "step",
                          "heart_cost", "created_at", "ad_impression_id", "char_index"], row)
            revealed.add(self.hint_to_recv[hid])

        # 힌트가 하나도 성사되지 않았으면 열람 상태를 HIDDEN 으로 되돌린다
        downgraded = 0
        for row in self.pending_received:
            if row[7] == "PARTIAL" and row[0] not in revealed:
                row[7] = "HIDDEN"
                downgraded += 1
            self.w.write("vote_received",
                         ["id", "vote_item_id", "voter_id", "receiver_id", "question_id",
                          "is_read", "read_at", "reveal_status", "answer_status",
                          "answered_at", "created_at", "reply_text", "replied_at"], row)
        self.downgraded_reveals = downgraded

    # -- 7. 유저 행 / 세션 / 탈퇴 ---------------------------------------
    def gen_user_rows(self):
        wd = self.cfg["withdrawal"]
        ss = self.cfg["sessions"]
        sess_id = 0
        wd_id = 0
        school_counts: dict[int, int] = {}
        self._nicks: set[str] = set()
        self._codes: set[str] = set()

        for u in self.users:
            school_counts[u.school_id] = school_counts.get(u.school_id, 0) + 1
            withdrawn = self.rng.random() < wd["rate"]
            last_active = u.created_at + timedelta(days=u.activity_days) if u.activity_days else u.created_at
            last_active = min(last_active, self.end)

            # auth_user_id 는 비운다. 합성 유저는 Supabase 익명 계정이 없다.
            # 실유저와 합성을 구분하는 신호이기도 하다.
            self.w.write("app_user",
                         ["id", "auth_user_id", "nickname", "invite_code", "gender", "class_id",
                          "heart_balance", "friend_count", "service_unlocked_at", "status",
                          "is_synthetic", "is_admin", "last_active_at", "created_at", "updated_at"],
                         [u.id, "", make_nickname(self.rng, self._nicks),
                          make_invite_code(self.rng, self._codes), u.gender, u.class_id,
                          getattr(u, "final_balance", 0), len(u.friends),
                          iso(u.unlocked_at), "WITHDRAWN" if withdrawn else "ACTIVE",
                          "true", "true" if u.id in self.admin_ids else "false",
                          iso(last_active), iso(u.created_at), iso(last_active)])

            if withdrawn:
                wd_id += 1
                code = weighted_choice(self.rng, wd["reason_weights"])
                text = self.rng.choice(WITHDRAW_TEXTS) if self.rng.random() < wd["free_text_rate"] else ""
                at = min(last_active + timedelta(days=self.rng.randint(0, 5)), self.end)
                self.w.write("user_withdrawal",
                             ["id", "user_id", "reason_code", "reason_text", "created_at"],
                             [wd_id, u.id, code, text, iso(at)])

            # 세션. 당일만 쓴 유저(activity_days=0)도 **하루치는 만든다** —
            # 진짜로 세션이 없는 것은 앱을 한 번도 안 연 유저뿐이다.
            if u.no_activity:
                continue
            for day in range(u.activity_days + 1):
                d = u.created_at + timedelta(days=day)
                if d > self.end:
                    break
                for _ in range(self.rng.randint(*ss["per_active_day"])):
                    sess_id += 1
                    st = d + timedelta(minutes=self.rng.randint(0, 1439))
                    if st > self.end:
                        continue
                    dur = self.rng.randint(*ss["duration_minutes"])
                    self.w.write("user_session",
                                 ["id", "user_id", "platform", "app_version", "device_id",
                                  "started_at", "ended_at"],
                                 [sess_id, u.id, weighted_choice(self.rng, ss["platform_ratio"]),
                                  self.rng.choice(["1.0.0", "1.1.0", "1.2.0"]),
                                  f"dev-{u.id:06d}", iso(st), iso(st + timedelta(minutes=dur))])

        # 학교 학생 수 갱신 (school.csv 를 다시 쓴다)
        self._school_counts = school_counts

    # -- 8. 게시판 -----------------------------------------------------
    def gen_board(self):
        """
        학교 단위 게시판. 익명 게시판이 아니라 **닉네임이 드러나는** 자유게시판이다.
        집계 컬럼(like_count·comment_count)은 원천 행과 반드시 일치해야 한다 —
        정합성 검사가 이 둘을 대조한다.
        """
        b = self.cfg.get("board", {})
        if not b:
            return
        actives = [u for u in self.users if not u.no_activity]
        if not actives:
            return

        authors = [u for u in actives
                   if self.rng.random() < self.pchance(b.get("author_ratio", 0.12),
                                                       u, "post")]
        commenters = [u for u in actives
                      if self.rng.random() < self.pchance(b.get("commenter_ratio", 0.5),
                                                          u, "comment")]
        by_school_comm: dict[int, list[User]] = {}
        for u in commenters:
            by_school_comm.setdefault(u.school_id, []).append(u)
        by_school_act: dict[int, list[User]] = {}
        for u in actives:
            by_school_act.setdefault(u.school_id, []).append(u)

        post_id = com_id = pl_id = cl_id = 0
        lo_p, hi_p = b.get("posts_per_author", [1, 25])

        for a in authors:
            n_posts = max(1, round(self.rng.randint(lo_p, max(lo_p, hi_p // 4))
                                   * a.traits["post"]))
            if self.rng.random() < 0.05:                  # 상위 소수가 글의 다수를 만든다
                n_posts = self.rng.randint(hi_p // 2, hi_p)
            for _ in range(n_posts):
                created = rand_dt(self.rng, a.created_at, self.end)
                post_id += 1
                pool = [x for x in by_school_comm.get(a.school_id, []) if x.id != a.id]

                # 댓글
                n_com = 0
                if self.rng.random() >= b.get("zero_comment_post_ratio", 0.3) and pool:
                    n_com = max(1, int(self.rng.expovariate(
                        1 / max(b.get("comments_per_post_mean", 2.5), 0.1))))
                    n_com = min(n_com, 25, len(pool))
                com_rows = []
                seq_of: dict[int, int] = {}
                for c_author in self.rng.sample(pool, n_com) if n_com else []:
                    com_id += 1
                    at = rand_dt(self.rng, created, self.end)
                    # anonymous_seq 는 글 안에서만 유효한 번호다. 같은 사람은 같은 글에서
                    # 같은 번호를 유지해야 대화 맥락이 읽힌다.
                    seq_of.setdefault(c_author.id, len(seq_of) + 1)
                    com_rows.append((com_id, c_author, seq_of[c_author.id], at))

                # 좋아요 — 대부분 몇 개, 드물게 떡상하는 글
                likers = [x for x in by_school_act.get(a.school_id, []) if x.id != a.id]
                if self.rng.random() < b.get("viral_post_ratio", 0.02):
                    lo, hi = b.get("viral_post_likes", [80, 400])
                    n_like = min(self.rng.randint(lo, hi), len(likers))
                else:
                    n_like = min(int(self.rng.expovariate(
                        1 / max(b.get("post_likes_per_post_mean", 4.0), 0.1))), len(likers))

                self.w.write("post",
                             ["id", "school_id", "category_id", "author_id", "title", "body",
                              "view_count", "like_count", "comment_count", "report_count",
                              "status", "created_at", "updated_at"],
                             [post_id, a.school_id, self.rng.randint(1, 5), a.id,
                              self.rng.choice(POST_TITLES), self.rng.choice(POST_BODIES),
                              n_like * self.rng.randint(4, 30), n_like, len(com_rows), 0,
                              "DELETED" if self.rng.random() < 0.03 else "PUBLISHED",
                              iso(created), iso(created)])
                self.posts.append((post_id, a.school_id, a.id, created))

                # 대댓글 — 앞선 댓글에 답을 단다. 같은 사람이 같은 글에 두 번 쓰면
                # uq_comment_anon 이 막으므로 **글쓴이가 다른 댓글에만** 붙인다.
                written: list[int] = []
                for cid, c_author, seq, at in sorted(com_rows, key=lambda r: r[3]):
                    c_likers = [x for x in likers if x.id != c_author.id]
                    n_clike = 0
                    if self.rng.random() < b.get("comment_like_ratio", 0.18) and c_likers:
                        n_clike = min(self.rng.randint(1, 6), len(c_likers))
                    self.w.write("post_comment",
                                 ["id", "post_id", "parent_comment_id", "author_id",
                                  "anonymous_seq", "body", "like_count", "status",
                                  "created_at", "updated_at"],
                                 [cid, post_id,
                                  self.rng.choice(written)
                                  if written and self.rng.random() < 0.28 else "",
                                  c_author.id, seq,
                                  self.rng.choice(COMMENT_BODIES), n_clike,
                                  "HIDDEN" if self.rng.random() < 0.02 else "PUBLISHED",
                                  iso(at), iso(at)])
                    written.append(cid)
                    self.comments.append((cid, post_id, c_author.id, at))
                    for liker in self.rng.sample(c_likers, n_clike) if n_clike else []:
                        cl_id += 1
                        self.w.write("comment_like",
                                     ["id", "comment_id", "user_id", "created_at"],
                                     [cl_id, cid, liker.id, iso(rand_dt(self.rng, at, self.end))])

                for liker in self.rng.sample(likers, n_like) if n_like else []:
                    pl_id += 1
                    self.w.write("post_like", ["id", "post_id", "user_id", "created_at"],
                                 [pl_id, post_id, liker.id,
                                  iso(rand_dt(self.rng, created, self.end))])

        # 대댓글 — 이미 쓴 댓글 일부에 부모를 달아준다면 UNIQUE 가 깨지므로
        # 여기서는 만들지 않는다. parent_comment_id 는 빈 채로 둔다.

    # -- 9. 신고 · 제재 · 차단 -------------------------------------------
    def gen_moderation(self):
        """
        신고는 **30% 가 PENDING 으로 고인다.** 이건 버그가 아니라 운영 현실이라
        일부러 재현한다(처리 인력이 없다). 대상 타입은 골고루 나와야 한다.
        """
        m = self.cfg.get("moderation", {})
        if not m:
            return
        actives = [u for u in self.users if not u.no_activity]
        if not actives:
            return

        n_reports = int(self.w.counts.get("vote_item", 0)
                        / 1000 * m.get("reports_per_1000_vote_items", 4))
        n_reports = max(n_reports, 12)
        mix = m.get("target_type_mix", {"USER": 1.0})
        reasons = {
            "USER":     ["U_HARASSMENT", "U_IMPERSONATION", "U_SPAM", "U_INAPPROPRIATE"],
            "QUESTION": ["Q_OFFENSIVE", "Q_APPEARANCE", "Q_SEXUAL", "Q_ETC"],
            "POST":     ["P_ABUSE", "P_SEXUAL", "P_SPAM"],
            "COMMENT":  ["C_ABUSE", "C_SPAM"],
        }
        # 신고는 특정 대상에 몰린다 — 피신고 대상의 10%가 신고의 절반을 받는다.
        # 균등하게 흩뿌리면 "반복 피신고자" 라는 분석 대상이 사라진다.
        hot_users = self.rng.sample(actives, max(1, len(actives) // 50))

        rep_id = san_id = 0
        reviewed_reports: list[tuple[int, int, datetime]] = []
        for _ in range(n_reports):
            ttype = weighted_choice(self.rng, mix)
            if ttype == "POST" and not self.posts:
                ttype = "USER"
            if ttype == "COMMENT" and not self.comments:
                ttype = "USER"
            reporter = self.rng.choice(actives)

            tgt_user = tgt_q = tgt_post = tgt_com = ""
            if ttype == "USER":
                # 신고당하는 쪽도 성향이 있다. 무작위로 고르면 "반복 피신고자"라는
                # 분석 대상이 사라진다. 악성형이 여기서 드러난다.
                victim = (self.rng.choice(hot_users) if self.rng.random() < 0.35
                          else self.rng.choices(
                              actives, [u.traits["reported"] for u in actives])[0])
                if victim.id == reporter.id:
                    continue
                tgt_user = victim.id
                at = rand_dt(self.rng, max(reporter.created_at, victim.created_at), self.end)
            elif ttype == "QUESTION":
                tgt_q = self.rng.choice(self.questions)["id"]
                at = rand_dt(self.rng, reporter.created_at, self.end)
            elif ttype == "POST":
                pid, _sch, author, created = self.rng.choice(self.posts)
                if author == reporter.id:
                    continue
                tgt_post, at = pid, rand_dt(self.rng, created, self.end)
            else:
                cid, _pid, author, created = self.rng.choice(self.comments)
                if author == reporter.id:
                    continue
                tgt_com, at = cid, rand_dt(self.rng, created, self.end)

            r = self.rng.random()
            reviewed = r < m.get("reviewed_rate", 0.7)
            actioned = reviewed and self.rng.random() < m.get("actioned_rate", 0.25)
            status = "PENDING" if not reviewed else ("ACTIONED" if actioned else "DISMISSED")
            rev_admin = self.rng.choice(self.reviewer_ids) if reviewed else ""
            rev_at = at + timedelta(hours=self.rng.randint(2, 240)) if reviewed else None
            if rev_at and rev_at > self.end:
                rev_at, status, rev_admin, actioned = None, "PENDING", "", False

            rep_id += 1
            self.w.write("report",
                         ["id", "reporter_id", "target_type", "target_user_id",
                          "target_question_id", "target_post_id", "target_comment_id",
                          "reason_code", "detail_text", "status",
                          "reviewed_by_admin_id", "reviewed_at", "created_at"],
                         [rep_id, reporter.id, ttype, tgt_user, tgt_q, tgt_post, tgt_com,
                          self.rng.choice(reasons[ttype]),
                          self.rng.choice(REPORT_DETAILS), status,
                          rev_admin, iso(rev_at), iso(at)])
            if actioned and ttype == "USER":
                reviewed_reports.append((rep_id, tgt_user, rev_at))

        # 제재 — 근거 신고를 반드시 가리킨다. 이 연결이 v1 에는 아예 없었다.
        for rid, uid, when in reviewed_reports:
            san_id += 1
            # USER 대상 정책 3종. 균등하게 뽑으면 영구정지가 경고만큼 나온다 —
            # 임계값이 5회 / 10회 / 20회 이므로 실제로는 경고가 압도적이어야 한다.
            policy = self.rng.choices([1, 2, 3], [0.60, 0.30, 0.10])[0]
            stype = ["WARNING", "SUSPEND", "BAN"][policy - 1]
            days = {"WARNING": None, "SUSPEND": 7, "BAN": None}[stype]
            ends = when + timedelta(days=days) if days else None
            self.w.write("sanction",
                         ["id", "user_id", "type", "triggered_by_report_id", "policy_id",
                          "issued_by_admin_id", "reason", "starts_at", "ends_at",
                          "is_active", "created_at"],
                         [san_id, uid, stype, rid, policy,
                          self.rng.choice(self.moderator_ids),
                          f"신고 누적에 따른 {stype}", iso(when), iso(ends),
                          "true" if (ends is None or ends > self.end) else "false",
                          iso(when)])

        # 차단 — 신고와 별개 경로다. 신고는 운영자에게, 차단은 나에게만 영향을 준다.
        bl = m.get("block", {})
        blk_id = 0
        seen: set[tuple[int, int]] = set()
        for u in actives:
            if self.rng.random() >= bl.get("user_ratio", 0.03):
                continue
            for _ in range(self.rng.randint(*bl.get("per_user", [1, 4]))):
                other = self.rng.choice(actives)
                if other.id == u.id or (u.id, other.id) in seen:
                    continue
                seen.add((u.id, other.id))
                blk_id += 1
                self.w.write("block_record",
                             ["id", "user_id", "blocked_user_id", "reason", "created_at"],
                             [blk_id, u.id, other.id,
                              self.rng.choice(["UNKNOWN_PERSON", "AWKWARD", "IMPERSONATION",
                                               "IRRELEVANT", "TOO_MANY"]),
                              iso(rand_dt(self.rng, max(u.created_at, other.created_at), self.end))])

    # -- 10. 추천 거절 --------------------------------------------------
    def gen_recommend_rejects(self):
        """'안 볼래'. 추천 목록 자체는 저장하지 않는다 — 이 표에는 거절만 들어온다."""
        fc = self.cfg.get("friends", {}).get("rejected_recommendation", {})
        if not fc:
            return
        rid = 0
        seen: set[tuple[int, int]] = set()
        for u in self.users:
            if self.rng.random() >= fc.get("user_ratio", 0.15):
                continue
            pool = [x for x in self.by_school.get(u.school_id, [])
                    if x != u.id and x not in u.friends]
            if not pool:
                continue
            lo, hi = fc.get("per_user", [1, 5])
            for other in self.rng.sample(pool, min(self.rng.randint(lo, hi), len(pool))):
                if (u.id, other) in seen:
                    continue
                seen.add((u.id, other))
                rid += 1
                at = rand_dt(self.rng, max(u.created_at, self.users[other - 1].created_at), self.end)
                # score 는 항상 0 이다. 추천 점수를 매기던 자리인데 거절만 들어온다.
                self.w.write("rejected_friend_recommendations",
                             ["id", "user_id", "recommended_user_id", "reason", "score",
                              "created_at", "dismissed_at"],
                             [rid, u.id, other,
                              self.rng.choices(["SAME_SCHOOL", "SAME_CLASS", "MUTUAL_FRIEND"],
                                               [0.6, 0.25, 0.15])[0],
                              0, iso(at),
                              iso(at) if self.rng.random() < 0.8 else ""])

    # -- 11. 학교 정보 --------------------------------------------------
    def gen_school_info(self):
        """
        급식 · 학사일정 · 공지 · 시간표.
        NEIS 를 새로 부르지 않고, 실데이터의 **구조만 본떠** 학교 수만큼 늘린다.
        """
        si = self.cfg.get("school_info", {})
        if not si:
            return
        mp_id = mi_id = ev_id = no_id = nr_id = tt_id = 0
        days = (self.end - self.start).days
        actives = [u for u in self.users if not u.no_activity]
        by_school_act: dict[int, list[User]] = {}
        for u in actives:
            by_school_act.setdefault(u.school_id, []).append(u)

        for s in self.schools:
            # --- 급식: 평일만. 휴일에 급식이 없는 것은 결측이 아니라 정상이다.
            for d in range(days):
                day = self.start + timedelta(days=d)
                if day.weekday() >= 5:
                    continue
                if self.rng.random() < 0.04:          # 재량휴업·시험 등
                    continue
                for meal in ("LUNCH", "BREAKFAST", "DINNER"):
                    # 중·고 모두 점심은 매일, 조·석식은 일부 학교만
                    if meal == "BREAKFAST" and self.rng.random() > 0.06:
                        continue
                    if meal == "DINNER" and (s["is_middle"] or self.rng.random() > 0.35):
                        continue
                    mp_id += 1
                    n_items = self.rng.randint(*si.get("meal", {}).get("items_per_meal", [4, 7]))
                    self.w.write("meal_plan",
                                 ["id", "school_id", "serve_date", "meal_type", "calorie_kcal",
                                  "source", "external_id", "is_manually_overridden",
                                  "synced_at", "created_at"],
                                 [mp_id, s["id"], day.date().isoformat(), meal,
                                  round(self.rng.uniform(480, 1020), 1),
                                  "MANUAL" if self.rng.random() < 0.05 else "NEIS",
                                  f"{s['id']}-{day.date()}-{meal}",
                                  "true" if self.rng.random() < 0.02 else "false",
                                  iso(day), iso(day)])
                    kinds = ["밥", "국", "주찬", "부찬", "김치", "후식"]
                    for order, kind in enumerate(kinds[:n_items], start=1):
                        mi_id += 1
                        self.w.write("meal_menu_item",
                                     ["id", "meal_plan_id", "dish_name", "allergy_codes",
                                      "sort_order"],
                                     [mi_id, mp_id, self.rng.choice(DISHES[kind]),
                                      ".".join(self.rng.sample(ALLERGY_CODES,
                                                               self.rng.randint(1, 3)))
                                      if self.rng.random() < 0.55 else "",
                                      order])

            # --- 학사일정: NEIS 가 하루씩 주는 것을 기간으로 묶어 둔 형태
            for _ in range(self.rng.randint(2, 4) * max(1, self.cfg["months"])):
                etype = weighted_choice(self.rng, {
                    "HOLIDAY": 0.2, "EXAM": 0.25, "CEREMONY": 0.25,
                    "FIELD_TRIP": 0.15, "ETC": 0.15})
                start_d = self.start + timedelta(days=self.rng.randint(0, max(days - 1, 1)))
                span = self.rng.choices([0, 1, 2, 4, 13], [0.55, 0.2, 0.13, 0.08, 0.04])[0]
                ev_id += 1
                self.w.write("school_event",
                             ["id", "school_id", "title", "event_type", "start_date",
                              "end_date", "is_all_day", "grade_scope", "source",
                              "external_id", "is_manually_overridden", "synced_at"],
                             [ev_id, s["id"], self.rng.choice(EVENT_TITLES[etype]), etype,
                              start_d.date().isoformat(),
                              (start_d + timedelta(days=span)).date().isoformat(),
                              "true" if span > 0 or self.rng.random() < 0.8 else "false",
                              self.rng.choice([1, 2, 3]) if self.rng.random() < 0.25 else "",
                              "MANUAL" if self.rng.random() < 0.08 else "NEIS",
                              f"EV{ev_id:08d}",
                              "true" if self.rng.random() < 0.03 else "false", iso(start_d)])

            # --- 공지 + 열람 기록
            for _ in range(self.rng.randint(*si.get("notice", {})
                                            .get("per_school_per_month", [2, 4]))
                           * max(1, self.cfg["months"])):
                no_id += 1
                pub = rand_dt(self.rng, self.start, self.end)
                self.w.write("school_notice",
                             ["id", "school_id", "title", "body", "source", "external_id",
                              "is_manually_overridden", "created_by_admin_id",
                              "published_at", "created_at", "updated_at"],
                             [no_id, s["id"], self.rng.choice(NOTICE_TITLES),
                              self.rng.choice(POST_BODIES),
                              "MANUAL" if self.rng.random() < 0.4 else "NEIS",
                              f"NT{no_id:08d}",
                              "true" if self.rng.random() < 0.05 else "false",
                              self.rng.choice(self.admin_ids), iso(pub), iso(pub), iso(pub)])
                readers = by_school_act.get(s["id"], [])
                lo, hi = si.get("notice_read", {}).get("read_ratio", [0.2, 0.6])
                n_read = int(len(readers) * self.rng.uniform(lo, hi))
                for r in self.rng.sample(readers, min(n_read, len(readers))):
                    at = rand_dt(self.rng, max(pub, r.created_at), self.end) \
                        if max(pub, r.created_at) < self.end else None
                    if at is None:
                        continue
                    nr_id += 1
                    self.w.write("school_notice_read",
                                 ["id", "notice_id", "user_id", "read_at"],
                                 [nr_id, no_id, r.id, iso(at)])

            # --- 시간표: 학급 × 요일 × 교시. 한 칸에 두 과목이 못 들어간다.
            semester = f"{self.start.year}-{1 if self.start.month <= 7 else 2}"
            n_period = si.get("timetable", {}).get("periods_per_week", 30) // 5
            for cid in s["class_ids"]:
                for dow in range(1, 6):
                    for period in range(1, n_period + 1):
                        tt_id += 1
                        self.w.write("timetable",
                                     ["id", "class_id", "semester", "day_of_week", "period",
                                      "subject_name", "teacher_name_masked", "room",
                                      "source", "is_manually_overridden", "synced_at"],
                                     [tt_id, cid, semester, dow, period,
                                      self.rng.choice(SUBJECTS),
                                      f"{self.rng.choice(SURNAMES)}○○",
                                      self.rng.choice(["본관 3-2", "과학실", "음악실", "체육관",
                                                       "컴퓨터실", "미술실", ""]),
                                      "MANUAL" if self.rng.random() < 0.1 else "NEIS",
                                      "true" if self.rng.random() < 0.02 else "false",
                                      iso(self.start)])

    def rewrite_schools(self):
        path = self.w.out_dir / "school.csv"
        rows = list(csv.reader(open(path, encoding="utf-8")))
        header, body = rows[0], rows[1:]
        idx = header.index("student_count")
        for r in body:
            r[idx] = str(self._school_counts.get(int(r[0]), 0))
        with open(path, "w", newline="", encoding="utf-8") as f:
            wr = csv.writer(f)
            wr.writerow(header)
            wr.writerows(body)

    def run(self):
        # 순서에 제약이 있다 — 게시판이 신고보다 먼저여야 신고할 대상이 있고,
        # 학교 정보는 유저가 있어야 열람 기록을 만들 수 있다.
        steps = [
            ("조직 생성", self.gen_org),
            ("유저 생성", self.gen_users),
            ("친구 그래프 생성", self.gen_friends),
            ("질문 생성", self.gen_questions),
            ("투표 생성 (가장 오래 걸림)", self.gen_votes),
            ("하트 원장 계산", self.gen_ledger),
            ("유저·세션·탈퇴 기록", self.gen_user_rows),
            ("게시판 생성", self.gen_board),
            ("신고·제재·차단 생성", self.gen_moderation),
            ("추천 거절 생성", self.gen_recommend_rejects),
            ("학교 정보 생성 (급식·일정·공지·시간표)", self.gen_school_info),
        ]
        for i, (label, fn) in enumerate(steps, start=1):
            print(f"{i}/{len(steps)} {label}...", flush=True)
            fn()
        self.w.close()
        self.rewrite_schools()
        self.write_persona_key()
        return self.w.counts

    def write_persona_key(self):
        """
        정답지. **DB 에도 CSV 에도 안 들어간다.**
        분석자가 이걸 보고 시작하면 클러스터링에서 발견할 것이 없어진다.
        검증(유형이 너무 또렷하지 않은가)에만 쓴다.
        """
        import json
        out = self.w.out_dir.parent / "personas.json"
        out.write_text(json.dumps({
            "note": "생성기 내부 상태. 분석자에게 주지 말 것.",
            "traits": list(TRAITS),
            "users": {str(u.id): {"persona": u.persona,
                                  "tier": u.tier,
                                  "traits": {t: round(u.traits[t], 4) for t in TRAITS}}
                      for u in self.users},
        }, ensure_ascii=False), encoding="utf-8")
        print(f"\n페르소나 정답지 — {out} (분석자에게 주지 않는다)")


def main():
    # Windows 기본 콘솔이 cp949 라 한글·기호 출력이 깨지거나 예외가 난다
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=str, default=None,
                    help="설정 파일. 이름만 주면 generator/config/ 에서 찾는다")
    ap.add_argument("--users", type=int)
    ap.add_argument("--months", type=int)
    ap.add_argument("--schools", type=int)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    path = CONFIG_PATH
    if args.config:
        path = Path(args.config)
        if not path.exists():
            path = CONFIG_DIR / args.config
        if not path.exists():
            print(f"설정 파일을 찾을 수 없다: {args.config}", file=sys.stderr)
            return 1
    print(f"설정 — {path.name}")
    cfg = load_config(path)
    if args.users:
        cfg["users"]["count"] = args.users
    if args.months:
        cfg["months"] = args.months
    if args.schools:
        cfg["schools"]["count"] = args.schools
    if args.seed:
        cfg["seed"] = args.seed

    g = Generator(cfg, args.out)
    counts = g.run()

    print("\n생성 완료 —", args.out)
    width = max(len(t) for t in counts)
    for t in sorted(counts, key=lambda x: -counts[x]):
        print(f"  {t:<{width}}  {counts[t]:>9,}")
    print(f"\n  총 {sum(counts.values()):,} 행")
    if g.skipped_hints:
        print(f"\n  잔액 부족으로 무산된 힌트 구매: {g.skipped_hints:,}건")
        print(f"  그에 따라 HIDDEN 으로 되돌린 열람 기록: {g.downgraded_reveals:,}건")
        print("  → 원장에 없는 구매 행은 기록하지 않았다(설계 규칙).")


if __name__ == "__main__":
    sys.exit(main())
