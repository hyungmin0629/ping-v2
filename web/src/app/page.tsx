"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { BoardPanel } from "@/components/board-panel";
import { FriendsPanel } from "@/components/friends-panel";
import { InboxPanel } from "@/components/inbox-panel";
import { SchoolCalendar } from "@/components/school-calendar";
import { OnboardingForm } from "@/components/onboarding-form";
import { ProfileCard } from "@/components/profile-card";
import { TopupPanel } from "@/components/topup-panel";
import { VotePanel } from "@/components/vote-panel";
import { WithdrawPanel } from "@/components/withdraw-panel";
import { ensureAnonymousSession } from "@/lib/supabase/session";
import { touchSession } from "@/lib/session-log";
import { getMyProfile, type Profile } from "@/lib/profile";

/**
 * 접속하면 익명 계정이 생기고(W2), 온보딩 전이면 온보딩을(W3),
 * 마쳤으면 프로필·친구·투표를 보여준다(W4·W5).
 *
 * 화면 이동 대신 상태로 갈라진다. 주소를 나눌 만큼 화면이 많지 않고,
 * 투표는 시작하면 끝까지 가는 흐름이라 뒤로가기가 오히려 방해가 된다.
 */
type Screen =
  | "home" | "vote" | "inbox" | "board" | "profile" | "withdraw" | "topup";

export default function Home() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [screen, setScreen] = useState<Screen>("home");
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    getMyProfile()
      .then((p) => p && setProfile(p))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        await ensureAnonymousSession();
        const mine = await getMyProfile();
        if (cancelled) return;
        setProfile(mine);
        // 리텐션을 실측할 재료. 실패해도 화면을 막지 않는다.
        touchSession();
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

  /**
   * 화면 이동을 브라우저 이력에 실는다.
   *
   * 이 앱은 주소를 나누지 않고 상태로 화면을 가른다(동적 라우트를 쓸 수 없는
   * 사정은 CLAUDE.md). 그대로 두면 **휴대폰 뒤로가기가 앱을 나가버린다** —
   * 테스터 대부분이 폰으로 들어오므로 실제로 자주 밟는다.
   * pushState 로 한 칸 쌓아두고 popstate 에서 홈으로 되돌린다.
   */
  function go(next: Screen) {
    setScreen(next);
    if (next !== "home") window.history.pushState({ screen: next }, "");
  }

  // 화면 안의 닫기 버튼도 같은 길을 타게 한다. 직접 setScreen 하면
  // 쌓아둔 이력이 남아 뒤로가기를 두 번 눌러야 나가진다.
  function backHome() {
    window.history.back();
  }

  useEffect(() => {
    function onPop() {
      setScreen("home");
      refresh();
    }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [refresh]);

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

      {!loading && !error && !profile && (
        <OnboardingForm
          onDone={(p) => {
            setProfile(p);
            touchSession();
          }}
        />
      )}

      {!loading && !error && profile && screen === "vote" && (
        <VotePanel onClose={backHome} />
      )}

      {!loading && !error && profile && screen === "inbox" && (
        <InboxPanel
          hearts={profile.heartBalance}
          onClose={backHome}
          onChanged={refresh}
        />
      )}

      {!loading && !error && profile && screen === "board" && (
        <BoardPanel onClose={backHome} />
      )}

      {!loading && !error && profile && screen === "topup" && (
        <TopupPanel
          hearts={profile.heartBalance}
          onClose={backHome}
          onChanged={refresh}
        />
      )}

      {!loading && !error && profile && screen === "profile" && (
        <div className="flex flex-col gap-10">
          <OnboardingForm
            edit={profile}
            onCancel={backHome}
            onDone={(p) => {
              setProfile(p);
              backHome();
            }}
          />
          <div className="border-t border-neutral-200 pt-6 dark:border-neutral-800">
            <button
              type="button"
              onClick={() => go("withdraw")}
              className="text-xs text-neutral-500 underline underline-offset-4"
            >
              계정 삭제
            </button>
          </div>
        </div>
      )}

      {!loading && !error && profile && screen === "withdraw" && (
        <WithdrawPanel
          nickname={profile.nickname}
          onCancel={backHome}
          onDone={() => {
            // 프로필을 비우면 온보딩 화면으로 돌아간다. 같은 브라우저지만
            // 계정 연결이 끊겼으므로 새로 가입하는 사람이 된다.
            setProfile(null);
            setScreen("home");
            window.history.go(-2);
          }}
        />
      )}

      {!loading && !error && profile && screen === "home" && (
        <div className="flex flex-col gap-10">
          <ProfileCard profile={profile} />

          <section className="flex flex-col gap-3">
            {profile.unlocked ? (
              <>
                <button
                  type="button"
                  onClick={() => go("vote")}
                  className="rounded bg-neutral-900 px-4 py-4 font-medium text-white dark:bg-neutral-100 dark:text-neutral-900"
                >
                  투표하러 가기
                </button>
                <button
                  type="button"
                  onClick={() => go("inbox")}
                  className="rounded border border-neutral-300 px-4 py-3 text-sm font-medium dark:border-neutral-700"
                >
                  받은 투표 보기
                </button>
              </>
            ) : (
              <p className="rounded border border-dashed border-neutral-300 px-4 py-6 text-center text-sm leading-relaxed text-neutral-500 dark:border-neutral-700">
                친구를 {Math.max(0, 5 - profile.friendCount)}명 더 모으면
                <br />
                투표가 열립니다
              </p>
            )}

            {/* 게시판은 친구 5명 게이트와 무관하다. 투표는 친구가 있어야
                성립하지만, 게시판은 같은 학교면 성립한다. */}
            <button
              type="button"
              onClick={() => go("board")}
              className="rounded border border-neutral-300 px-4 py-3 text-sm font-medium dark:border-neutral-700"
            >
              자유게시판
            </button>
            <button
              type="button"
              onClick={() => go("topup")}
              className="rounded border border-neutral-300 px-4 py-3 text-sm font-medium dark:border-neutral-700"
            >
              하트 충전
            </button>
          </section>

          <section className="flex flex-col gap-3 rounded border border-neutral-200 dark:border-neutral-800">
            <button
              type="button"
              onClick={() => setCalendarOpen((v) => !v)}
              className="flex items-center justify-between px-4 py-3 text-sm font-medium"
            >
              급식·학사일정
              <span className="text-xs text-neutral-500">
                {calendarOpen ? "닫기" : "열기"}
              </span>
            </button>
            {calendarOpen && (
              <div className="border-t border-neutral-200 p-4 dark:border-neutral-800">
                <SchoolCalendar />
              </div>
            )}
          </section>

          <hr className="border-neutral-200 dark:border-neutral-800" />
          <FriendsPanel myId={profile.id} onChanged={refresh} />

          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={() => go("profile")}
              className="text-xs text-neutral-500 underline underline-offset-4"
            >
              프로필 수정
            </button>
            <Link
              href="/privacy"
              className="text-xs text-neutral-500 underline underline-offset-4"
            >
              개인정보처리방침
            </Link>
          </div>
        </div>
      )}
    </main>
  );
}
