"use client";

import { useCallback, useEffect, useState } from "react";
import {
  listFriends,
  listIncomingRequests,
  normalizeCode,
  respondToRequest,
  sendFriendRequest,
  SEND_MESSAGE,
  type Person,
} from "@/lib/friends";

/**
 * 친구 화면. 코드 입력 · 받은 요청 · 친구 목록.
 *
 * 수락하면 내 친구 수와 게이트 상태가 바뀌므로 프로필도 다시 읽어야 한다.
 * 그 갱신은 부모(page)가 한다.
 */
export function FriendsPanel({
  myId,
  onChanged,
}: {
  myId: number;
  onChanged: () => void;
}) {
  const [code, setCode] = useState("");
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState("");
  const [incoming, setIncoming] = useState<Person[]>([]);
  const [friends, setFriends] = useState<Person[]>([]);
  const [error, setError] = useState("");

  // 상태 갱신을 콜백 안에서 한다 — effect 본문에서 곧바로 setState 하면
  // 렌더가 연쇄로 도는 패턴이라 린트가 막는다.
  const reload = useCallback(
    () =>
      Promise.all([listIncomingRequests(), listFriends(myId)])
        .then(([reqs, mates]) => {
          setIncoming(reqs);
          setFriends(mates);
          setError("");
        })
        .catch((e) => setError(e instanceof Error ? e.message : String(e))),
    [myId],
  );

  useEffect(() => {
    reload();
  }, [reload]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const normalized = normalizeCode(code);
    if (!normalized || sending) return;

    setSending(true);
    setMessage("");
    try {
      const result = await sendFriendRequest(normalized);
      setMessage(SEND_MESSAGE[result]);
      if (result === "SENT" || result === "ACCEPTED") setCode("");
      await reload();
      onChanged();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  }

  async function respond(requestId: number, accept: boolean) {
    try {
      await respondToRequest(requestId, accept);
      await reload();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium">친구 추가</h2>
        <form onSubmit={handleSend} className="flex gap-2">
          <input
            value={code}
            // maxLength 를 걸면 브라우저가 붙여넣기를 잘라버린다.
            // 길이 제한과 정리는 normalizeCode 가 한다.
            onChange={(e) => setCode(normalizeCode(e.target.value))}
            placeholder="친구의 초대 코드"
            autoCapitalize="characters"
            className="min-w-0 flex-1 rounded border border-neutral-300 bg-transparent px-3 py-2.5 font-mono tracking-widest outline-none placeholder:font-sans placeholder:tracking-normal focus:border-neutral-900 dark:border-neutral-700 dark:focus:border-neutral-100"
          />
          <button
            type="submit"
            disabled={!normalizeCode(code) || sending}
            className="shrink-0 rounded bg-neutral-900 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-30 dark:bg-neutral-100 dark:text-neutral-900"
          >
            {sending ? "보내는 중…" : "요청"}
          </button>
        </form>
        {message && (
          <p className="text-sm text-neutral-600 dark:text-neutral-400">
            {message}
          </p>
        )}
      </section>

      {incoming.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-medium">
            받은 요청 <span className="text-neutral-500">{incoming.length}</span>
          </h2>
          <ul className="divide-y divide-neutral-200 rounded border border-neutral-200 dark:divide-neutral-800 dark:border-neutral-800">
            {incoming.map((p) => (
              <li
                key={p.id}
                className="flex items-center justify-between gap-3 px-4 py-3"
              >
                <PersonLine person={p} />
                <span className="flex shrink-0 gap-2">
                  <button
                    type="button"
                    onClick={() => respond(p.id, true)}
                    className="rounded bg-neutral-900 px-3 py-1.5 text-xs text-white dark:bg-neutral-100 dark:text-neutral-900"
                  >
                    수락
                  </button>
                  <button
                    type="button"
                    onClick={() => respond(p.id, false)}
                    className="rounded border border-neutral-300 px-3 py-1.5 text-xs dark:border-neutral-700"
                  >
                    거절
                  </button>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium">
          친구 <span className="text-neutral-500">{friends.length}</span>
        </h2>
        {friends.length === 0 ? (
          <p className="text-sm leading-relaxed text-neutral-500">
            아직 없습니다. 내 초대 코드를 알려주거나, 친구의 코드를 위에
            입력하세요.
          </p>
        ) : (
          <ul className="divide-y divide-neutral-200 rounded border border-neutral-200 dark:divide-neutral-800 dark:border-neutral-800">
            {friends.map((p) => (
              <li key={p.id} className="px-4 py-3">
                <PersonLine person={p} />
              </li>
            ))}
          </ul>
        )}
      </section>

      {error && (
        <p className="font-mono text-xs break-all text-red-700 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}

function PersonLine({ person }: { person: Person }) {
  return (
    <span className="min-w-0 flex-1">
      <span className="font-medium">{person.nickname}</span>
      {person.belonging && (
        <span className="ml-2 text-xs text-neutral-500">{person.belonging}</span>
      )}
    </span>
  );
}
