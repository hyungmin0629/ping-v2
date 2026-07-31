"use client";

import { useCallback, useEffect, useState } from "react";
import { ReceivedDetail } from "./received-detail";
import {
  formatDay,
  listMyVotes,
  listReceived,
  markRead,
  UNLOCK_MIN,
  blankName,
  type MyVote,
  type ReceivedVote,
} from "@/lib/received";

type Tab = "received" | "sent";

/**
 * 받은 투표 / 내가 한 투표.
 *
 * 받은 쪽은 하나를 눌러 상세로 들어가 힌트를 관리한다(W14). 힌트가 5+1 로
 * 늘면서 목록에 다 늘어놓을 수 없게 됐고, 무엇을 열었는지도 투표마다 다르다.
 *
 * 보낸 쪽은 내 기록이라 그냥 보인다 — 가려야 하는 것은 "누가 나를 뽑았나"이지
 * "내가 누구를 뽑았나"가 아니다.
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
  const [open, setOpen] = useState<ReceivedVote | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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
          // 상세를 보고 있으면 그 항목도 새로 고친다.
          setOpen((cur) => (cur ? (inbox.find((r) => r.id === cur.id) ?? cur) : null));
        })
        .catch((e) => setError(e instanceof Error ? e.message : String(e)))
        .finally(() => setLoading(false)),
    [],
  );

  useEffect(() => {
    reload();
  }, [reload]);

  if (open) {
    return (
      <ReceivedDetail
        item={open}
        hearts={hearts}
        onBack={() => setOpen(null)}
        onChanged={() => {
          reload();
          onChanged();
        }}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div className="flex gap-4">
          <TabButton active={tab === "received"} onClick={() => setTab("received")}>
            받은 투표
          </TabButton>
          <TabButton active={tab === "sent"} onClick={() => setTab("sent")}>
            내가 한 투표
          </TabButton>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-sm text-neutral-500 underline underline-offset-4"
        >
          홈으로
        </button>
      </div>

      {error && (
        <p className="rounded border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </p>
      )}
      {loading && <p className="font-mono text-sm text-neutral-500">불러오는 중…</p>}

      {!loading && tab === "received" && (
        <>
          {received.length === 0 && (
            <p className="rounded border border-dashed border-neutral-300 px-4 py-10 text-center text-sm text-neutral-500 dark:border-neutral-700">
              아직 받은 투표가 없습니다
            </p>
          )}
          <ul className="flex flex-col">
            {received.map((r) => (
              <li key={r.id} className="border-b border-neutral-200 dark:border-neutral-800">
                <button
                  type="button"
                  onClick={() => setOpen(r)}
                  className="flex w-full items-center justify-between gap-3 py-4 text-left"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm">{r.question}</span>
                    <span className="mt-1 block text-xs text-neutral-500">
                      {formatDay(r.createdAt)} ·{" "}
                      {r.hasName
                        ? r.nickname
                        : r.basicCount === 0
                          ? "아직 아무 힌트도 열지 않음"
                          : `힌트 ${r.basicCount} / ${UNLOCK_MIN}`}
                    </span>
                  </span>
                  <span className="shrink-0 font-mono text-sm tracking-widest text-neutral-500">
                    {r.hasName ? "공개" : blankName(r.nameLength)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      {!loading && tab === "sent" && (
        <>
          {sent.length === 0 && (
            <p className="rounded border border-dashed border-neutral-300 px-4 py-10 text-center text-sm text-neutral-500 dark:border-neutral-700">
              아직 한 투표가 없습니다
            </p>
          )}
          <ul className="flex flex-col">
            {sent.map((v) => (
              <li
                key={v.id}
                className="border-b border-neutral-200 py-4 dark:border-neutral-800"
              >
                <p className="text-sm">{v.question}</p>
                <p className="mt-1 text-xs text-neutral-500">
                  {formatDay(v.votedAt)} · <strong>{v.chosenNickname}</strong>
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
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
      className={`text-sm transition-colors ${
        active ? "font-semibold" : "text-neutral-500"
      }`}
    >
      {children}
    </button>
  );
}
