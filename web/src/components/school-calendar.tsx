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
import {
  byDate,
  formatSpan,
  listEvents,
  EVENT_COLOR,
  EVENT_LABEL,
  type SchoolEvent,
} from "@/lib/school-events";

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

/**
 * 급식표 + 학사일정 (W8 · W16).
 *
 * 둘을 한 달력에 얹는다. 학사일정을 따로 두지 않은 이유는 **둘이 서로를
 * 설명하기 때문**이다 — 급식이 없는 날은 대개 방학이나 휴업일이고, 그
 * 이유가 같은 화면에 있어야 "왜 이 날은 비었나"에 답이 된다.
 *
 * 날짜 칸 아래 점이 그날의 일정이다. 날짜를 누르면 그날 일정과 메뉴가
 * 함께 펼쳐지고, 달력 아래에는 그 달 일정이 통째로 나온다 — 대부분의 날은
 * 일정이 없어서, 눌러가며 찾게 두면 못 찾는다.
 */
export function SchoolCalendar() {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [meals, setMeals] = useState<Meal[]>([]);
  const [events, setEvents] = useState<SchoolEvent[]>([]);
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
      Promise.all([listMeals(year, month), listEvents(year, month)])
        .then(([mealRows, eventRows]) => {
          setMeals(mealRows);
          setEvents(eventRows);
          setPicked(null);
          setError("");
          setLoadedKey(`${year}-${month}`);
          // 지금 고른 끼니가 이 달에 없으면 있는 것으로 옮긴다.
          const kinds = MEAL_ORDER.filter((k) => mealRows.some((r) => r.type === k));
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
  const eventsOn = byDate(events);

  const firstWeekday = new Date(year, month - 1, 1).getDay();
  const dayCount = new Date(year, month, 0).getDate();
  const cells: (number | null)[] = [
    ...Array<null>(firstWeekday).fill(null),
    ...Array.from({ length: dayCount }, (_, i) => i + 1),
  ];

  const pickedMeal = picked ? ofType.get(picked) : undefined;
  const pickedEvents = picked ? (eventsOn.get(picked) ?? []) : [];

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
              const meal = ofType.has(date);
              const onDay = eventsOn.get(date) ?? [];
              // 급식이 없어도 일정이 있으면 누를 수 있어야 한다 —
              // 방학·시험처럼 정작 궁금한 날에 급식이 없다.
              const has = meal || onDay.length > 0;
              const isPicked = picked === date;
              return (
                <button
                  key={date}
                  type="button"
                  disabled={!has}
                  onClick={() => setPicked(isPicked ? null : date)}
                  className={`flex aspect-square flex-col items-center justify-center gap-1 rounded text-xs transition-colors ${
                    isPicked
                      ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
                      : has
                        ? "border border-neutral-300 hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-900"
                        : "text-neutral-300 dark:text-neutral-700"
                  }`}
                >
                  <span className={meal ? "" : "opacity-60"}>{day}</span>
                  {/* 점 세 개까지만. 그 이상은 칸을 넘고, 세어봐야 알 수 없다 */}
                  <span className="flex h-1 gap-0.5">
                    {onDay.slice(0, 3).map((e) => (
                      <span
                        key={e.id}
                        className={`h-1 w-1 rounded-full ${EVENT_COLOR[e.kind]}`}
                      />
                    ))}
                  </span>
                </button>
              );
            })}
          </div>

          {picked ? (
            <div className="flex flex-col gap-3 rounded border border-neutral-200 p-4 dark:border-neutral-800">
              <p className="text-xs text-neutral-500">{picked}</p>

              {pickedEvents.length > 0 && (
                <ul className="flex flex-col gap-1.5 text-sm">
                  {pickedEvents.map((e) => (
                    <li key={e.id} className="flex items-center gap-2">
                      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${EVENT_COLOR[e.kind]}`} />
                      <span>{e.title}</span>
                      {e.grade !== null && (
                        <span className="text-xs text-neutral-500">{e.grade}학년</span>
                      )}
                      {e.start !== e.end && (
                        <span className="text-xs text-neutral-500">{formatSpan(e)}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}

              {pickedMeal ? (
                <div className="flex flex-col gap-1">
                  {pickedEvents.length > 0 && (
                    <p className="mt-1 border-t border-neutral-200 pt-3 text-xs text-neutral-500 dark:border-neutral-800">
                      {MEAL_LABEL[pickedMeal.type]}
                      {pickedMeal.calorie !== null && ` · ${pickedMeal.calorie} kcal`}
                    </p>
                  )}
                  {pickedEvents.length === 0 && (
                    <p className="text-xs text-neutral-500">
                      {MEAL_LABEL[pickedMeal.type]}
                      {pickedMeal.calorie !== null && ` · ${pickedMeal.calorie} kcal`}
                    </p>
                  )}
                  <ul className="flex flex-col gap-1 text-sm">
                    {pickedMeal.dishes.map((dish) => (
                      <li key={dish}>{dish}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="text-xs text-neutral-500">이 날은 급식이 없습니다.</p>
              )}
            </div>
          ) : (
            <p className="text-xs leading-relaxed text-neutral-500">
              {ofType.size === 0 && events.length === 0
                ? "이 달에는 급식도 학사일정도 없습니다. 아직 올라오지 않았습니다."
                : "날짜를 누르면 그날 일정과 메뉴가 보입니다."}
            </p>
          )}

          {/* 그 달 일정 전체. 대부분의 날은 비어 있어서 눌러 찾게 두면 못 찾는다 */}
          {events.length > 0 && (
            <section className="flex flex-col gap-2 border-t border-neutral-200 pt-4 dark:border-neutral-800">
              <h4 className="text-xs font-medium text-neutral-500">
                {month}월 학사일정
              </h4>
              <ul className="flex flex-col gap-1.5">
                {events.map((e) => (
                  <li key={e.id} className="flex items-baseline gap-2 text-sm">
                    <span
                      className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${EVENT_COLOR[e.kind]}`}
                    />
                    <span className="shrink-0 font-mono text-xs text-neutral-500">
                      {formatSpan(e)}
                    </span>
                    <span className="min-w-0">
                      {e.title}
                      {e.grade !== null && (
                        <span className="ml-1 text-xs text-neutral-500">
                          {e.grade}학년
                        </span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-neutral-500">
                {(Object.keys(EVENT_LABEL) as (keyof typeof EVENT_LABEL)[]).map((k) => (
                  <span key={k} className="flex items-center gap-1">
                    <span className={`h-1.5 w-1.5 rounded-full ${EVENT_COLOR[k]}`} />
                    {EVENT_LABEL[k]}
                  </span>
                ))}
              </p>
            </section>
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
          급식·학사일정은 {source.infoSchoolName}의 공개 데이터(NEIS 교육정보
          개방포털)입니다.
        </p>
      )}
    </div>
  );
}
