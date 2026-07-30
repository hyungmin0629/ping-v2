import { createClient } from "./supabase/client";

/**
 * 하트 충전 (W13).
 *
 * ⚠️ **결제가 없다.** 누르면 그 자리에서 하트가 들어온다. 실결제는 계정 개설과
 * 심사가 필요해 MVP 범위 밖이다. 스키마는 실결제를 전제로 설계돼 있어서
 * 나중에 SDK 를 붙일 때 구조를 바꿀 필요가 없다.
 *
 * 결제가 없으므로 **하루 한 번**이 하트 경제를 지키는 유일한 장치다.
 * 그 판정은 화면이 하지 않는다 — 브라우저 시간대는 이용자가 바꿀 수 있고,
 * 그러면 시간대를 옮기는 것만으로 제한이 뚫린다. (db/rls/topup.sql)
 */

export type HeartProduct = {
  code: string;
  hearts: number;
  price: number;
  label: string | null;
};

export type TopupState = {
  canPurchase: boolean;
  lastPurchasedAt: string | null;
};

export type PurchaseResult = "OK" | "ALREADY_TODAY" | "NOT_FOUND";

export const PURCHASE_MESSAGE: Record<PurchaseResult, string> = {
  OK: "충전했습니다.",
  ALREADY_TODAY: "오늘은 이미 충전했어요. 내일 다시 받을 수 있습니다.",
  NOT_FOUND: "지금은 살 수 없는 상품입니다.",
};

export async function listProducts(): Promise<HeartProduct[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("heart_product")
    .select("product_code, heart_amount, price_krw, label, is_active")
    .eq("is_active", true)
    .order("heart_amount");

  if (error) throw new Error(error.message);
  return (data ?? []).map((r) => ({
    code: r.product_code,
    hearts: r.heart_amount,
    price: r.price_krw,
    label: r.label,
  }));
}

export async function getTopupState(): Promise<TopupState> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("my_topup_state")
    .select("can_purchase, last_purchased_at")
    .maybeSingle();

  if (error) throw new Error(error.message);
  return {
    canPurchase: data?.can_purchase ?? true,
    lastPurchasedAt: data?.last_purchased_at ?? null,
  };
}

export async function purchase(code: string): Promise<PurchaseResult> {
  const supabase = createClient();
  const { data, error } = await supabase.rpc("purchase_hearts", {
    p_product_code: code,
  });
  if (error) throw new Error(error.message);
  return data as PurchaseResult;
}

/** 다음 충전이 열리는 시각. 한국 시간 자정이다. */
export function nextOpenAt(): string {
  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  return tomorrow.toLocaleDateString("ko-KR", { month: "long", day: "numeric" });
}
