import { createClient } from "./supabase/client";

/**
 * 내 계정(app_user)을 읽고 만드는 곳.
 *
 * 가입은 반드시 complete_onboarding RPC 로만 한다. 브라우저에는 app_user 의
 * INSERT 권한이 아예 없다 — 열어주면 heart_balance 를 얹어서 계정을 만들 수 있다.
 * (db/rls/onboarding.sql, 검증은 db/rls/verify.py 의 "온보딩 시험")
 */

export type Profile = {
  id: number;
  nickname: string;
  inviteCode: string;
  heartBalance: number;
  friendCount: number;
  /** 친구 5명을 채워 투표가 열렸는가 */
  unlocked: boolean;
  /** 화면에 보여줄 소속. 예: "코드잇 DA 14기 · 1팀" */
  belonging: string;
};

export type School = { id: number; name: string };
export type ClassOption = { id: number; label: string };

/**
 * 학급 표시명.
 *
 * label 은 임시 조직(팀)처럼 "N학년 M반"으로 부르지 않는 곳을 위한 컬럼이다.
 * 비어 있으면 학년·반으로 조립한다 — NEIS 로 실제 학교가 들어오면 그쪽이 된다.
 */
function classLabel(grade: number, classNum: number, label: string | null) {
  return label?.trim() || `${grade}학년 ${classNum}반`;
}

/** PostgREST 는 관계를 상황에 따라 객체나 배열로 준다. 하나로 맞춘다. */
function one<T>(v: T | T[] | null | undefined): T | null {
  if (Array.isArray(v)) return v[0] ?? null;
  return v ?? null;
}

const PROFILE_COLUMNS = `
  id, nickname, invite_code, heart_balance, friend_count, service_unlocked_at,
  grade_class ( grade, class_num, label, school ( name_masked ) )
`;

type ProfileRow = {
  id: number;
  nickname: string;
  invite_code: string;
  heart_balance: number;
  friend_count: number;
  service_unlocked_at: string | null;
  grade_class:
    | {
        grade: number;
        class_num: number;
        label: string | null;
        school: { name_masked: string } | { name_masked: string }[] | null;
      }
    | null
    | Array<{
        grade: number;
        class_num: number;
        label: string | null;
        school: { name_masked: string } | { name_masked: string }[] | null;
      }>;
};

function toProfile(row: ProfileRow): Profile {
  const cls = one(row.grade_class);
  const school = one(cls?.school);
  const belonging = cls
    ? [school?.name_masked, classLabel(cls.grade, cls.class_num, cls.label)]
        .filter(Boolean)
        .join(" · ")
    : "";

  return {
    id: row.id,
    nickname: row.nickname,
    inviteCode: row.invite_code,
    heartBalance: row.heart_balance,
    friendCount: row.friend_count,
    unlocked: row.service_unlocked_at !== null,
    belonging,
  };
}

/** 온보딩을 마쳤으면 프로필, 아직이면 null. RLS 가 내 행만 돌려준다. */
export async function getMyProfile(): Promise<Profile | null> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("app_user")
    .select(PROFILE_COLUMNS)
    .maybeSingle<ProfileRow>();

  if (error) throw error;
  return data ? toProfile(data) : null;
}

/**
 * 학급 id → 표시명. 친구 목록·요청 목록에서 상대의 소속을 보여주는 데 쓴다.
 * 학급은 마스터 데이터라 누구나 읽을 수 있다(온보딩에서 골라야 하므로).
 */
export async function lookupClassLabels(
  ids: number[],
): Promise<Map<number, string>> {
  const unique = [...new Set(ids)];
  if (unique.length === 0) return new Map();

  const supabase = createClient();
  const { data, error } = await supabase
    .from("grade_class")
    .select("id, grade, class_num, label")
    .in("id", unique);

  if (error) throw error;
  return new Map(
    (data ?? []).map((c) => [c.id, classLabel(c.grade, c.class_num, c.label)]),
  );
}

export async function listSchools(): Promise<School[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("school")
    .select("id, name_masked")
    .order("name_masked");

  if (error) throw error;
  return (data ?? []).map((s) => ({ id: s.id, name: s.name_masked }));
}

export async function listClasses(schoolId: number): Promise<ClassOption[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("grade_class")
    .select("id, grade, class_num, label")
    .eq("school_id", schoolId)
    .order("grade")
    .order("class_num");

  if (error) throw error;
  return (data ?? []).map((c) => ({
    id: c.id,
    label: classLabel(c.grade, c.class_num, c.label),
  }));
}

/**
 * 가입. 초대 코드 발급과 가입 하트 지급은 서버(RPC)가 한 트랜잭션에서 처리한다.
 * 두 번 불려도 계정이 갈라지지 않으므로 중복 클릭을 따로 막지 않아도 된다.
 */
export async function completeOnboarding(
  nickname: string,
  classId: number,
): Promise<Profile> {
  const supabase = createClient();
  const { error } = await supabase.rpc("complete_onboarding", {
    p_nickname: nickname,
    p_class_id: classId,
  });

  if (error) throw new Error(error.message);

  // RPC 는 app_user 행만 돌려준다. 소속 이름까지 붙여서 다시 읽는다.
  const profile = await getMyProfile();
  if (!profile) throw new Error("계정을 만들었지만 다시 읽지 못했습니다");
  return profile;
}
