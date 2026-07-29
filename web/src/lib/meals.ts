import { createClient } from "./supabase/client";

/**
 * 급식표.
 *
 * NEIS 인증키는 서버 비밀이라 브라우저가 직접 부를 수 없다. 수집기가 미리
 * 받아둔 것을 읽는다(db/neis_meals.py). 어느 학교 것을 보게 되는지는 RLS 가
 * 정한다 — 테스트 조직은 실제 학교(서울고)의 급식을 빌려 본다.
 * (db/rls/school_info.sql)
 */

export type MealType = "BREAKFAST" | "LUNCH" | "DINNER";

export const MEAL_LABEL: Record<MealType, string> = {
  BREAKFAST: "아침",
  LUNCH: "점심",
  DINNER: "저녁",
};

/** 화면에 보여줄 순서. 학교에 없는 끼니는 탭에 나오지 않는다. */
export const MEAL_ORDER: MealType[] = ["BREAKFAST", "LUNCH", "DINNER"];

export type Meal = {
  /** YYYY-MM-DD */
  date: string;
  type: MealType;
  calorie: number | null;
  dishes: string[];
};

type MealRow = {
  serve_date: string;
  meal_type: MealType;
  calorie_kcal: number | string | null;
  meal_menu_item: { dish_name: string; sort_order: number }[];
};

/** 그 달의 급식을 한 번에 가져온다. 한 달이면 많아야 100행 남짓이다. */
export async function listMeals(year: number, month: number): Promise<Meal[]> {
  const first = `${year}-${String(month).padStart(2, "0")}-01`;
  const lastDay = new Date(year, month, 0).getDate();
  const last = `${year}-${String(month).padStart(2, "0")}-${lastDay}`;

  const supabase = createClient();
  const { data, error } = await supabase
    .from("meal_plan")
    .select("serve_date, meal_type, calorie_kcal, meal_menu_item(dish_name, sort_order)")
    .gte("serve_date", first)
    .lte("serve_date", last)
    .order("serve_date")
    .returns<MealRow[]>();

  if (error) throw error;

  return (data ?? []).map((row) => ({
    date: row.serve_date,
    type: row.meal_type,
    calorie: row.calorie_kcal === null ? null : Number(row.calorie_kcal),
    dishes: [...(row.meal_menu_item ?? [])]
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((d) => d.dish_name),
  }));
}

export type SchoolSource = {
  schoolName: string;
  infoSchoolName: string;
  /** 다른 학교의 정보를 빌려 쓰는가 */
  borrowed: boolean;
};

/**
 * 내 학교가 어디 정보를 쓰는지.
 *
 * 빌려 쓰는 조직(테스트 조직)에만 출처 문구를 띄우기 위해 필요하다.
 * 실제 학교 소속에게는 "OO고등학교 공개 데이터"가 오히려 혼란스럽다.
 */
export async function getSchoolSource(): Promise<SchoolSource | null> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("my_school_source")
    .select("school_name, info_school_name, borrowed")
    .maybeSingle();

  if (error) throw error;
  if (!data) return null;
  return {
    schoolName: data.school_name,
    infoSchoolName: data.info_school_name,
    borrowed: data.borrowed,
  };
}
