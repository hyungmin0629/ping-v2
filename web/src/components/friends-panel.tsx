"use client";

import { useCallback, useEffect, useState } from "react";
import {
  dismissSuggestion,
  listFriends,
  listIncomingRequests,
  listSuggestions,
  normalizeCode,
  removeFriend,
  respondToRequest,
  sendFriendRequest,
  sendRequestTo,
  REMOVE_MESSAGE,
  SEND_MESSAGE,
  type Person,
  type Suggestion,
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
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  // 끊기는 되돌릴 수 없어 한 번 더 묻는다. 목록에서 실수로 누르기 쉬운 자리다.
  const [confirming, setConfirming] = useState<Person | null>(null);
  const [error, setError] = useState("");

  // 상태 갱신을 콜백 안에서 한다 — effect 본문에서 곧바로 setState 하면
  // 렌더가 연쇄로 도는 패턴이라 린트가 막는다.
  const reload = useCallback(
    () =>
      Promise.all([listIncomingRequests(), listFriends(myId), listSuggestions()])
        .then(([reqs, mates, suggested]) => {
          setIncoming(reqs);
          setFriends(mates);
          setSuggestions(suggested);
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

  async function suggest(userId: number, send: boolean) {
    setBusyId(userId);
    setMessage("");
    try {
      if (send) {
        setMessage(SEND_MESSAGE[await sendRequestTo(userId)]);
      } else {
        await dismissSuggestion(userId);
      }
      await reload();
      if (send) onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
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

      {suggestions.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-medium">
            알 수도 있는 사람{" "}
            <span className="text-neutral-500">{suggestions.length}</span>
          </h2>
          <p className="text-xs leading-relaxed text-neutral-500">
            같은 학교 사람입니다. 요청을 보내면 상대가 수락해야 친구가 됩니다.
          </p>
          <ul className="divide-y divide-neutral-200 rounded border border-neutral-200 dark:divide-neutral-800 dark:border-neutral-800">
            {suggestions.map((s) => (
              <li
                key={s.id}
                className="flex items-center justify-between gap-3 px-4 py-3"
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm">{s.nickname}</span>
                  <span className="block text-xs text-neutral-500">
                    {s.belonging}
                    {s.sameClass && " · 같은 반"}
                  </span>
                </span>
                <span className="flex shrink-0 gap-2">
                  <button
                    type="button"
                    disabled={busyId === s.id}
                    onClick={() => suggest(s.id, true)}
                    className="rounded bg-neutral-900 px-3 py-1.5 text-xs text-white disabled:opacity-30 dark:bg-neutral-100 dark:text-neutral-900"
                  >
                    요청
                  </button>
                  <button
                    type="button"
                    disabled={busyId === s.id}
                    onClick={() => suggest(s.id, false)}
                    className="rounded border border-neutral-300 px-3 py-1.5 text-xs text-neutral-500 disabled:opacity-30 dark:border-neutral-700"
                  >
                    안 볼래
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
              <li key={p.id} className="flex items-center gap-3 px-4 py-3">
                <span className="min-w-0 flex-1">
                  <PersonLine person={p} />
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setMessage("");
                    setConfirming(p);
                  }}
                  className="shrink-0 text-xs text-neutral-500 underline underline-offset-2"
                >
                  끊기
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/*
        끊기 확인. 되돌릴 수 없는 데다, 끊으면 상대가 투표 후보에서도 빠진다.
        "차단이 아니다"를 함께 밝힌다 — 끊으면 다시는 못 만난다고 오해하기 쉽다.
      */}
      {confirming && (
        <div className="flex flex-col gap-3 rounded border border-neutral-300 p-4 dark:border-neutral-700">
          <p className="text-sm">
            <strong>{confirming.nickname}</strong> 님과 친구를 끊을까요?
          </p>
          <p className="text-xs leading-relaxed text-neutral-500">
            서로 친구 목록에서 사라지고 투표 후보에도 나오지 않습니다.
            <br />
            차단은 아니에요 — 초대 코드를 주고받으면 다시 친구가 될 수 있습니다.
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={busyId === confirming.id}
              onClick={() => setConfirming(null)}
              className="flex-1 rounded border border-neutral-300 px-4 py-2.5 text-sm disabled:opacity-40 dark:border-neutral-700"
            >
              그만두기
            </button>
            <button
              type="button"
              disabled={busyId === confirming.id}
              onClick={async () => {
                const target = confirming;
                setBusyId(target.id);
                setError("");
                try {
                  const result = await removeFriend(target.id);
                  setMessage(REMOVE_MESSAGE[result]);
                  setConfirming(null);
                  await reload();
                  onChanged();
                } catch (e) {
                  setError(e instanceof Error ? e.message : String(e));
                } finally {
                  setBusyId(null);
                }
              }}
              className="flex-1 rounded bg-neutral-900 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
            >
              끊기
            </button>
          </div>
        </div>
      )}

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
