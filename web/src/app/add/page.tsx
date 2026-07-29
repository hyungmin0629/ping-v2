"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { OnboardingForm } from "@/components/onboarding-form";
import { getMyProfile, type Profile } from "@/lib/profile";
import { normalizeCode, sendFriendRequest, SEND_MESSAGE } from "@/lib/friends";
import { touchSession } from "@/lib/session-log";
import { ensureAnonymousSession } from "@/lib/supabase/session";

/**
 * 초대 링크. /add?code=6RSH96F8
 *
 * 코드를 주소에 담았을 뿐, 맺어지는 근거는 여전히 초대 코드다.
 * 아직 가입 전이면 온보딩을 먼저 시키고, 끝나는 대로 요청을 보낸다.
 *
 * 왜 /add/[code] 가 아니라 쿼리스트링인가:
 *   이 환경(Windows + Next 16)에서는 **모든 동적 라우트가 개발 서버에서 500** 이다.
 *   최소한의 [x] 라우트로 재현했다(Jest worker ... exceeding retry limit).
 *   프로덕션 빌드는 정상이지만, 로컬에서 확인할 수 없는 구조는 쓰지 않는다.
 */
export default function AddFriendPage() {
  return (
    <Suspense
      fallback={
        <main className="mx-auto flex min-h-dvh w-full max-w-md items-center px-6">
          <p className="font-mono text-sm text-neutral-500">불러오는 중…</p>
        </main>
      }
    >
      <AddFriend />
    </Suspense>
  );
}

function AddFriend() {
  const invite = normalizeCode(useSearchParams().get("code") ?? "");

  const [profile, setProfile] = useState<Profile | null>(null);
  const [checking, setChecking] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  // 개발 모드에서 effect 가 두 번 도는 것에 대비한다. 두 번 보내도 서버는
  // ALREADY_SENT 를 돌려주지만, 화면 문구가 그걸로 바뀌면 혼란스럽다.
  const sent = useRef(false);

  const send = useCallback(async () => {
    if (sent.current || !invite) return;
    sent.current = true;
    try {
      setMessage(SEND_MESSAGE[await sendFriendRequest(invite)]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [invite]);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        await ensureAnonymousSession();
        const mine = await getMyProfile();
        if (cancelled) return;
        setProfile(mine);
        touchSession();
        if (mine) await send();
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setChecking(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [send]);

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col justify-center gap-8 px-6 py-16">
      {checking && (
        <p className="font-mono text-sm text-neutral-500">불러오는 중…</p>
      )}

      {!checking && !invite && (
        <div className="flex flex-col gap-6">
          <h1 className="text-2xl font-semibold tracking-tight">
            초대 코드가 없는 링크입니다
          </h1>
          <p className="text-sm text-neutral-500">
            친구에게 받은 링크를 다시 확인해 주세요.
          </p>
          <HomeButton />
        </div>
      )}

      {!checking && invite && !profile && (
        <>
          <p className="rounded border border-neutral-200 px-4 py-3 text-sm dark:border-neutral-800">
            초대를 받았습니다 —{" "}
            <span className="font-mono tracking-widest">{invite}</span>
            <br />
            <span className="text-neutral-500">
              별명만 정하면 바로 친구 요청을 보냅니다.
            </span>
          </p>
          <OnboardingForm
            onDone={async (p) => {
              setProfile(p);
              touchSession();
              await send();
            }}
          />
        </>
      )}

      {!checking && invite && profile && (
        <div className="flex flex-col gap-6">
          <h1 className="text-2xl leading-snug font-semibold tracking-tight text-balance">
            {message || "요청을 보내는 중…"}
          </h1>
          <HomeButton />
        </div>
      )}

      {error && (
        <p className="font-mono text-xs break-all text-red-700 dark:text-red-400">
          {error}
        </p>
      )}
    </main>
  );
}

function HomeButton() {
  return (
    <Link
      href="/"
      className="rounded bg-neutral-900 px-4 py-3 text-center font-medium text-white dark:bg-neutral-100 dark:text-neutral-900"
    >
      내 화면으로
    </Link>
  );
}
