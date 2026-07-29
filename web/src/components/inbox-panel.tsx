"use client";

import { useCallback, useEffect, useState } from "react";
import {
  buyHint,
  formatDay,
  listMyVotes,
  listReceived,
  markRead,
  HINT_COSTS,
  HINT_LABELS,
  type MyVote,
  type ReceivedVote,
} from "@/lib/received";
import { SCOPE_LABEL } from "@/lib/voting";

type Tab = "received" | "sent";

/**
 * 받은 투표 / 내가 한 투표.
 *
 * 받은 쪽은 힌트를 사야 하나씩 열린다. 보낸 쪽은 내 기록이라 그냥 보인다
 * — 가려야 하는 것은 "누가 나를 뽑았나"이지 "내가 누구를 뽑았나"가 아니다.
 */
export function InboxPanel({
  hearts,
  onClose,
  onChanged,
}: {
  hearts: number;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [tab, setTab] = useState<Tab>("received");
  const [received, setReceived] = useState<ReceivedVote[]>([]);
  const [sent, setSent] = useState<MyVote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);

  const reload = useCallback(
    () =>
      Promise.all([listReceived(), listMyVotes()])
        .then(([inbox, mine]) => {
          setReceived(inbox);
          setSent(mine);
          setError("");
          // 목록을 연 시점이 곧 열람 시점이다.
          const unread = inbox.filter((r) => !r.isRead).map((r) => r.id);
          if (unread.length) markRead(unread);
        })
        .catch((e) => setError(e instanceof Error ? e.message : String(e)))
        .finally(() => setLoading(false)),
    [],
  );

  useEffect(() => {
    reload();
  }, [reload]);

  async function hint(item: ReceivedVote) {
    setBusy(item.id);
    setError("");
    try {
      await buyHint(item.id);
      await reload();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-center justify-between">
        <div className="flex gap-1 text-sm">
          <TabButton active={tab === "received"} onClick={() => setTab("received")}>
            받은 투표 {received.length > 0 && received.length}
          </TabButton>
          <TabButton active={tab === "sent"} onClick={() => setTab("sent")}>
            내가 한 투표
          </TabButton>
        </div>
        <span className="text-xs text-neutral-500">하트 {hearts}</span>
      </header>

      {loading && <p className="font-mono text-sm text-neutral-500">불러오는 중…</p>}

      {!loading && tab === "received" && (
        <ul className="flex flex-col gap-3">
          {received.length === 0 && (
            <li className="text-sm leading-relaxed text-neutral-500">
              아직 받은 투표가 없습니다. 친구들이 투표하면 여기에 쌓입니다.
            </li>
          )}
          {received.map((r) => (
            <li
              key={r.id}
              className="flex flex-col gap-3 rounded border border-neutral-200 p-4 dark:border-neutral-800"
            >
              <div className="flex items-baseline justify-between gap-3">
                <p className="font-medium text-balance">{r.questionText}</p>
                <span className="shrink-0 text-xs text-neutral-500">
                  {formatDay(r.createdAt)}
                </span>
              </div>

              <p className="text-sm text-neutral-600 dark:text-neutral-400">
                {r.voterNickname ? (
                  <>
                    <span className="font-medium text-neutral-900 dark:text-neutral-100">
                      {r.voterNickname}
                    </span>
                    님이 나를 뽑았습니다
                  </>
                ) : (
                  <>
                    {r.voterInitial ? `${r.voterInitial}…` : "???"}
                    {[r.voterGenderLabel, r.voterClassLabel]
                      .filter(Boolean)
                      .map((v) => ` · ${v}`)
                      .join("")}
                    <span className="text-neutral-500"> 이 나를 뽑았습니다</span>
                  </>
                )}
              </p>

              {r.hintSteps < HINT_COSTS.length && (
                <button
                  type="button"
                  disabled={busy === r.id}
                  onClick={() => hint(r)}
                  className="self-start rounded border border-neutral-300 px-3 py-1.5 text-xs disabled:opacity-40 dark:border-neutral-700"
                >
                  {busy === r.id
                    ? "구매 중…"
                    : `${HINT_LABELS[r.hintSteps]} · 하트 ${HINT_COSTS[r.hintSteps]}`}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {!loading && tab === "sent" && (
        <ul className="flex flex-col gap-3">
          {sent.length === 0 && (
            <li className="text-sm leading-relaxed text-neutral-500">
              아직 한 투표가 없습니다.
            </li>
          )}
          {sent.map((v) => (
            <li
              key={v.itemId}
              className="flex flex-col gap-1 rounded border border-neutral-200 p-4 dark:border-neutral-800"
            >
              <div className="flex items-baseline justify-between gap-3">
                <p className="text-sm text-neutral-600 dark:text-neutral-400 text-balance">
                  {v.questionText}
                </p>
                <span className="shrink-0 text-xs text-neutral-500">
                  {formatDay(v.votedAt)}
                </span>
              </div>
              <p>
                <span className="font-medium">{v.chosenNickname}</span>
                <span className="ml-2 text-xs text-neutral-500">
                  {SCOPE_LABEL[v.scope]}
                </span>
              </p>
            </li>
          ))}
        </ul>
      )}

      {error && (
        <p className="rounded border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </p>
      )}

      <button
        type="button"
        onClick={onClose}
        className="self-start text-xs text-neutral-500 underline underline-offset-4"
      >
        내 화면으로
      </button>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded px-3 py-1.5 transition-colors ${
        active
          ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
          : "text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100"
      }`}
    >
      {children}
    </button>
  );
}
