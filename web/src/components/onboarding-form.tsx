"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  completeOnboarding,
  listClasses,
  listSchools,
  GENDER_LABEL,
  type ClassOption,
  type Gender,
  type Profile,
  type School,
} from "@/lib/profile";

/**
 * 온보딩 화면.
 *
 * 받는 것은 닉네임·성별·소속이다. 이름·이메일·전화번호는 받지 않는다.
 * 성별은 힌트로 파는 정보라(받은 투표의 2단계) 비워둘 수 없다.
 */
export function OnboardingForm({ onDone }: { onDone: (p: Profile) => void }) {
  const [schools, setSchools] = useState<School[]>([]);
  const [classes, setClasses] = useState<ClassOption[]>([]);
  const [schoolId, setSchoolId] = useState<number | null>(null);
  const [grade, setGrade] = useState<number | null>(null);
  const [classId, setClassId] = useState<number | null>(null);
  const [nickname, setNickname] = useState("");
  const [gender, setGender] = useState<Gender | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    listSchools()
      .then((rows) => {
        if (cancelled) return;
        setSchools(rows);
        // 클로즈드 테스트 기간에는 학교가 하나뿐이다. 고를 것이 없으면 미리 고른다.
        if (rows.length === 1) setSchoolId(rows[0].id);
      })
      .catch((e) => !cancelled && setError(messageOf(e)));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (schoolId === null) return;
    let cancelled = false;
    listClasses(schoolId)
      .then((rows) => !cancelled && setClasses(rows))
      .catch((e) => !cancelled && setError(messageOf(e)));
    return () => {
      cancelled = true;
    };
  }, [schoolId]);

  // 학교를 바꾸면 반 선택은 무효다. 화면을 다시 그리게 두지 않고 여기서 비운다.
  function chooseSchool(id: number | null) {
    setSchoolId(id);
    setGrade(null);
    setClassId(null);
    setClasses([]);
  }

  function chooseGrade(g: number | null) {
    setGrade(g);
    setClassId(null);
  }

  const grades = [...new Set(classes.map((c) => c.grade))].sort((a, b) => a - b);
  const classesOfGrade = classes.filter((c) => c.grade === grade);
  // 테스터에게는 팀 번호를 반으로 바꿔 넣으라고 안내해야 한다.
  // 조직 이름은 그대로 두고 실제 학교(서울고)의 학급을 쓰고 있기 때문이다.
  const isTestOrg = schools.find((s) => s.id === schoolId)?.name.includes("코드잇");

  const trimmed = nickname.trim();
  // 서버(complete_onboarding)와 같은 기준이다. 여기서 막는 건 안내용일 뿐,
  // 진짜 검증은 서버가 한다.
  const nicknameOk = trimmed.length >= 2 && trimmed.length <= 20;
  const canSubmit = nicknameOk && gender !== null && classId !== null && !submitting;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || classId === null || gender === null) return;

    setSubmitting(true);
    setError("");
    try {
      onDone(await completeOnboarding(trimmed, classId, gender));
    } catch (err) {
      setError(messageOf(err));
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight text-balance">
          어떻게 부르면 될까요?
        </h1>
        <p className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
          이름도 이메일도 전화번호도 받지 않습니다. 친구들이 알아볼 별명과
          성별·소속만 알려주세요.
        </p>
      </header>

      <div className="flex flex-col gap-5">
        <Field label="별명" hint="2~20자. 나중에 바꿀 수 있어요">
          <input
            type="text"
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            maxLength={20}
            autoFocus
            placeholder="친구들이 부르는 이름"
            className="w-full rounded border border-neutral-300 bg-transparent px-3 py-2.5 outline-none focus:border-neutral-900 dark:border-neutral-700 dark:focus:border-neutral-100"
          />
        </Field>

        <Field label="성별">
          <div className="flex gap-2">
            {(Object.keys(GENDER_LABEL) as Gender[]).map((g) => (
              <button
                key={g}
                type="button"
                onClick={() => setGender(g)}
                className={`flex-1 rounded border px-3 py-2.5 text-sm transition-colors ${
                  gender === g
                    ? "border-neutral-900 font-medium dark:border-neutral-100"
                    : "border-neutral-300 text-neutral-500 dark:border-neutral-700"
                }`}
              >
                {GENDER_LABEL[g]}
              </button>
            ))}
          </div>
        </Field>

        <Field label="학교">
          <select
            value={schoolId ?? ""}
            onChange={(e) => chooseSchool(Number(e.target.value) || null)}
            className="w-full rounded border border-neutral-300 bg-transparent px-3 py-2.5 outline-none focus:border-neutral-900 dark:border-neutral-700 dark:bg-neutral-950 dark:focus:border-neutral-100"
          >
            <option value="">선택하세요</option>
            {schools.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </Field>

        <div className="flex gap-3">
          <Field label="학년">
            <select
              value={grade ?? ""}
              onChange={(e) => chooseGrade(Number(e.target.value) || null)}
              disabled={classes.length === 0}
              className="w-full rounded border border-neutral-300 bg-transparent px-3 py-2.5 outline-none focus:border-neutral-900 disabled:opacity-40 dark:border-neutral-700 dark:bg-neutral-950 dark:focus:border-neutral-100"
            >
              <option value="">
                {schoolId === null ? "학교 먼저" : "선택"}
              </option>
              {grades.map((g) => (
                <option key={g} value={g}>
                  {g}학년
                </option>
              ))}
            </select>
          </Field>

          <Field label="반">
            <select
              value={classId ?? ""}
              onChange={(e) => setClassId(Number(e.target.value) || null)}
              disabled={grade === null}
              className="w-full rounded border border-neutral-300 bg-transparent px-3 py-2.5 outline-none focus:border-neutral-900 disabled:opacity-40 dark:border-neutral-700 dark:bg-neutral-950 dark:focus:border-neutral-100"
            >
              <option value="">{grade === null ? "학년 먼저" : "선택"}</option>
              {classesOfGrade.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.classNum}반
                </option>
              ))}
            </select>
          </Field>
        </div>

        {isTestOrg && (
          <p className="rounded border border-neutral-200 px-4 py-3 text-xs leading-relaxed text-neutral-600 dark:border-neutral-800 dark:text-neutral-400">
            <strong>팀 번호를 반으로 바꿔 넣어주세요.</strong>
            <br />
            1팀이면 <strong>1학년 1반</strong>, 2팀이면 <strong>1학년 2반</strong>,
            3팀이면 <strong>1학년 3반</strong>, 4팀이면 <strong>1학년 4반</strong>입니다.
          </p>
        )}
      </div>

      {error && (
        <p className="rounded border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={!canSubmit}
        className="rounded bg-neutral-900 px-4 py-3 font-medium text-white transition-opacity disabled:opacity-30 dark:bg-neutral-100 dark:text-neutral-900"
      >
        {submitting ? "만드는 중…" : "시작하기"}
      </button>

      {/*
        생년월일을 받지 않으므로 나이를 확인할 방법이 없다. 받는 순간
        개인정보 수집이 되므로, 고지로 갈음하는 것이 이 설계의 일관된 선택이다.
      */}
      <p className="text-xs leading-relaxed text-neutral-500">
        만 14세 미만은 가입할 수 없습니다. 시작하기를 누르면 만 14세 이상임을
        확인하고{" "}
        <Link href="/privacy" className="underline underline-offset-2">
          개인정보처리방침
        </Link>
        에 동의한 것으로 봅니다.
      </p>
    </form>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="flex items-baseline justify-between">
        <span className="font-medium">{label}</span>
        {hint && <span className="text-xs text-neutral-500">{hint}</span>}
      </span>
      {children}
    </label>
  );
}

function messageOf(e: unknown) {
  return e instanceof Error ? e.message : String(e);
}
