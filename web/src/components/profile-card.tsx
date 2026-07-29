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
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(profile.inviteCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
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
          <button
            type="button"
            onClick={copy}
            className="rounded border border-neutral-300 px-3 py-1.5 text-xs transition-colors hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-900"
          >
            {copied ? "복사됨" : "복사"}
          </button>
        </div>
        <p className="text-xs leading-relaxed text-neutral-500">
          이 코드를 친구에게 알려주세요. 친구가 코드를 입력하면 서로 친구가 됩니다.
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

      <p className="text-xs leading-relaxed text-neutral-500">
        친구 추가 화면은 준비 중입니다(W4). 브라우저 저장소를 지우면 계정이
        사라지니, 초대 코드를 적어두세요.
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
