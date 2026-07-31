import { createClient } from "./supabase/client";

/**
 * 받은 투표와 힌트 (W14).
 *
 * "누가 나를 뽑았는가"는 이 서비스가 하트를 받고 파는 정보다. 그래서
 * vote_received 는 직접 읽을 수 없고, 산 힌트만큼만 열어주는
 * my_vote_received 뷰로만 나온다.
 *
 * 힌트는 순차 4단계에서 **골라 사는 5+1** 로 바뀌었다(W14).
 * 기본 5종은 각 20하트이고 순서가 없다. 이름 공개는 100하트이며
 * **기본 5종 중 3개 이상**을 연 뒤에만 살 수 있다.
 *
 * 자모 힌트(초·중·종성)는 **각자 다른 글자**를 연다. 어느 글자를 여는지,
 * 무엇이 보이는지는 전부 DB 가 정한다 — 화면에서 계산하면 아직 안 산 자모가
 * 브라우저로 나가고, 보낸 뒤 숨기는 것은 가린 것이 아니다. (db/rls/hints.sql)
 */

export type HintKind = "GENDER" | "INITIAL" | "MEDIAL" | "FINAL" | "CLASS";

export const HINT_COST = 20;
export const NAME_COST = 100;
export const UNLOCK_MIN = 3;
export const AD_SECONDS = 30;

export const HINT_LABEL: Record<HintKind, string> = {
  GENDER: "성별",
  INITIAL: "글자 하나의 초성",
  MEDIAL: "글자 하나의 중성",
  FINAL: "글자 하나의 종성",
  CLASS: "어느 반인지",
};

/** 성별을 앞에 두는 것은 광고로도 열 수 있어서다. */
export const HINT_ORDER: HintKind[] = ["GENDER", "INITIAL", "MEDIAL", "FINAL", "CLASS"];

export const GENDER_TEXT: Record<string, string> = { F: "여자", M: "남자", X: "밝히지 않음" };

export type ReceivedVote = {
  id: number;
  question: string;
  isRead: boolean;
  createdAt: string;
  /** 이름 글자 수. 아직 아무것도 못 산 자리를 ○ 로 그리는 데 쓴다 */
  nameLength: number;
  basicCount: number;
  canUnlockName: boolean;
  hasName: boolean;
  bought: Record<HintKind, boolean>;
  gender: string | null;
  grade: number | null;
  classNum: number | null;
  nickname: string | null;
  leadHint: string | null;
  vowelHint: string | null;
  tailHint: string | null;
};

export type MyVote = {
  id: number;
  question: string;
  chosenNickname: string;
  votedAt: string;
};

const COLUMNS = `
  id, question_text, is_read, created_at, name_length,
  basic_count, can_unlock_name,
  has_gender, has_lead, has_vowel, has_tail, has_class, has_name,
  voter_gender, voter_grade, voter_class_num, voter_nickname,
  lead_hint, vowel_hint, tail_hint
`;

type Row = {
  id: number;
  question_text: string;
  is_read: boolean;
  created_at: string;
  name_length: number;
  basic_count: number;
  can_unlock_name: boolean;
  has_gender: boolean;
  has_lead: boolean;
  has_vowel: boolean;
  has_tail: boolean;
  has_class: boolean;
  has_name: boolean;
  voter_gender: string | null;
  voter_grade: number | null;
  voter_class_num: number | null;
  voter_nickname: string | null;
  lead_hint: string | null;
  vowel_hint: string | null;
  tail_hint: string | null;
};

function toVote(r: Row): ReceivedVote {
  return {
    id: r.id,
    question: r.question_text,
    isRead: r.is_read,
    createdAt: r.created_at,
    nameLength: r.name_length,
    basicCount: r.basic_count,
    canUnlockName: r.can_unlock_name,
    hasName: r.has_name,
    bought: {
      GENDER: r.has_gender,
      INITIAL: r.has_lead,
      MEDIAL: r.has_vowel,
      FINAL: r.has_tail,
      CLASS: r.has_class,
    },
    gender: r.voter_gender,
    grade: r.voter_grade,
    classNum: r.voter_class_num,
    nickname: r.voter_nickname,
    leadHint: r.lead_hint,
    vowelHint: r.vowel_hint,
    tailHint: r.tail_hint,
  };
}

export async function listReceived(): Promise<ReceivedVote[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("my_vote_received")
    .select(COLUMNS)
    .order("created_at", { ascending: false })
    .returns<Row[]>();

  if (error) throw error;
  return (data ?? []).map(toVote);
}

export async function getReceived(id: number): Promise<ReceivedVote | null> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("my_vote_received")
    .select(COLUMNS)
    .eq("id", id)
    .maybeSingle<Row>();

  if (error) throw error;
  return data ? toVote(data) : null;
}

export async function markRead(ids: number[]): Promise<void> {
  if (ids.length === 0) return;
  const supabase = createClient();
  await Promise.all(
    ids.map((id) => supabase.rpc("mark_received_read", { p_received_id: id })),
  );
}

export type BuyResult =
  | "OK" | "ALREADY" | "NEED_MORE" | "NOT_ENOUGH" | "NOT_FOUND"
  | "AD_INVALID" | "AD_USED_TODAY" | "AD_NOT_ALLOWED";

export const BUY_MESSAGE: Record<BuyResult, string> = {
  OK: "",
  ALREADY: "이미 연 힌트입니다.",
  NEED_MORE: `기본 힌트를 ${UNLOCK_MIN}개 이상 열어야 이름을 볼 수 있어요.`,
  NOT_ENOUGH: "하트가 모자랍니다.",
  NOT_FOUND: "찾을 수 없는 투표입니다.",
  AD_INVALID: "광고를 끝까지 보지 않았어요.",
  AD_USED_TODAY: "오늘 광고로 여는 것은 이미 썼습니다. 내일 다시 열려요.",
  AD_NOT_ALLOWED: "이 힌트는 광고로 열 수 없습니다.",
};

export async function buyHint(
  receivedId: number,
  kind: HintKind | "FULL_NAME",
  adImpressionId?: number,
): Promise<BuyResult> {
  const supabase = createClient();
  const { data, error } = await supabase.rpc("buy_hint", {
    p_received_id: receivedId,
    p_hint_type: kind,
    p_ad_impression_id: adImpressionId ?? null,
  });
  if (error) throw new Error(error.message);
  return data as BuyResult;
}

// 광고 -----------------------------------------------------------------
// MVP 의 광고는 스텁이다(30초 대기). 그래도 기록은 진짜로 남긴다 —
// "광고를 보고 여는 사람이 얼마나 되나"가 이 기능을 넣은 이유이기 때문이다.

export async function startAd(): Promise<number> {
  const supabase = createClient();
  const { data, error } = await supabase.rpc("start_hint_ad");
  if (error) throw new Error(error.message);
  return data as number;
}

export async function completeAd(adId: number): Promise<void> {
  const supabase = createClient();
  const { error } = await supabase.rpc("complete_hint_ad", { p_ad_id: adId });
  if (error) throw new Error(error.message);
}

export async function adAvailable(): Promise<boolean> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("my_hint_ad_state")
    .select("ad_available")
    .maybeSingle();
  if (error) throw new Error(error.message);
  return data?.ad_available ?? false;
}

// 내가 한 투표 ---------------------------------------------------------
export async function listMyVotes(): Promise<MyVote[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("my_vote_history")
    .select("vote_item_id, question_text, chosen_nickname, voted_at")
    .order("voted_at", { ascending: false });

  if (error) throw error;
  return (data ?? []).map((r) => ({
    id: r.vote_item_id,
    question: r.question_text,
    chosenNickname: r.chosen_nickname,
    votedAt: r.voted_at,
  }));
}

export function formatDay(iso: string) {
  return new Date(iso).toLocaleDateString("ko-KR", { month: "long", day: "numeric" });
}

/** 아직 아무 자모도 못 산 자리표시 — ○○○ */
export function blankName(length: number) {
  return "○".repeat(Math.max(length, 1));
}
