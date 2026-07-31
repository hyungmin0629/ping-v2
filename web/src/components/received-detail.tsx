"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  adAvailable,
  buyHint,
  completeAd,
  getReceived,
  startAd,
  AD_SECONDS,
  BUY_MESSAGE,
  GENDER_TEXT,
  HINT_COST,
  HINT_LABEL,
  HINT_ORDER,
  NAME_COST,
  REPLY_COST,
  REPLY_MAX,
  REPLY_MESSAGE,
  UNLOCK_MIN,
  sendReply,
  blankName,
  formatDay,
  type HintKind,
  type ReceivedVote,
} from "@/lib/received";

/**
 * 받은 투표 하나 — 힌트를 관리하는 창.
 *
 * 힌트 5종은 **순서가 없다.** 아무거나 골라 살 수 있고, 3개 이상 열면
 * 이름 공개가 열린다. 자모 힌트 셋은 각자 다른 글자를 가리키므로
 * 합치지 않고 나란히 보여준다.
 *
 * 성별만 광고로도 열 수 있다(하루 한 번). 광고는 스텁이라 30초를 세는 것이
 * 전부지만, 기록은 진짜로 남는다.
 */
export function ReceivedDetail({
  item,
  hearts,
  onBack,
  onChanged,
}: {
  item: ReceivedVote;
  hearts: number;
  onBack: () => void;
  onChanged: () => void;
}) {
  const [vote, setVote] = useState(item);
  const [canAd, setCanAd] = useState(false);
  const [adLeft, setAdLeft] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const adRef = useRef<number | null>(null);

  const reload = useCallback(async () => {
    const fresh = await getReceived(vote.id);
    if (fresh) setVote(fresh);
    onChanged();
  }, [vote.id, onChanged]);

  useEffect(() => {
    adAvailable().then(setCanAd).catch(() => setCanAd(false));
  }, []);

  // 광고 카운트다운. 스텁이라 시간만 센다.
  useEffect(() => {
    if (adLeft === null) return;
    if (adLeft <= 0) {
      const id = adRef.current;
      adRef.current = null;
      setAdLeft(null);
      if (id === null) return;
      (async () => {
        setBusy(true);
        try {
          await completeAd(id);
          const result = await buyHint(vote.id, "GENDER", id);
          if (result !== "OK") setNotice(BUY_MESSAGE[result]);
          setCanAd(await adAvailable());
          await reload();
        } catch (e) {
          setError(e instanceof Error ? e.message : String(e));
        } finally {
          setBusy(false);
        }
      })();
      return;
    }
    const t = setTimeout(() => setAdLeft((n) => (n ?? 0) - 1), 1000);
    return () => clearTimeout(t);
  }, [adLeft, vote.id, reload]);

  async function buy(kind: HintKind | "FULL_NAME") {
    setBusy(true);
    setNotice("");
    setError("");
    try {
      const result = await buyHint(vote.id, kind);
      if (result !== "OK") setNotice(BUY_MESSAGE[result]);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function watchAd() {
    setNotice("");
    setError("");
    try {
      adRef.current = await startAd();
      setAdLeft(AD_SECONDS);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function reply() {
    if (!draft.trim() || busy) return;
    setBusy(true);
    setNotice("");
    setError("");
    try {
      const result = await sendReply(vote.id, draft.trim());
      setNotice(REPLY_MESSAGE[result]);
      if (result === "OK") setDraft("");
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  // 열린 자모를 나란히. 셋은 서로 다른 자리를 가리킨다.
  const jamo: [HintKind, string | null][] = [
    ["INITIAL", vote.leadHint],
    ["MEDIAL", vote.vowelHint],
    ["FINAL", vote.tailHint],
  ];
  const openJamo = jamo.filter(([, v]) => v !== null);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onBack}
          className="text-sm text-neutral-500 underline underline-offset-4"
        >
          목록
        </button>
        <span className="font-mono text-sm tabular-nums text-neutral-500">
          ♥ {hearts.toLocaleString()}
        </span>
      </div>

      <header className="flex flex-col gap-1">
        <p className="text-xs text-neutral-500">{formatDay(vote.createdAt)}</p>
        <h2 className="text-lg leading-snug font-semibold text-balance">
          {vote.question}
        </h2>
      </header>

      {/* 지금까지 알아낸 것 */}
      <section className="flex flex-col gap-3 rounded border border-neutral-300 px-4 py-4 dark:border-neutral-700">
        <p className="text-xs text-neutral-500">나를 뽑은 사람</p>
        <p className="font-mono text-2xl font-semibold tracking-widest">
          {vote.hasName ? vote.nickname : blankName(vote.nameLength)}
        </p>

        {(vote.gender || vote.grade !== null || openJamo.length > 0) && (
          <dl className="flex flex-col gap-1.5 text-sm">
            {vote.gender && (
              <Line label="성별">{GENDER_TEXT[vote.gender] ?? vote.gender}</Line>
            )}
            {vote.grade !== null && (
              <Line label="반">
                {vote.grade}학년 {vote.classNum}반
              </Line>
            )}
            {openJamo.map(([kind, value]) => (
              <Line key={kind} label={HINT_LABEL[kind].replace("글자 하나의 ", "")}>
                <span className="font-mono tracking-widest">{value}</span>
              </Line>
            ))}
          </dl>
        )}

        {!vote.hasName && (
          <p className="text-xs leading-relaxed text-neutral-500">
            기본 힌트 {vote.basicCount} / {UNLOCK_MIN}개
            {vote.canUnlockName
              ? " — 이름을 볼 수 있어요"
              : ` — ${UNLOCK_MIN - vote.basicCount}개 더 열면 이름을 볼 수 있어요`}
          </p>
        )}
      </section>

      {notice && (
        <p className="rounded border border-neutral-300 px-4 py-3 text-sm dark:border-neutral-700">
          {notice}
        </p>
      )}
      {error && (
        <p className="rounded border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </p>
      )}

      {adLeft !== null && (
        <p className="rounded border border-neutral-300 px-4 py-6 text-center text-sm dark:border-neutral-700">
          광고를 보는 중… <strong className="font-mono tabular-nums">{adLeft}</strong>초
          <br />
          <span className="text-xs text-neutral-500">
            시험판이라 실제 광고 대신 기다리기만 합니다
          </span>
        </p>
      )}

      {/* 힌트 고르기 — 순서가 없다 */}
      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium">힌트 열기</h3>
        {HINT_ORDER.map((kind) => {
          const done = vote.bought[kind];
          return (
            <div key={kind} className="flex gap-2">
              <button
                type="button"
                disabled={done || busy || adLeft !== null}
                onClick={() => buy(kind)}
                className={`flex flex-1 items-center justify-between gap-3 rounded border px-4 py-3 text-left text-sm transition-opacity disabled:opacity-40 ${
                  done
                    ? "border-neutral-900 dark:border-neutral-100"
                    : "border-neutral-300 dark:border-neutral-700"
                }`}
              >
                <span>{HINT_LABEL[kind]}</span>
                <span className="shrink-0 font-mono text-xs tabular-nums text-neutral-500">
                  {done ? "열림" : `♥ ${HINT_COST}`}
                </span>
              </button>
              {/* 성별만 광고로 열 수 있다. 하루 한 번. */}
              {kind === "GENDER" && !done && (
                <button
                  type="button"
                  disabled={!canAd || busy || adLeft !== null}
                  onClick={watchAd}
                  className="shrink-0 rounded border border-neutral-300 px-3 py-3 text-xs disabled:opacity-30 dark:border-neutral-700"
                >
                  {canAd ? "광고 보고 무료" : "오늘 다 씀"}
                </button>
              )}
            </div>
          );
        })}
      </section>

      {!vote.hasName && (
        <button
          type="button"
          disabled={!vote.canUnlockName || busy || adLeft !== null}
          onClick={() => buy("FULL_NAME")}
          className="flex items-center justify-between gap-3 rounded bg-neutral-900 px-4 py-4 font-medium text-white transition-opacity disabled:opacity-30 dark:bg-neutral-100 dark:text-neutral-900"
        >
          <span>누구인지 보기</span>
          <span className="font-mono text-sm tabular-nums">♥ {NAME_COST}</span>
        </button>
      )}

      {/* 답장 — 힌트와 순서가 없다. 누군지 몰라도 고맙다고 할 수는 있다. */}
      <section className="flex flex-col gap-2 border-t border-neutral-200 pt-6 dark:border-neutral-800">
        <h3 className="text-sm font-medium">답장 보내기</h3>
        {vote.reply ? (
          <div className="rounded border border-neutral-300 px-4 py-3 dark:border-neutral-700">
            <p className="text-sm">{vote.reply}</p>
            <p className="mt-1 text-xs text-neutral-500">
              이미 보냈습니다. 답장은 한 번만 보낼 수 있어요.
            </p>
          </div>
        ) : (
          <>
            <p className="text-xs leading-relaxed text-neutral-500">
              나를 뽑은 사람에게 <strong>한 번만</strong> 보낼 수 있습니다.
              상대는 자기가 누구를 뽑았는지 알기 때문에,{" "}
              <strong>보낸 사람이 나라는 것을 압니다.</strong>
            </p>
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              maxLength={REPLY_MAX}
              rows={2}
              placeholder="짧게 한마디"
              className="rounded border border-neutral-300 bg-transparent px-3 py-2.5 text-sm outline-none focus:border-neutral-900 dark:border-neutral-700 dark:focus:border-neutral-100"
            />
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-xs tabular-nums text-neutral-500">
                {draft.length} / {REPLY_MAX}
              </span>
              <button
                type="button"
                disabled={!draft.trim() || busy || adLeft !== null}
                onClick={reply}
                className="rounded border border-neutral-300 px-4 py-2.5 text-sm font-medium disabled:opacity-30 dark:border-neutral-700"
              >
                보내기 ♥ {REPLY_COST}
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}

function Line({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-neutral-500">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}
