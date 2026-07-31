import { createClient } from "./supabase/client";

/**
 * 학사일정 (W16).
 *
 * 급식과 같은 자리에서 온다 — 수집기가 NEIS 에서 미리 받아두고
 * (db/neis_events.py), 앱은 RLS 를 통해 자기 학교 것만 읽는다.
 * 테스트 조직은 서울고의 일정을 빌려 본다. (db/rls/school_info.sql)
 *
 * NEIS 는 하루씩 주지만 DB 에는 **기간으로 묶여** 들어 있다. 여름방학이
 * 29개 행으로 오면 달력이 방학으로 도배되기 때문이다. 그래서 여기서는
 * 기간을 다시 날짜로 펼쳐 어느 날에 무엇이 걸리는지 만든다.
 */

export type EventKind = "HOLIDAY" | "EXAM" | "CEREMONY" | "FIELD_TRIP" | "ETC";

export const EVENT_LABEL: Record<EventKind, string> = {
  HOLIDAY: "휴업",
  EXAM: "시험",
  CEREMONY: "행사",
  FIELD_TRIP: "체험",
  ETC: "일정",
};

/**
 * 종류별 색. 휴업일은 빨강 — 달력에서 쉬는 날을 먼저 찾기 때문이다.
 * 나머지는 서로 구별만 되면 되므로 눈에 덜 띄는 색을 쓴다.
 */
export const EVENT_COLOR: Record<EventKind, string> = {
  HOLIDAY: "bg-red-500",
  EXAM: "bg-amber-500",
  CEREMONY: "bg-violet-500",
  FIELD_TRIP: "bg-emerald-500",
  ETC: "bg-neutral-400",
};

export type SchoolEvent = {
  id: number;
  title: string;
  kind: EventKind;
  /** YYYY-MM-DD */
  start: string;
  end: string;
  /** 특정 학년만 해당하면 그 학년, 전교면 null */
  grade: number | null;
};

type EventRow = {
  id: number;
  title: string;
  event_type: EventKind;
  start_date: string;
  end_date: string;
  grade_scope: number | null;
};

/**
 * 그 달에 걸치는 일정을 가져온다.
 *
 * 시작·끝이 달을 넘는 일정도 잡아야 한다 — 7월 23일에 시작해 8월 2일에
 * 끝나는 체험학습은 8월 달력에도 나와야 한다. 그래서 "이 달 안에 시작"이
 * 아니라 "이 달과 겹침"으로 찾는다.
 */
export async function listEvents(year: number, month: number): Promise<SchoolEvent[]> {
  const first = `${year}-${String(month).padStart(2, "0")}-01`;
  const lastDay = new Date(year, month, 0).getDate();
  const last = `${year}-${String(month).padStart(2, "0")}-${lastDay}`;

  const supabase = createClient();
  const { data, error } = await supabase
    .from("school_event")
    .select("id, title, event_type, start_date, end_date, grade_scope")
    .lte("start_date", last)
    .gte("end_date", first)
    .order("start_date")
    .returns<EventRow[]>();

  if (error) throw error;
  return (data ?? []).map((r) => ({
    id: r.id,
    title: r.title,
    kind: r.event_type,
    start: r.start_date,
    end: r.end_date,
    grade: r.grade_scope,
  }));
}

/**
 * 날짜 → 그날 걸리는 일정들.
 *
 * 기간 일정은 하루씩 펼쳐 넣는다. 달력 칸이 자기 날짜만 보고
 * 표시를 정할 수 있어야 하기 때문이다.
 */
export function byDate(events: SchoolEvent[]): Map<string, SchoolEvent[]> {
  const map = new Map<string, SchoolEvent[]>();
  for (const event of events) {
    for (const day of daysOf(event)) {
      const list = map.get(day);
      if (list) list.push(event);
      else map.set(day, [event]);
    }
  }
  return map;
}

function daysOf(event: SchoolEvent): string[] {
  const days: string[] = [];
  const end = new Date(`${event.end}T00:00:00`);
  for (
    let d = new Date(`${event.start}T00:00:00`);
    d <= end;
    d.setDate(d.getDate() + 1)
  ) {
    days.push(
      `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
        d.getDate(),
      ).padStart(2, "0")}`,
    );
  }
  return days;
}

/** "7월 3일" 또는 "7월 3일 ~ 7월 6일" */
export function formatSpan(event: SchoolEvent): string {
  const show = (iso: string) => {
    const [, m, d] = iso.split("-");
    return `${Number(m)}월 ${Number(d)}일`;
  };
  return event.start === event.end
    ? show(event.start)
    : `${show(event.start)} ~ ${show(event.end)}`;
}
