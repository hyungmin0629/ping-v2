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
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "generator" / "config" / "distribution.yaml"
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
}

WITHDRAW_TEXTS = [
    "쓸 일이 없어졌어요", "친구들이 안 해서요", "질문이 반복돼서 재미없어요",
    "알림이 너무 자주 와요", "생각보다 할 게 없네요", "다른 앱 쓰고 있어요",
]


# =====================================================================
# 유틸
# =====================================================================

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
                    self.classes.append({"id": cls_id, "school_id": sid, "grade": grade, "class_num": cnum})
                    school["class_ids"].append(cls_id)
                    self.w.write("grade_class", ["id", "school_id", "grade", "class_num", "created_at"],
                                 [cls_id, sid, grade, cnum, iso(self.start)])
            self.schools.append(school)

        # 운영자 — 질문 검수·신고 처리의 주체.
        # 구 스키마에는 이 개념이 없어 운영 행위의 작성자를 알 수 없었다.
        admins = [
            (1, "관*자", "SUPER"),
            (2, "김*원", "REVIEWER"),
            (3, "이*진", "REVIEWER"),
            (4, "박*영", "MODERATOR"),
            (5, "최*수", "MODERATOR"),
        ]
        for aid, name, role in admins:
            self.w.write("admin_user",
                         ["id", "name_masked", "role", "school_id", "is_active", "created_at"],
                         [aid, name, role, "", "true", iso(self.start)])
        self.reviewer_ids = [2, 3]
        self.moderator_ids = [4, 5]

        # student_count 는 유저 배정 후 갱신되므로 일단 0으로 두고 마지막에 다시 쓴다
        for s in self.schools:
            self.w.write("school",
                         ["id", "name_masked", "region_id", "school_type", "neis_school_code",
                          "student_count", "created_at", "updated_at"],
                         [s["id"], s["name"], s["region_id"],
                          "MIDDLE" if s["is_middle"] else "HIGH",
                          f"N{s['id']:06d}", 0, iso(self.start), iso(self.start)])

    # -- 2. 유저 ------------------------------------------------------
    def gen_users(self):
        uc = self.cfg["users"]
        ret = self.cfg["retention"]
        spike_end = self.start + timedelta(days=14)

        # 리텐션 구간을 미리 뽑아둔다
        buckets = [
            (ret["no_activity"], (0, 0)),
            (ret["same_day_only"], (0, 0)),
            (ret["within_week"], (1, 6)),
            (ret["within_month"], (7, 29)),
            (ret["long_term"], (30, 30 * self.cfg["months"])),
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

            r = self.rng.random()
            acc = 0.0
            span = (0, 0)
            for weight, rng_days in buckets:
                acc += weight
                if r <= acc:
                    span = rng_days
                    break
            days = self.rng.randint(*span) if span[1] > 0 else 0
            no_activity = r <= ret["no_activity"]

            u = User(
                id=uid,
                class_id=cls["id"],
                school_id=cls["school_id"],
                created_at=created,
                gender="F" if self.rng.random() < uc["gender_ratio_f"] else "M",
                activity_days=0 if no_activity else days,
                is_power=self.rng.random() < self.cfg["voting"]["power_user_ratio"],
            )
            self.users.append(u)
            self.by_class.setdefault(cls["id"], []).append(uid)
            self.by_school.setdefault(cls["school_id"], []).append(uid)

    # -- 3. 친구 그래프 -----------------------------------------------
    def gen_friends(self):
        fc = self.cfg["friends"]
        lo, hi = fc["per_user"]
        med = fc["per_user_median"]
        edges: set[tuple[int, int]] = set()

        for u in self.users:
            if self.rng.random() < fc["locked_user_ratio"]:
                target = self.rng.randint(0, 4)          # 게이트 미달 유저
            else:
                target = int(self.rng.triangular(lo, hi, med))
            need = target - len(u.friends)
            attempts = 0
            while need > 0 and attempts < need * 12:
                attempts += 1
                r = self.rng.random()
                if r < fc["same_class_ratio"]:
                    pool = self.by_class.get(u.class_id, [])
                elif r < fc["same_school_ratio"]:
                    pool = self.by_school.get(u.school_id, [])
                else:
                    pool = None
                cand = self.rng.choice(pool) if pool else self.rng.randint(1, len(self.users))
                if cand == u.id or cand in u.friends:
                    continue
                other = self.users[cand - 1]
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
            self.w.write("friendship",
                         ["id", "user_low_id", "user_high_id", "source", "created_at"],
                         [fs_id, lo_id, hi_id, source, iso(responded)])

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
        # 90_seed_master.sql 이 넣는 카테고리 id 순서와 맞춘다
        codes = ["PERSONALITY", "RELATIONSHIP", "TALENT", "HUMOR", "SCHOOL_LIFE", "FUTURE", "TASTE"]
        for i, code in enumerate(codes, start=1):
            self.categories[code] = i

        qid = 0
        pool = [(c, t) for c in codes for t in QUESTION_TEMPLATES[c]]
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
                              "USER_SUBMITTED" if is_user else "OFFICIAL", 0, "", iso(self.start)])

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

    # -- 5. 투표 ------------------------------------------------------
    def gen_votes(self):
        v = self.cfg["voting"]
        rc = self.cfg["received"]
        h = self.cfg["hearts"]

        by_scope: dict[str, list[dict]] = {"CLASS": [], "SCHOOL": [], "GLOBAL": []}
        for q in self.questions:
            by_scope[q["scope"]].append(q)

        sess_id = item_id = cand_id = ad_id = shuf_id = recv_id = hint_id = 0
        lo_s, hi_s = v["sessions_per_active_user"]

        for u in self.users:
            if not u.unlocked_at or u.activity_days == 0 or len(u.friends) < 5:
                continue
            # 세션 수는 활동 기간에 비례해야 한다.
            # 3일 쓰고 떠난 유저가 40세션을 돌 수는 없다.
            n_sess = max(1, round((u.activity_days + 1) * self.rng.uniform(0.8, 2.5)))
            if u.is_power:
                n_sess = int(n_sess * v["power_user_multiplier"] / 2)
            n_sess = min(n_sess, hi_s * 3)
            active_end = min(u.unlocked_at + timedelta(days=u.activity_days), self.end)

            friend_ids = list(u.friends)
            same_class = [f for f in friend_ids if self.users[f - 1].class_id == u.class_id]
            same_school = [f for f in friend_ids if self.users[f - 1].school_id == u.school_id]

            for _ in range(n_sess):
                started = rand_dt(self.rng, u.unlocked_at, active_end)
                sess_id += 1
                n_items = v["items_per_session"]
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

                    did_shuffle = self.rng.random() < v["shuffle_rate"]
                    rounds = [0, 1] if did_shuffle else [0]
                    chosen_uid = None
                    voted = self.rng.random() < v["complete_rate"]

                    for rnd in rounds:
                        picks = self.rng.sample(pool, 4)
                        for slot, cu in enumerate(picks, start=1):
                            cand_id += 1
                            is_chosen = False
                            if voted and rnd == rounds[-1] and slot == self.rng.randint(1, 4):
                                if chosen_uid is None:
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
                            u.ledger.append((ad_start, "AD_REWARD", h["ad_reward"], "ad_impression_id", ad_id))

                    voted_at = served + timedelta(seconds=self.rng.randint(3, 25)) if voted else None
                    session_rows.append(("vote_item",
                        ["id", "session_id", "user_id", "question_id", "candidate_scope",
                         "position", "shuffle_count", "served_at", "voted_at"],
                        [item_id, sess_id, u.id, q["id"], scope, pos,
                         1 if did_shuffle else 0, iso(served), iso(voted_at)]))

                    if voted and chosen_uid:
                        completed += 1
                        recv_id += 1
                        receiver = self.users[chosen_uid - 1]
                        read = self.rng.random() < rc["read_rate"]
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
                            if self.rng.random() < rc["reveal_rate"]:
                                reveal = "PARTIAL"

                        # reveal_status 는 힌트가 실제로 성사됐는지에 달려 있다.
                        # 잔액 부족으로 구매가 무산될 수 있으므로 원장 계산 후에 확정한다.
                        self.pending_received.append(
                            [recv_id, item_id, u.id, chosen_uid, q["id"],
                             str(read).lower(), iso(read_at), reveal, ans, iso(ans_at), iso(voted_at)])

                        # 투표 적립: 투표자 + 지목당한 사람 양쪽
                        u.ledger.append((voted_at, "VOTE_REWARD",
                                         self.rng.randint(*h["vote_reward"]), "vote_item_id", item_id))
                        if h["reward_both_sides"]:
                            receiver.ledger.append((voted_at, "VOTE_REWARD",
                                                    self.rng.randint(*h["vote_reward"]), "vote_item_id", item_id))

                        # 힌트 구매 (누진). 잔액 확인은 원장 계산 단계에서 한다.
                        if reveal == "PARTIAL" and read_at:
                            # 실측 분포: 1단계 83% / 2단계 13% / 3단계 3.5% / 4단계 0.5%
                            steps = self.rng.choices([1, 2, 3, 4], [0.83, 0.13, 0.035, 0.005])[0]
                            for step in range(1, steps + 1):
                                hint_id += 1
                                cost = h["hint_cost_steps"][step - 1]
                                at = read_at + timedelta(minutes=step * self.rng.randint(1, 30))
                                if at > self.end:
                                    break
                                self.pending_hints[hint_id] = [
                                    hint_id, recv_id, chosen_uid,
                                    ["INITIAL", "GENDER", "CLASS", "FULL_NAME"][step - 1],
                                    step, cost, iso(at)]
                                self.hint_to_recv[hint_id] = recv_id
                                receiver.ledger.append((at, "HINT_PURCHASE", -cost, "hint_purchase_id", hint_id))

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
        rows_purchase = []

        for u in self.users:
            balance = 0
            events = [(u.created_at, "SIGNUP_GRANT", h["signup_grant"], None, None)]

            # 충전
            if self.rng.random() < h["topup_rate"]:
                for _ in range(self.rng.randint(*h["topup_repeat"])):
                    at = rand_dt(self.rng, u.created_at, self.end)
                    pid = self.rng.randint(1, 4)
                    amount = [200, 777, 1000, 4000][pid - 1]
                    price = [900, 1900, 2900, 9900][pid - 1]
                    pur_id += 1
                    ok = self.rng.random() < 0.9983          # 실측 실패율 0.17%
                    rows_purchase.append(
                        ["id", "user_id", "product_id", "platform", "store_transaction_id",
                         "status", "failure_reason", "price_krw", "heart_amount",
                         "created_at", "completed_at"],
                    )
                    self.w.write("heart_purchase",
                                 ["id", "user_id", "product_id", "platform", "store_transaction_id",
                                  "status", "failure_reason", "price_krw", "heart_amount",
                                  "created_at", "completed_at"],
                                 [pur_id, u.id, pid,
                                  self.rng.choices(["IOS", "ANDROID"], [0.65, 0.35])[0],
                                  f"tx-{pur_id:09d}", "SUCCESS" if ok else "FAILED",
                                  "" if ok else "결제 승인 거부", price, amount,
                                  iso(at), iso(at + timedelta(seconds=3)) if ok else ""])
                    if ok:
                        events.append((at, "TOPUP", amount, "purchase_id", pur_id))

            events.extend(u.ledger)
            events.sort(key=lambda e: e[0])

            for at, code, delta, ref_col, ref_id in events:
                if delta < 0 and balance + delta < 0:
                    skipped_hints += 1
                    continue                      # 잔액 부족 → 구매 성립 안 함
                if ref_col == "hint_purchase_id":
                    self.accepted_hints.add(ref_id)
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
                              "", "", iso(at)])
            u.final_balance = balance

        self.skipped_hints = skipped_hints

        # 성사된 힌트 구매만 기록한다. 원장 없는 구매는 존재해선 안 된다.
        revealed = set()
        for hid in sorted(self.accepted_hints):
            row = self.pending_hints.get(hid)
            if not row:
                continue
            self.w.write("hint_purchase",
                         ["id", "vote_received_id", "user_id", "hint_type", "step",
                          "heart_cost", "created_at"], row)
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
                          "answered_at", "created_at"], row)
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
                          "is_synthetic", "last_active_at", "created_at", "updated_at"],
                         [u.id, "", make_nickname(self.rng, self._nicks),
                          make_invite_code(self.rng, self._codes), u.gender, u.class_id,
                          getattr(u, "final_balance", 0), len(u.friends),
                          iso(u.unlocked_at), "WITHDRAWN" if withdrawn else "ACTIVE",
                          "true", iso(last_active), iso(u.created_at), iso(last_active)])

            if withdrawn:
                wd_id += 1
                code = weighted_choice(self.rng, wd["reason_weights"])
                text = self.rng.choice(WITHDRAW_TEXTS) if self.rng.random() < wd["free_text_rate"] else ""
                at = min(last_active + timedelta(days=self.rng.randint(0, 5)), self.end)
                self.w.write("user_withdrawal",
                             ["id", "user_id", "reason_code", "reason_text", "created_at"],
                             [wd_id, u.id, code, text, iso(at)])

            # 세션
            if u.activity_days == 0:
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
        print("1/7 조직 생성...", flush=True)
        self.gen_org()
        print("2/7 유저 생성...", flush=True)
        self.gen_users()
        print("3/7 친구 그래프 생성...", flush=True)
        self.gen_friends()
        print("4/7 질문 생성...", flush=True)
        self.gen_questions()
        print("5/7 투표 생성... (가장 오래 걸림)", flush=True)
        self.gen_votes()
        print("6/7 하트 원장 계산...", flush=True)
        self.gen_ledger()
        print("7/7 유저·세션·탈퇴 기록...", flush=True)
        self.gen_user_rows()
        self.w.close()
        self.rewrite_schools()
        return self.w.counts


def main():
    # Windows 기본 콘솔이 cp949 라 한글·기호 출력이 깨지거나 예외가 난다
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int)
    ap.add_argument("--months", type=int)
    ap.add_argument("--schools", type=int)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
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
