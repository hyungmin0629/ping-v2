import { createClient } from "./supabase/client";

/**
 * 투표.
 *
 * 세션·후보·하트는 전부 서버가 정한다. 브라우저에는 vote_* 테이블의 쓰기
 * 권한이 없다 — 후보를 직접 넣을 수 있으면 아무나 지목할 수 있고,
 * 하트 원장을 쓸 수 있으면 무한정 만들 수 있다. (db/rls/voting.sql)
 */

export type Scope = "CLASS" | "SCHOOL" | "GLOBAL";

/** 실제로 후보를 뽑은 범위. 요청한 스코프보다 낮아졌을 수 있다. */
export const SCOPE_LABEL: Record<Scope, string> = {
  CLASS: "우리 반에서",
  SCHOOL: "우리 학교에서",
  GLOBAL: "친구 전체에서",
};

export type Candidate = { userId: number; nickname: string };

export type VoteQuestion = {
  itemId: number;
  position: number;
  text: string;
  scope: Scope;
  /** 셔플을 이미 썼는가 (문항당 1회) */
  shuffled: boolean;
  /** 스코프 밖 친구로 채운 후보 수. 0 이면 전부 그 범위 안에서 뽑혔다 */
  paddedCount: number;
  voted: boolean;
  candidates: Candidate[];
};

export async function startVoteSession(): Promise<VoteQuestion[]> {
  const supabase = createClient();
  const { data, error } = await supabase.rpc("start_vote_session");
  if (error) throw new Error(error.message);
  return loadSession(data as number);
}

/** 세션의 문항과 현재 라운드 후보를 모아 온다. 읽기는 전부 RLS 가 거른다. */
export async function loadSession(sessionId: number): Promise<VoteQuestion[]> {
  const supabase = createClient();

  const { data: items, error: itemErr } = await supabase
    .from("vote_item")
    .select("id, position, question_id, candidate_scope, shuffle_count, voted_at, padded_count")
    .eq("session_id", sessionId)
    .order("position");
  if (itemErr) throw itemErr;
  if (!items?.length) return [];

  const [questions, candidates] = await Promise.all([
    supabase.from("question").select("id, text").in("id", items.map((i) => i.question_id)),
    supabase
      .from("vote_candidate")
      .select("vote_item_id, candidate_user_id, shuffle_round, slot")
      .in("vote_item_id", items.map((i) => i.id)),
  ]);
  if (questions.error) throw questions.error;
  if (candidates.error) throw candidates.error;

  const rows = candidates.data ?? [];
  // 후보는 언제나 내 친구다. 닉네임은 friend_profile 로만 나온다
  // (app_user 를 직접 읽으면 하트 잔액까지 보이므로 열지 않았다).
  const { data: people, error: peopleErr } = await supabase
    .from("friend_profile")
    .select("id, nickname")
    .in("id", [...new Set(rows.map((c) => c.candidate_user_id))]);
  if (peopleErr) throw peopleErr;

  const nameOf = new Map((people ?? []).map((p) => [p.id, p.nickname]));
  const textOf = new Map((questions.data ?? []).map((q) => [q.id, q.text]));

  return items.map((item) => ({
    itemId: item.id,
    position: item.position,
    text: textOf.get(item.question_id) ?? "",
    scope: item.candidate_scope as Scope,
    shuffled: item.shuffle_count > 0,
    paddedCount: item.padded_count ?? 0,
    voted: item.voted_at !== null,
    candidates: rows
      // 셔플했다면 새 라운드의 후보만 보여준다. 이전 라운드는 분석용으로 남는다.
      .filter((c) => c.vote_item_id === item.id && c.shuffle_round === item.shuffle_count)
      .sort((a, b) => a.slot - b.slot)
      .map((c) => ({
        userId: c.candidate_user_id,
        nickname: nameOf.get(c.candidate_user_id) ?? "알 수 없음",
      })),
  }));
}

/** 돌려주는 값은 내가 받은 하트다. */
export async function submitVote(itemId: number, candidateUserId: number): Promise<number> {
  const supabase = createClient();
  const { data, error } = await supabase.rpc("submit_vote", {
    p_item_id: itemId,
    p_candidate_user_id: candidateUserId,
  });
  if (error) throw new Error(error.message);
  return data as number;
}

export async function shuffleCandidates(itemId: number): Promise<void> {
  const supabase = createClient();
  const { error } = await supabase.rpc("shuffle_candidates", { p_item_id: itemId });
  if (error) throw new Error(error.message);
}
