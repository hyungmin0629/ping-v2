import { createClient } from "./supabase/client";
import { lookupClassLabels, GENDER_LABEL, type Gender } from "./profile";
import type { Scope } from "./voting";

/**
 * 받은 투표와 내가 한 투표.
 *
 * "누가 나를 뽑았는가"는 이 서비스가 하트를 받고 파는 정보다. 그래서
 * vote_received 테이블은 직접 읽을 수 없고, 산 힌트만큼만 열어주는
 * my_vote_received 뷰로만 나온다. (db/rls/received.sql)
 */

/** 누진 요금. 구 서비스 실측값 그대로다. */
export const HINT_COSTS = [200, 300, 500, 1000];
export const HINT_LABELS = [
  "초성 보기",
  "성별 보기",
  "어느 반인지 보기",
  "누구인지 보기",
];

export type ReceivedVote = {
  id: number;
  questionText: string;
  createdAt: string;
  isRead: boolean;
  /** 지금까지 산 힌트 단계 (0~4) */
  hintSteps: number;
  voterInitial: string | null;
  voterGenderLabel: string | null;
  voterClassLabel: string | null;
  voterNickname: string | null;
  answerStatus: "NONE" | "PUBLIC" | "PRIVATE";
};

export type MyVote = {
  itemId: number;
  questionText: string;
  chosenNickname: string;
  votedAt: string;
  scope: Scope;
};

export async function listReceived(): Promise<ReceivedVote[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("my_vote_received")
    // 문자열을 이어붙이면 supabase-js 가 컬럼 타입을 못 읽는다. 한 줄로 둔다.
    .select("id, question_id, created_at, is_read, hint_steps, voter_initial, voter_gender, voter_class_id, voter_nickname, answer_status")
    .order("created_at", { ascending: false });
  if (error) throw error;

  const rows = data ?? [];
  const [questions, labels] = await Promise.all([
    supabase.from("question").select("id, text").in("id", rows.map((r) => r.question_id)),
    lookupClassLabels(
      rows.map((r) => r.voter_class_id).filter((v): v is number => v !== null),
    ),
  ]);
  if (questions.error) throw questions.error;
  const textOf = new Map((questions.data ?? []).map((q) => [q.id, q.text]));

  return rows.map((r) => ({
    id: r.id,
    questionText: textOf.get(r.question_id) ?? "",
    createdAt: r.created_at,
    isRead: r.is_read,
    hintSteps: r.hint_steps,
    voterInitial: r.voter_initial,
    voterGenderLabel: r.voter_gender
      ? GENDER_LABEL[r.voter_gender as Gender]
      : null,
    voterClassLabel: r.voter_class_id ? (labels.get(r.voter_class_id) ?? null) : null,
    voterNickname: r.voter_nickname,
    answerStatus: r.answer_status,
  }));
}

/** 목록을 연 시점이 곧 열람 시점이다. 실패해도 화면을 막지 않는다. */
export async function markRead(ids: number[]): Promise<void> {
  const supabase = createClient();
  await Promise.all(
    ids.map((id) => supabase.rpc("mark_received_read", { p_received_id: id })),
  );
}

/** 돌려주는 값은 이번에 산 단계(1~3). 하트가 모자라면 예외가 난다. */
export async function buyHint(receivedId: number): Promise<number> {
  const supabase = createClient();
  const { data, error } = await supabase.rpc("buy_hint", { p_received_id: receivedId });
  if (error) throw new Error(error.message);
  return data as number;
}

export async function listMyVotes(): Promise<MyVote[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("my_vote_history")
    .select("vote_item_id, question_text, chosen_nickname, voted_at, candidate_scope")
    .order("voted_at", { ascending: false });
  if (error) throw error;

  return (data ?? []).map((r) => ({
    itemId: r.vote_item_id,
    questionText: r.question_text,
    chosenNickname: r.chosen_nickname,
    votedAt: r.voted_at,
    scope: r.candidate_scope as Scope,
  }));
}

export function formatDay(iso: string) {
  return new Date(iso).toLocaleDateString("ko-KR", {
    month: "long",
    day: "numeric",
  });
}
