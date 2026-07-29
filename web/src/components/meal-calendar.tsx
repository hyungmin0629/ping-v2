"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getSchoolSource,
  listMeals,
  MEAL_LABEL,
  MEAL_ORDER,
  type Meal,
  type MealType,
  type SchoolSource,
} from "@/lib/meals";

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

/**
 * 급식표. 달력으로 한 달을 보여주고, 날짜를 누르면 그날 메뉴가 펼쳐진다.
 *
 * 끼니 탭은 **그 달에 실제로 있는 끼니만** 만든다. 학교마다 다르고
 * (서울고는 중식·석식만 있다), 없는 탭을 눌러 빈 화면을 보게 할 이유가 없다.
 */
export function MealCalendar() {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [meals, setMeals] = useState<Meal[]>([]);
  const [type, setType] = useState<MealType>("LUNCH");
  const [picked, setPicked] = useState<string | null>(null);
  const [error, setError] = useState("");
  // 어느 달을 다 불러왔는지로 로딩을 판단한다. effect 본문에서 곧바로
  // setState 하면 렌더가 연쇄로 도는 패턴이라 린트가 막는다.
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const [source, setSource] = useState<SchoolSource | null>(null);
  const key = `${year}-${month}`;
  const loading = loadedKey !== key;

  const load = useCallback(
    () =>
      listMeals(year, month)
        .then((rows) => {
          setMeals(rows);
          setPicked(null);
          setError("");
          setLoadedKey(`${year}-${month}`);
          // 지금 고른 끼니가 이 달에 없으면 있는 것으로 옮긴다.
          const kinds = MEAL_ORDER.filter((k) => rows.some((r) => r.type === k));
          if (kinds.length && !kinds.includes(type)) setType(kinds[0]);
        })
        .catch((e) => {
          setError(e instanceof Error ? e.message : String(e));
          setLoadedKey(`${year}-${month}`);
        }),
    // type 은 의도적으로 뺐다 — 끼니를 바꿀 때마다 다시 불러올 이유가 없다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [year, month],
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    getSchoolSource()
      .then(setSource)
      .catch(() => setSource(null));
  }, []);

  function move(step: number) {
    const next = new Date(year, month - 1 + step, 1);
    setYear(next.getFullYear());
    setMonth(next.getMonth() + 1);
  }

  const kinds = MEAL_ORDER.filter((k) => meals.some((m) => m.type === k));
  const ofType = new Map(meals.filter((m) => m.type === type).map((m) => [m.date, m]));

  const firstWeekday = new Date(year, month - 1, 1).getDay();
  const dayCount = new Date(year, month, 0).getDate();
  const cells: (number | null)[] = [
    ...Array<null>(firstWeekday).fill(null),
    ...Array.from({ length: dayCount }, (_, i) => i + 1),
  ];

  const pickedMeal = picked ? ofType.get(picked) : undefined;

  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => move(-1)}
          className="rounded px-2 py-1 text-sm text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-900"
        >
          ‹
        </button>
        <p className="text-sm font-medium">
          {year}년 {month}월
        </p>
        <button
          type="button"
          onClick={() => move(1)}
          className="rounded px-2 py-1 text-sm text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-900"
        >
          ›
        </button>
      </header>

      {kinds.length > 1 && (
        <div className="flex gap-1">
          {kinds.map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => {
                setType(k);
                setPicked(null);
              }}
              className={`flex-1 rounded px-3 py-1.5 text-xs transition-colors ${
                type === k
                  ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
                  : "border border-neutral-300 text-neutral-500 dark:border-neutral-700"
              }`}
            >
              {MEAL_LABEL[k]}
            </button>
          ))}
        </div>
      )}

      {loading && <p className="font-mono text-xs text-neutral-500">불러오는 중…</p>}

      {!loading && (
        <>
          <div className="grid grid-cols-7 gap-1 text-center">
            {WEEKDAYS.map((w, i) => (
              <span
                key={w}
                className={`py-1 text-xs ${
                  i === 0 ? "text-red-500" : "text-neutral-500"
                }`}
              >
                {w}
              </span>
            ))}

            {cells.map((day, i) => {
              if (day === null) return <span key={`b${i}`} />;
              const date = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
              const has = ofType.has(date);
              const isPicked = picked === date;
              return (
                <button
                  key={date}
                  type="button"
                  disabled={!has}
                  onClick={() => setPicked(isPicked ? null : date)}
                  className={`aspect-square rounded text-xs transition-colors ${
                    isPicked
                      ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
                      : has
                        ? "border border-neutral-300 hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-900"
                        : "text-neutral-300 dark:text-neutral-700"
                  }`}
                >
                  {day}
                </button>
              );
            })}
          </div>

          {pickedMeal ? (
            <div className="flex flex-col gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800">
              <p className="text-xs text-neutral-500">
                {picked} · {MEAL_LABEL[pickedMeal.type]}
                {pickedMeal.calorie !== null && ` · ${pickedMeal.calorie} kcal`}
              </p>
              <ul className="flex flex-col gap-1 text-sm">
                {pickedMeal.dishes.map((dish) => (
                  <li key={dish}>{dish}</li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-xs leading-relaxed text-neutral-500">
              {ofType.size === 0
                ? "이 달에는 급식 정보가 없습니다. 방학이거나 아직 올라오지 않았습니다."
                : "날짜를 누르면 그날 메뉴가 보입니다."}
            </p>
          )}
        </>
      )}

      {error && (
        <p className="font-mono text-xs break-all text-red-700 dark:text-red-400">
          {error}
        </p>
      )}

      {/*
        다른 학교 정보를 빌려 쓰는 조직에만 출처를 밝힌다. 공개 데이터지만
        아무 설명 없이 "우리 학교 급식"으로 읽히면 사실과 다르다.
        실제 학교 소속에게는 자기 학교 급식이므로 이 문구가 오히려 혼란스럽다.
      */}
      {source?.borrowed && (
        <p className="border-t border-neutral-200 pt-3 text-xs leading-relaxed text-neutral-500 dark:border-neutral-800">
          급식 정보는 {source.infoSchoolName}의 공개 데이터(NEIS 교육정보
          개방포털)입니다.
        </p>
      )}
    </div>
  );
}
