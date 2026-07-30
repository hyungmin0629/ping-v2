"use client";

import { useEffect, useState } from "react";
import {
  listWithdrawalReasons,
  withdrawAccount,
  type WithdrawalReason,
} from "@/lib/profile";

const CONFIRM_WORD = "삭제";

/**
 * 계정 삭제.
 *
 * 두 단계로 나눈다 — 사유를 고르고, 확인 문구를 직접 입력해야 버튼이 열린다.
 * 되돌릴 수 없는 동작이라 "실수로 눌렀다"가 나올 수 없어야 한다.
 *
 * 사유를 받는 것은 절차를 무겁게 하려는 것이 아니다. 구 서비스는 탈퇴 7만 건에
 * 유저 식별자가 없어 "왜 떠났는가"를 영영 알 수 없었다. 그 구멍을 닫으려고
 * 스키마에 user_withdrawal 을 둔 것이고, 사유가 없으면 그 설계가 무의미해진다.
 */
export function WithdrawPanel({
  nickname,
  onCancel,
  onDone,
}: {
  nickname: string;
  onCancel: () => void;
  onDone: () => void;
}) {
  const [reasons, setReasons] = useState<WithdrawalReason[]>([]);
  const [code, setCode] = useState<string | null>(null);
  const [detail, setDetail] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    listWithdrawalReasons()
      .then(setReasons)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  const ready = code !== null && confirm.trim() === CONFIRM_WORD && !busy;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!ready || code === null) return;
    setBusy(true);
    setError("");
    try {
      await withdrawAccount(code, detail);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-7">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">계정 삭제</h1>
        <p className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
          <strong>{nickname}</strong> 계정을 삭제합니다. 되돌릴 수 없습니다.
        </p>
      </header>

      <div className="flex flex-col gap-2 rounded border border-neutral-300 px-4 py-3 text-xs leading-relaxed text-neutral-600 dark:border-neutral-700 dark:text-neutral-400">
        <p>삭제하면 이렇게 됩니다.</p>
        <ul className="flex list-disc flex-col gap-1 pl-4">
          <li>친구 목록·추천·투표 후보에서 사라집니다</li>
          <li>받은 투표와 하트를 다시 볼 수 없습니다</li>
          <li>이 브라우저로 다시 들어오면 <strong>새 계정</strong>이 됩니다</li>
          <li>
            게시판에 쓴 글은 남고 이름만 <strong>탈퇴한 사용자</strong>로 바뀝니다
            — 댓글이 달린 글을 지우면 남의 대화까지 사라지기 때문입니다
          </li>
        </ul>
      </div>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-sm font-medium">
          왜 그만두시나요? <span className="text-neutral-500">(필수)</span>
        </legend>
        {reasons.map((r) => (
          <button
            key={r.code}
            type="button"
            onClick={() => setCode(r.code)}
            className={`rounded border px-3 py-2.5 text-left text-sm transition-colors ${
              code === r.code
                ? "border-neutral-900 font-medium dark:border-neutral-100"
                : "border-neutral-300 text-neutral-600 dark:border-neutral-700 dark:text-neutral-400"
            }`}
          >
            {r.label}
          </button>
        ))}
      </fieldset>

      <label className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium">
          더 하고 싶은 말 <span className="text-neutral-500">(선택)</span>
        </span>
        <textarea
          value={detail}
          onChange={(e) => setDetail(e.target.value)}
          maxLength={500}
          rows={3}
          placeholder="무엇이 불편했는지 알려주시면 고치겠습니다"
          className="rounded border border-neutral-300 bg-transparent px-3 py-2.5 text-sm outline-none focus:border-neutral-900 dark:border-neutral-700 dark:focus:border-neutral-100"
        />
      </label>

      <label className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium">
          확인을 위해 <code className="font-mono">{CONFIRM_WORD}</code> 를 입력해 주세요
        </span>
        <input
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder={CONFIRM_WORD}
          className="rounded border border-neutral-300 bg-transparent px-3 py-2.5 outline-none focus:border-red-500 dark:border-neutral-700"
        />
      </label>

      {error && (
        <p className="rounded border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </p>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 rounded border border-neutral-300 px-4 py-3 font-medium dark:border-neutral-700"
        >
          그만두기
        </button>
        <button
          type="submit"
          disabled={!ready}
          className="flex-1 rounded bg-red-600 px-4 py-3 font-medium text-white transition-opacity disabled:opacity-30"
        >
          {busy ? "삭제 중…" : "계정 삭제"}
        </button>
      </div>
    </form>
  );
}
