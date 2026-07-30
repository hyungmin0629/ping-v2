"use client";

import { useCallback, useEffect, useState } from "react";
import {
  bumpView,
  createComment,
  createPost,
  deleteComment,
  deletePost,
  formatWhen,
  getPost,
  listComments,
  listPosts,
  reportContent,
  toggleCommentLike,
  togglePostLike,
  COMMENT_REASONS,
  POST_REASONS,
  type Comment,
  type Post,
} from "@/lib/board";

type View = "list" | "write" | "detail";

const TITLE_MAX = 120;
const BODY_MAX = 5000;
const COMMENT_MAX = 1000;

/**
 * 자유게시판.
 *
 * 주소를 나누지 않고 상태로 갈라진다. 이 프로젝트의 개발 서버가 동적
 * 라우트(`/board/[id]`)를 열지 못하기 때문이다 — 프로덕션에서는 되지만
 * 로컬에서 확인할 수 없는 화면은 만들지 않는다(CLAUDE.md).
 */
export function BoardPanel({ onClose }: { onClose: () => void }) {
  const [view, setView] = useState<View>("list");
  const [posts, setPosts] = useState<Post[]>([]);
  const [current, setCurrent] = useState<Post | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const reloadList = useCallback(
    () =>
      listPosts()
        .then((rows) => {
          setPosts(rows);
          setError("");
        })
        .catch((e) => setError(e instanceof Error ? e.message : String(e)))
        .finally(() => setLoading(false)),
    [],
  );

  useEffect(() => {
    reloadList();
  }, [reloadList]);

  const openPost = useCallback(async (id: number) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await bumpView(id);
      const [post, list] = await Promise.all([getPost(id), listComments(id)]);
      if (!post) {
        setNotice("지워진 글입니다");
        setView("list");
        await reloadList();
        return;
      }
      setCurrent(post);
      setComments(list);
      setView("detail");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [reloadList]);

  async function refreshDetail(id: number) {
    const [post, list] = await Promise.all([getPost(id), listComments(id)]);
    setCurrent(post);
    setComments(list);
  }

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function report(target: "POST" | "COMMENT", id: number, reason: string) {
    await run(async () => {
      const result = await reportContent(target, id, reason);
      setNotice(
        result === "OK"
          ? "신고했습니다. 확인 후 조치됩니다"
          : result === "ALREADY"
            ? "이미 신고한 글입니다"
            : result === "SELF"
              ? "자기 글은 신고할 수 없습니다"
              : "찾을 수 없습니다",
      );
    });
  }

  const header = (
    <div className="mb-6 flex items-center justify-between">
      <h2 className="text-lg font-semibold">자유게시판</h2>
      <button
        type="button"
        onClick={view === "list" ? onClose : () => { setView("list"); setNotice(""); reloadList(); }}
        className="text-sm text-neutral-500 underline underline-offset-4"
      >
        {view === "list" ? "닫기" : "목록"}
      </button>
    </div>
  );

  const messages = (
    <>
      {error && (
        <p className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-xs text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-400">
          {error}
        </p>
      )}
      {notice && (
        <p className="mb-4 rounded border border-neutral-300 p-3 text-xs text-neutral-600 dark:border-neutral-700 dark:text-neutral-400">
          {notice}
        </p>
      )}
    </>
  );

  if (view === "write") {
    return (
      <div>
        {header}
        {messages}
        <WriteForm
          busy={busy}
          onCancel={() => setView("list")}
          onSubmit={(title, body) =>
            run(async () => {
              const id = await createPost(title, body);
              await reloadList();
              await openPost(id);
            })
          }
        />
      </div>
    );
  }

  if (view === "detail" && current) {
    return (
      <div>
        {header}
        {messages}
        <PostDetail
          post={current}
          comments={comments}
          busy={busy}
          onLike={() =>
            run(async () => {
              await togglePostLike(current.id);
              await refreshDetail(current.id);
            })
          }
          onCommentLike={(cid) =>
            run(async () => {
              await toggleCommentLike(cid);
              await refreshDetail(current.id);
            })
          }
          onComment={(body) =>
            run(async () => {
              await createComment(current.id, body);
              await refreshDetail(current.id);
            })
          }
          onDelete={() =>
            run(async () => {
              await deletePost(current.id);
              setNotice("글을 지웠습니다");
              setView("list");
              await reloadList();
            })
          }
          onDeleteComment={(cid) =>
            run(async () => {
              await deleteComment(cid);
              await refreshDetail(current.id);
            })
          }
          onReport={report}
        />
      </div>
    );
  }

  return (
    <div>
      {header}
      {messages}

      <button
        type="button"
        onClick={() => { setView("write"); setNotice(""); }}
        className="mb-6 w-full rounded bg-neutral-900 px-4 py-3 text-sm font-medium text-white dark:bg-neutral-100 dark:text-neutral-900"
      >
        글쓰기
      </button>

      {loading && <p className="font-mono text-sm text-neutral-500">불러오는 중…</p>}

      {!loading && posts.length === 0 && (
        <p className="rounded border border-dashed border-neutral-300 px-4 py-10 text-center text-sm text-neutral-500 dark:border-neutral-700">
          아직 글이 없습니다
          <br />첫 글을 남겨보세요
        </p>
      )}

      <ul className="flex flex-col">
        {posts.map((p) => (
          <li key={p.id} className="border-b border-neutral-200 dark:border-neutral-800">
            <button
              type="button"
              onClick={() => openPost(p.id)}
              className="w-full py-4 text-left"
            >
              <p className="mb-1 font-medium">{p.title}</p>
              <p className="line-clamp-1 text-xs text-neutral-500">{p.body}</p>
              <p className="mt-2 flex gap-3 text-xs text-neutral-500">
                <span>{p.authorNickname}</span>
                <span>{formatWhen(p.createdAt)}</span>
                {p.likeCount > 0 && <span>♥ {p.likeCount}</span>}
                {p.commentCount > 0 && <span>댓글 {p.commentCount}</span>}
              </p>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function WriteForm({
  busy,
  onCancel,
  onSubmit,
}: {
  busy: boolean;
  onCancel: () => void;
  onSubmit: (title: string, body: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const ready = title.trim() !== "" && body.trim() !== "";

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready && !busy) onSubmit(title, body);
      }}
    >
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        maxLength={TITLE_MAX}
        placeholder="제목"
        className="rounded border border-neutral-300 px-3 py-3 text-sm dark:border-neutral-700 dark:bg-neutral-900"
      />
      <div>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          maxLength={BODY_MAX}
          rows={10}
          placeholder="내용"
          className="w-full rounded border border-neutral-300 px-3 py-3 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        />
        <p className="mt-1 text-right text-xs text-neutral-500">
          {body.length} / {BODY_MAX}
        </p>
      </div>

      <p className="text-xs leading-relaxed text-neutral-500">
        글에는 <strong>닉네임이 함께 표시됩니다.</strong> 익명이 아닙니다.
      </p>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 rounded border border-neutral-300 px-4 py-3 text-sm dark:border-neutral-700"
        >
          취소
        </button>
        <button
          type="submit"
          disabled={!ready || busy}
          className="flex-1 rounded bg-neutral-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
        >
          {busy ? "올리는 중…" : "올리기"}
        </button>
      </div>
    </form>
  );
}

function PostDetail({
  post,
  comments,
  busy,
  onLike,
  onCommentLike,
  onComment,
  onDelete,
  onDeleteComment,
  onReport,
}: {
  post: Post;
  comments: Comment[];
  busy: boolean;
  onLike: () => void;
  onCommentLike: (id: number) => void;
  onComment: (body: string) => void;
  onDelete: () => void;
  onDeleteComment: (id: number) => void;
  onReport: (target: "POST" | "COMMENT", id: number, reason: string) => void;
}) {
  const [draft, setDraft] = useState("");
  const [reporting, setReporting] = useState<{ target: "POST" | "COMMENT"; id: number } | null>(
    null,
  );

  const reasons = reporting?.target === "POST" ? POST_REASONS : COMMENT_REASONS;

  return (
    <div className="flex flex-col gap-6">
      <article>
        <h3 className="mb-2 text-base font-semibold">{post.title}</h3>
        <p className="mb-4 flex gap-3 text-xs text-neutral-500">
          <span>{post.authorNickname}</span>
          <span>{formatWhen(post.createdAt)}</span>
          <span>조회 {post.viewCount}</span>
        </p>
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{post.body}</p>
      </article>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={onLike}
          disabled={busy}
          className={`rounded border px-3 py-2 text-xs disabled:opacity-40 ${
            post.likedByMe
              ? "border-neutral-900 font-medium dark:border-neutral-100"
              : "border-neutral-300 dark:border-neutral-700"
          }`}
        >
          ♥ {post.likeCount}
        </button>
        {post.isMine ? (
          <button
            type="button"
            onClick={onDelete}
            disabled={busy}
            className="rounded border border-neutral-300 px-3 py-2 text-xs text-neutral-500 disabled:opacity-40 dark:border-neutral-700"
          >
            삭제
          </button>
        ) : (
          <button
            type="button"
            onClick={() => setReporting({ target: "POST", id: post.id })}
            disabled={busy}
            className="rounded border border-neutral-300 px-3 py-2 text-xs text-neutral-500 disabled:opacity-40 dark:border-neutral-700"
          >
            신고
          </button>
        )}
      </div>

      {reporting && (
        <div className="rounded border border-neutral-300 p-4 dark:border-neutral-700">
          <p className="mb-3 text-xs font-medium">신고 사유를 골라주세요</p>
          <div className="flex flex-col gap-2">
            {reasons.map((r) => (
              <button
                key={r.code}
                type="button"
                disabled={busy}
                onClick={() => {
                  onReport(reporting.target, reporting.id, r.code);
                  setReporting(null);
                }}
                className="rounded border border-neutral-300 px-3 py-2 text-left text-xs disabled:opacity-40 dark:border-neutral-700"
              >
                {r.label}
              </button>
            ))}
            <button
              type="button"
              onClick={() => setReporting(null)}
              className="px-3 py-2 text-left text-xs text-neutral-500"
            >
              취소
            </button>
          </div>
        </div>
      )}

      <hr className="border-neutral-200 dark:border-neutral-800" />

      <section className="flex flex-col gap-4">
        <p className="text-xs font-medium text-neutral-500">댓글 {comments.length}</p>

        {comments.map((c) => (
          <div key={c.id} className="border-b border-neutral-100 pb-3 dark:border-neutral-900">
            <p className="mb-1 flex gap-3 text-xs text-neutral-500">
              <span>{c.authorNickname}</span>
              <span>{formatWhen(c.createdAt)}</span>
            </p>
            <p className="mb-2 text-sm leading-relaxed whitespace-pre-wrap">{c.body}</p>
            <div className="flex gap-3 text-xs text-neutral-500">
              <button
                type="button"
                onClick={() => onCommentLike(c.id)}
                disabled={busy}
                className={c.likedByMe ? "font-medium text-neutral-900 dark:text-neutral-100" : ""}
              >
                ♥ {c.likeCount}
              </button>
              {c.isMine ? (
                <button type="button" onClick={() => onDeleteComment(c.id)} disabled={busy}>
                  삭제
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => setReporting({ target: "COMMENT", id: c.id })}
                  disabled={busy}
                >
                  신고
                </button>
              )}
            </div>
          </div>
        ))}

        <form
          className="flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (draft.trim() && !busy) {
              onComment(draft);
              setDraft("");
            }
          }}
        >
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            maxLength={COMMENT_MAX}
            rows={3}
            placeholder="댓글 남기기"
            className="rounded border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          />
          <button
            type="submit"
            disabled={!draft.trim() || busy}
            className="self-end rounded bg-neutral-900 px-4 py-2 text-xs font-medium text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
          >
            등록
          </button>
        </form>
      </section>
    </div>
  );
}
