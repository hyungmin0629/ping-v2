"use client";

import { useEffect, useState } from "react";
import {
  loadSession,
  shuffleCandidates,
  startVoteSession,
  submitVote,
  SCOPE_LABEL,
  type VoteQuestion,
} from "@/lib/voting";

/** MVP 광고는 스텁이다. 실제 SDK 대신 이만큼 기다린다. */
const AD_SECONDS = 3;

type Phase = "loading" | "voting" | "ad" | "done" | "error";

export function VotePanel({ onClose }: { onClose: () => void }) {
  const [items, setItems] = useState<VoteQuestion[]>([]);
  const [phase, setPhase] = useState<Phase>("loading");
  const [earned, setEarned] = useState(0);
  const [flash, setFlash] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    startVoteSession()
      .then((rows) => {
        if (cancelled) return;
        setItems(rows);
        setPhase(rows.every((i) => i.voted) ? "done" : "voting");
      })
      .catch((e) => {
        if (cancelled) return;
        setMessage(e instanceof Error ? e.message : String(e));
        setPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const current = items.find((i) => !i.voted);
  const answered = items.filter((i) => i.voted).length;

  async function choose(userId: number) {
    if (!current || busy) return;
    setBusy(true);
    try {
      const reward = await submitVote(current.itemId, userId);
      setEarned((h) => h + reward);
      setFlash(`+${reward}`);
      setTimeout(() => setFlash(""), 1200);

      const rest = items.map((i) =>
        i.itemId === current.itemId ? { ...i, voted: true } : i,
      );
      setItems(rest);
      if (rest.every((i) => i.voted)) setPhase("done");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function watchAdAndShuffle() {
    if (!current || busy) return;
    setPhase("ad");
    setBusy(true);
    try {
      await new Promise((r) => setTimeout(r, AD_SECONDS * 1000));
      await shuffleCandidates(current.itemId);
      // 새 후보를 받아오려면 다시 읽어야 한다. 세션 id 는 문항이 알고 있다.
      setItems(await reloadFrom(current.itemId, items));
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      setPhase("voting");
    }
  }

  if (phase === "loading") {
    return <p className="font-mono text-sm text-neutral-500">문제를 뽑는 중…</p>;
  }

  if (phase === "error") {
    return (
      <div className="flex flex-col gap-4">
        <p className="rounded border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {message}
        </p>
        <BackButton onClick={onClose} />
      </div>
    );
  }

  if (phase === "done" || !current) {
    return (
      <div className="flex flex-col gap-6 text-center">
        <p className="text-sm text-neutral-500">오늘의 투표 끝</p>
        <p className="text-4xl font-semibold tracking-tight">+{earned}</p>
        <p className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
          하트를 받았습니다. 나를 뽑은 사람이 누구인지는 &lsquo;받은 투표&rsquo;에서
          확인할 수 있습니다(준비 중).
        </p>
        <BackButton onClick={onClose} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex items-baseline justify-between">
        <p className="font-mono text-xs tracking-widest text-neutral-500">
          {answered + 1} / {items.length}
        </p>
        <span className="text-xs text-neutral-500">
          {flash ? (
            <span className="font-medium text-neutral-900 dark:text-neutral-100">
              {flash}
            </span>
          ) : (
            `하트 ${earned}`
          )}
        </span>
      </header>

      <div className="flex flex-col gap-2">
        <p className="text-xs text-neutral-500">{SCOPE_LABEL[current.scope]}</p>
        <h2 className="text-2xl leading-snug font-semibold text-balance">
          {current.text}
        </h2>
        {/*
          범위 안 친구가 4명이 안 되면 다른 친구로 채운다. 그 사실을 숨기면
          "우리 반에서" 라고 해놓고 다른 반 친구가 나와 이상하게 보인다.
        */}
        {current.paddedCount > 0 && (
          <p className="text-xs leading-relaxed text-neutral-500">
            이 범위의 친구가 모자라 다른 친구 {current.paddedCount}명이 후보에
            들어갔습니다.
          </p>
        )}
      </div>

      {phase === "ad" ? (
        <p className="rounded border border-neutral-200 px-4 py-10 text-center text-sm text-neutral-500 dark:border-neutral-800">
          광고 보는 중… ({AD_SECONDS}초)
        </p>
      ) : (
        <ul className="grid grid-cols-2 gap-3">
          {current.candidates.map((c) => (
            <li key={c.userId}>
              <button
                type="button"
                disabled={busy}
                onClick={() => choose(c.userId)}
                className="w-full rounded border border-neutral-300 px-4 py-6 text-center font-medium transition-colors hover:border-neutral-900 disabled:opacity-40 dark:border-neutral-700 dark:hover:border-neutral-100"
              >
                {c.nickname}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex items-center justify-between">
        {current.shuffled ? (
          <span className="text-xs text-neutral-500">셔플은 문항당 한 번뿐입니다</span>
        ) : (
          <button
            type="button"
            onClick={watchAdAndShuffle}
            disabled={busy}
            className="rounded border border-neutral-300 px-3 py-1.5 text-xs disabled:opacity-40 dark:border-neutral-700"
          >
            다른 사람 보기 (광고)
          </button>
        )}
        <button
          type="button"
          onClick={onClose}
          className="text-xs text-neutral-500 underline underline-offset-4"
        >
          나중에
        </button>
      </div>

      {message && (
        <p className="font-mono text-xs break-all text-red-700 dark:text-red-400">
          {message}
        </p>
      )}
    </div>
  );
}

/** 셔플 후 새 후보를 받아온다. 진행 중 세션이 하나뿐이라 다시 열면 그대로 온다. */
async function reloadFrom(itemId: number, current: VoteQuestion[]) {
  const sessionId = await sessionIdOf(itemId);
  return sessionId ? loadSession(sessionId) : current;
}

async function sessionIdOf(itemId: number): Promise<number | null> {
  const { createClient } = await import("@/lib/supabase/client");
  const { data } = await createClient()
    .from("vote_item")
    .select("session_id")
    .eq("id", itemId)
    .maybeSingle();
  return data?.session_id ?? null;
}

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded bg-neutral-900 px-4 py-3 font-medium text-white dark:bg-neutral-100 dark:text-neutral-900"
    >
      내 화면으로
    </button>
  );
}
