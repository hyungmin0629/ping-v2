"use client";

import { useEffect, useState } from "react";
import { OnboardingForm } from "@/components/onboarding-form";
import { ProfileCard } from "@/components/profile-card";
import { ensureAnonymousSession } from "@/lib/supabase/session";
import { getMyProfile, type Profile } from "@/lib/profile";

/**
 * 접속하면 익명 계정이 생기고(W2), 아직 온보딩 전이면 온보딩 화면을,
 * 마쳤으면 프로필을 보여준다(W3).
 *
 * 화면 이동 없이 한 페이지에서 갈라진다. 온보딩은 한 번뿐이라 주소를 나눌 이유가 없다.
 */
export default function Home() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        await ensureAnonymousSession();
        const mine = await getMyProfile();
        if (cancelled) return;
        setProfile(mine);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col justify-center px-6 py-16">
      {loading && (
        <p className="font-mono text-sm text-neutral-500">불러오는 중…</p>
      )}

      {!loading && error && (
        <div className="rounded border border-red-300 bg-red-50 p-4 text-sm dark:border-red-900 dark:bg-red-950/40">
          <p className="mb-1 font-semibold text-red-700 dark:text-red-400">
            연결 실패
          </p>
          <p className="font-mono text-xs break-all text-red-900 dark:text-red-300">
            {error}
          </p>
        </div>
      )}

      {!loading && !error && !profile && <OnboardingForm onDone={setProfile} />}
      {!loading && !error && profile && <ProfileCard profile={profile} />}
    </main>
  );
}
