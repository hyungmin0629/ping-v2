import { createClient } from "./supabase/client";

/**
 * 자유게시판 (W9).
 *
 * 익명 게시판이 아니다. 글쓴이 닉네임이 드러난다 — 익명을 뺐던 이유가
 * "사고가 나도 책임을 물을 수 없다"였고, 글쓴이가 붙으면 그 전제가 바뀐다.
 *
 * 범위는 같은 학교다. 그 판단은 화면이 아니라 DB 가 한다(db/rls/board.sql) —
 * 읽기는 board_post·board_comment 뷰로만, 쓰기는 RPC 로만 열려 있다.
 * 여기서 school_id 나 author_id 를 보내지 않는 것은 보낼 수 없기 때문이다.
 */

export type Post = {
  id: number;
  title: string;
  body: string;
  authorNickname: string;
  isMine: boolean;
  likeCount: number;
  commentCount: number;
  viewCount: number;
  likedByMe: boolean;
  createdAt: string;
};

export type Comment = {
  id: number;
  body: string;
  authorNickname: string;
  isMine: boolean;
  likeCount: number;
  likedByMe: boolean;
  createdAt: string;
};

type PostRow = {
  id: number;
  title: string;
  body: string;
  author_nickname: string;
  is_mine: boolean;
  like_count: number;
  comment_count: number;
  view_count: number;
  liked_by_me: boolean;
  created_at: string;
};

type CommentRow = {
  id: number;
  body: string;
  author_nickname: string;
  is_mine: boolean;
  like_count: number;
  liked_by_me: boolean;
  created_at: string;
};

const POST_COLUMNS =
  "id, title, body, author_nickname, is_mine, like_count, comment_count, view_count, liked_by_me, created_at";

function toPost(r: PostRow): Post {
  return {
    id: r.id,
    title: r.title,
    body: r.body,
    authorNickname: r.author_nickname,
    isMine: r.is_mine,
    likeCount: r.like_count,
    commentCount: r.comment_count,
    viewCount: r.view_count,
    likedByMe: r.liked_by_me,
    createdAt: r.created_at,
  };
}

/** 최신 글부터. 클로즈드 테스트 규모라 페이지를 나누지 않는다. */
export async function listPosts(limit = 50): Promise<Post[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("board_post")
    .select(POST_COLUMNS)
    .order("created_at", { ascending: false })
    .limit(limit)
    .returns<PostRow[]>();

  if (error) throw error;
  return (data ?? []).map(toPost);
}

export async function getPost(id: number): Promise<Post | null> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("board_post")
    .select(POST_COLUMNS)
    .eq("id", id)
    .maybeSingle<PostRow>();

  if (error) throw error;
  return data ? toPost(data) : null;
}

export async function listComments(postId: number): Promise<Comment[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("board_comment")
    .select("id, body, author_nickname, is_mine, like_count, liked_by_me, created_at")
    .eq("post_id", postId)
    .order("created_at")
    .returns<CommentRow[]>();

  if (error) throw error;
  return (data ?? []).map((r) => ({
    id: r.id,
    body: r.body,
    authorNickname: r.author_nickname,
    isMine: r.is_mine,
    likeCount: r.like_count,
    likedByMe: r.liked_by_me,
    createdAt: r.created_at,
  }));
}

export async function createPost(title: string, body: string): Promise<number> {
  const supabase = createClient();
  const { data, error } = await supabase.rpc("create_post", {
    p_title: title,
    p_body: body,
  });
  if (error) throw error;
  return data as number;
}

export async function createComment(postId: number, body: string): Promise<void> {
  const supabase = createClient();
  const { error } = await supabase.rpc("create_comment", {
    p_post_id: postId,
    p_body: body,
  });
  if (error) throw error;
}

export async function togglePostLike(postId: number): Promise<boolean> {
  const supabase = createClient();
  const { data, error } = await supabase.rpc("toggle_post_like", { p_post_id: postId });
  if (error) throw error;
  return data as boolean;
}

export async function toggleCommentLike(commentId: number): Promise<boolean> {
  const supabase = createClient();
  const { data, error } = await supabase.rpc("toggle_comment_like", {
    p_comment_id: commentId,
  });
  if (error) throw error;
  return data as boolean;
}

export async function deletePost(postId: number): Promise<void> {
  const supabase = createClient();
  const { error } = await supabase.rpc("delete_own_post", { p_post_id: postId });
  if (error) throw error;
}

export async function deleteComment(commentId: number): Promise<void> {
  const supabase = createClient();
  const { error } = await supabase.rpc("delete_own_comment", { p_comment_id: commentId });
  if (error) throw error;
}

/** 조회수. 실패해도 화면을 막지 않는다 — 없어도 읽는 데 지장이 없다. */
export async function bumpView(postId: number): Promise<void> {
  try {
    const supabase = createClient();
    await supabase.rpc("bump_post_view", { p_post_id: postId });
  } catch {
    /* 무시 */
  }
}

// 신고 -----------------------------------------------------------------
// 사유 코드는 report_reason 테이블의 것과 같아야 한다. RPC 가 대상 종류와
// 사유가 맞는지 확인하므로, 여기서 잘못 보내면 오류로 돌아온다.
export const POST_REASONS = [
  { code: "P_ABUSE", label: "욕설·비방" },
  { code: "P_SEXUAL", label: "선정적 내용" },
  { code: "P_SPAM", label: "스팸·광고" },
] as const;

export const COMMENT_REASONS = [
  { code: "C_ABUSE", label: "욕설·비방" },
  { code: "C_SPAM", label: "스팸·광고" },
] as const;

export type ReportResult = "OK" | "ALREADY" | "SELF" | "NOT_FOUND";

export async function reportContent(
  target: "POST" | "COMMENT",
  targetId: number,
  reasonCode: string,
): Promise<ReportResult> {
  const supabase = createClient();
  const { data, error } = await supabase.rpc("report_content", {
    p_target: target,
    p_target_id: targetId,
    p_reason_code: reasonCode,
  });
  if (error) throw error;
  return data as ReportResult;
}

/** 오늘이면 시각, 아니면 날짜. 목록에서 최신 글을 가늠하기 좋다. */
export function formatWhen(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();

  return sameDay
    ? d.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("ko-KR", { month: "long", day: "numeric" });
}
