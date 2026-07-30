"use client";

import { useState } from "react";
import type { Profile } from "@/lib/profile";

const FRIEND_GATE = 5; // 투표가 열리는 친구 수. 후보 풀의 하한을 보장한다.

/**
 * 온보딩을 마친 뒤 보는 화면.
 *
 * 초대 코드가 주인공이다. 친구를 맺는 유일한 수단이고(전화번호를 받지 않으므로),
 * 이 코드를 주고받아야 투표가 열린다.
 */
export function ProfileCard({ profile }: { profile: Profile }) {
  const [copied, setCopied] = useState<"code" | "link" | null>(null);

  async function copy(what: "code" | "link") {
    // 링크는 코드를 주소에 담은 것뿐이다. 받은 사람이 누르면 가입 후 요청이
    // 자동으로 간다. 친구를 맺는 근거는 여전히 초대 코드 하나다.
    const text =
      what === "code"
        ? profile.inviteCode
        : `${window.location.origin}/add?code=${profile.inviteCode}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(what);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      // 클립보드를 막아둔 브라우저도 있다. 코드는 화면에 이미 보이므로 넘어간다.
    }
  }

  const remaining = Math.max(0, FRIEND_GATE - profile.friendCount);

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-3xl font-semibold tracking-tight">
          {profile.nickname}
        </h1>
        <p className="text-sm text-neutral-500">{profile.belonging}</p>
      </header>

      <section className="flex flex-col gap-3 rounded border border-neutral-200 p-5 dark:border-neutral-800">
        <p className="text-sm font-medium">내 초대 코드</p>
        <div className="flex items-center gap-3">
          <span className="font-mono text-3xl tracking-[0.2em] tabular-nums">
            {profile.inviteCode}
          </span>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => copy("link")}
            className="rounded bg-neutral-900 px-3 py-1.5 text-xs text-white transition-opacity hover:opacity-80 dark:bg-neutral-100 dark:text-neutral-900"
          >
            {copied === "link" ? "복사됨" : "초대 링크 복사"}
          </button>
          <button
            type="button"
            onClick={() => copy("code")}
            className="rounded border border-neutral-300 px-3 py-1.5 text-xs transition-colors hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-900"
          >
            {copied === "code" ? "복사됨" : "코드만 복사"}
          </button>
        </div>
        <p className="text-xs leading-relaxed text-neutral-500">
          링크를 보내면 친구는 누르기만 하면 됩니다. 직접 불러줄 때만 코드를 쓰세요.
          어느 쪽이든 내가 수락해야 친구가 됩니다.
        </p>
      </section>

      <dl className="divide-y divide-neutral-200 rounded border border-neutral-200 text-sm dark:divide-neutral-800 dark:border-neutral-800">
        <Row label="하트" value={`${profile.heartBalance.toLocaleString()}개`} />
        <Row
          label="친구"
          value={`${profile.friendCount}명 / ${FRIEND_GATE}명`}
        />
      </dl>

      <p className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
        {remaining > 0
          ? `친구 ${remaining}명을 더 모으면 투표가 열립니다.`
          : "투표를 시작할 수 있습니다."}
      </p>

      {/* 초대 코드를 적어두라고 안내하던 자리다. 그건 틀린 말이었다 —
          초대 코드는 남이 나를 찾는 코드고, 계정을 되찾는 데는 쓸 수 없다.
          지금은 복구 수단이 아예 없으므로, 있는 그대로 알린다. */}
      <p className="text-xs leading-relaxed text-neutral-500">
        이 계정은 <strong>지금 이 브라우저에만</strong> 있습니다. 저장소를
        지우거나 다른 브라우저·기기로 열면 <strong>새 계정</strong>이 되고,
        친구와 하트는 되찾을 수 없습니다.
      </p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 px-4 py-3">
      <dt className="text-neutral-500">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
