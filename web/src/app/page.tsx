"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { ensureAnonymousSession } from "@/lib/supabase/session";

type Status = "checking" | "ready" | "error";

type Diag = {
  userId: string;
  isAnonymous: boolean;
  profileExists: boolean;
  schoolCount: number | null;
  leakCheck: string;
};

export default function Home() {
  const [status, setStatus] = useState<Status>("checking");
  const [diag, setDiag] = useState<Diag | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const session = await ensureAnonymousSession();
        const supabase = createClient();

        // 온보딩 전이므로 app_user 행이 없는 것이 정상이다.
        const { data: profile } = await supabase
          .from("app_user")
          .select("id, nickname, invite_code")
          .maybeSingle();

        // 마스터 데이터는 읽혀야 한다 (온보딩에서 학교를 골라야 하므로).
        const { count: schoolCount } = await supabase
          .from("school")
          .select("*", { count: "exact", head: true });

        // 브라우저에서도 RLS가 실제로 막는지 확인한다.
        // 내 거래가 없으므로 0건이어야 하고, 남의 것이 새면 안 된다.
        const { data: others, error: leakErr } = await supabase
          .from("heart_transaction")
          .select("id")
          .limit(5);
        const leakCheck = leakErr
          ? `차단됨 (${leakErr.code})`
          : `${others?.length ?? 0}건 — 남의 내역 안 보임`;

        if (cancelled) return;
        setDiag({
          userId: session.user.id,
          isAnonymous: session.user.is_anonymous ?? false,
          profileExists: !!profile,
          schoolCount: schoolCount ?? null,
          leakCheck,
        });
        setStatus("ready");
      } catch (e) {
        if (cancelled) return;
        setMessage(e instanceof Error ? e.message : String(e));
        setStatus("error");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="mx-auto flex min-h-dvh max-w-xl flex-col justify-center gap-8 px-6 py-16">
      <header className="flex flex-col gap-2">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-neutral-500">
          W2 · 앱 뼈대
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-balance">
          접속만으로 계정이 생깁니다
        </h1>
        <p className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
          아이디도 비밀번호도 이메일도 받지 않습니다. 이 페이지를 연 순간 익명
          계정이 만들어졌고, 새로고침해도 같은 계정이 유지됩니다.
        </p>
      </header>

      {status === "checking" && (
        <p className="font-mono text-sm text-neutral-500">세션 확인 중…</p>
      )}

      {status === "error" && (
        <div className="rounded border border-red-300 bg-red-50 p-4 text-sm dark:border-red-900 dark:bg-red-950/40">
          <p className="mb-1 font-semibold text-red-700 dark:text-red-400">
            연결 실패
          </p>
          <p className="font-mono text-xs break-all text-red-900 dark:text-red-300">
            {message}
          </p>
        </div>
      )}

      {status === "ready" && diag && (
        <dl className="divide-y divide-neutral-200 rounded border border-neutral-200 text-sm dark:divide-neutral-800 dark:border-neutral-800">
          <Row label="계정 uuid" value={diag.userId} mono />
          <Row label="익명 계정" value={diag.isAnonymous ? "예" : "아니오"} />
          <Row
            label="프로필"
            value={diag.profileExists ? "생성됨" : "없음 — 온보딩(W3)에서 만듭니다"}
          />
          <Row
            label="학교 목록 조회"
            value={
              diag.schoolCount === null
                ? "실패"
                : `${diag.schoolCount}개 — 읽기 허용됨`
            }
          />
          <Row label="하트 거래 조회" value={diag.leakCheck} />
        </dl>
      )}

      <p className="text-xs leading-relaxed text-neutral-500">
        브라우저 저장소를 지우면 계정이 사라집니다. 복구 코드는 다음 버전에서
        제공합니다.
      </p>
    </main>
  );
}

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 px-4 py-3">
      <dt className="shrink-0 text-neutral-500">{label}</dt>
      <dd className={`text-right break-all ${mono ? "font-mono text-xs" : ""}`}>
        {value}
      </dd>
    </div>
  );
}
