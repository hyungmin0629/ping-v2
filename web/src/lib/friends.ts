import { createClient } from "./supabase/client";
import { lookupClassLabels } from "./profile";

/**
 * 친구 맺기.
 *
 * 상대를 지목하는 수단은 초대 코드뿐이다. 브라우저에는 friend_request 와
 * friendship 의 쓰기 권한이 없다 — 열어두면 id 를 1,2,3… 으로 바꿔가며
 * 전체 가입자에게 요청을 뿌릴 수 있다. (db/rls/friends.sql)
 */

export type SendResult =
  | "SENT"
  | "ACCEPTED"
  | "ALREADY_FRIEND"
  | "ALREADY_SENT"
  | "SELF"
  | "NOT_FOUND";

/** 서버가 돌려준 결과를 화면에 쓸 말로 옮긴다. 전부 오류가 아니라 안내다. */
export const SEND_MESSAGE: Record<SendResult, string> = {
  SENT: "요청을 보냈습니다. 상대가 수락하면 친구가 됩니다.",
  ACCEPTED: "친구가 되었습니다. 상대도 내 코드를 입력해 둔 상태였어요.",
  ALREADY_FRIEND: "이미 친구입니다.",
  ALREADY_SENT: "이미 보낸 요청입니다. 상대의 수락을 기다리는 중이에요.",
  SELF: "내 초대 코드예요. 친구에게 보낼 코드를 입력해 주세요.",
  NOT_FOUND: "그런 초대 코드가 없어요. 다시 확인해 주세요.",
};

export type Person = {
  /** 요청 목록에서는 요청 id, 친구 목록에서는 유저 id */
  id: number;
  nickname: string;
  belonging: string;
};

/**
 * 입력에서 초대 코드를 뽑아낸다.
 *
 * 주소가 섞여 들어와도 마지막 경로 조각(= 코드)만 취한다. 코드를 주고받는
 * 통로가 카톡이라 링크나 군더더기가 딸려오기 쉽다. 초대 링크 자체는
 * 배포 후(W7)로 미뤘지만, 입력을 관대하게 받는 것은 그대로 둔다.
 *
 *   "6RSH96F8"                           → "6RSH96F8"
 *   "코드: 6rsh96f8"                      → "6RSH96F8"
 *   "https://…/add/6rsh96f8"             → "6RSH96F8"
 */
export function normalizeCode(raw: string) {
  const text = raw.trim().replace(/\s+/g, "");
  const lastSegment =
    text.split(/[?#]/)[0].replace(/\/+$/, "").split("/").pop() ?? "";
  // 코드에 쓰이는 글자만 남긴다. 헷갈리는 0·O·1·I·L 은 애초에 코드에
  // 들어가지 않으므로(ck_invite_code), 섞여 들어오면 잘못 읽은 것이다.
  return lastSegment
    .toUpperCase()
    .replace(/[^A-HJ-NP-Z2-9]/g, "")
    .slice(0, 8);
}

export async function sendFriendRequest(code: string): Promise<SendResult> {
  const supabase = createClient();
  const { data, error } = await supabase.rpc("send_friend_request", {
    p_code: normalizeCode(code),
  });

  if (error) throw new Error(error.message);
  return data as SendResult;
}

/** 아직 응답하지 않은, 내가 받은 요청. */
export async function listIncomingRequests(): Promise<Person[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("my_friend_request")
    .select("id, counterpart_nickname, counterpart_class_id, created_at")
    .eq("direction", "INCOMING")
    .eq("status", "PENDING")
    .order("created_at", { ascending: false });

  if (error) throw error;

  const rows = data ?? [];
  const labels = await lookupClassLabels(rows.map((r) => r.counterpart_class_id));
  return rows.map((r) => ({
    id: r.id,
    nickname: r.counterpart_nickname,
    belonging: labels.get(r.counterpart_class_id) ?? "",
  }));
}

export async function respondToRequest(requestId: number, accept: boolean) {
  const supabase = createClient();
  const fn = accept ? "accept_friend_request" : "reject_friend_request";
  const { error } = await supabase.rpc(fn, { p_request_id: requestId });
  if (error) throw new Error(error.message);
}

/**
 * 내 친구 목록.
 *
 * friend_profile 뷰에는 나 자신도 들어 있고(뷰 정의상 그렇다) 하트 잔액은
 * 빠져 있다 — 친구의 잔액까지 보여줄 이유가 없기 때문이다.
 */
export async function listFriends(myId: number): Promise<Person[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("friend_profile")
    .select("id, nickname, class_id, status")
    .eq("status", "ACTIVE");

  if (error) throw error;

  const rows = (data ?? []).filter((r) => r.id !== myId);
  const labels = await lookupClassLabels(rows.map((r) => r.class_id));
  return rows
    .map((r) => ({
      id: r.id,
      nickname: r.nickname,
      belonging: labels.get(r.class_id) ?? "",
    }))
    .sort((a, b) => a.nickname.localeCompare(b.nickname, "ko"));
}
