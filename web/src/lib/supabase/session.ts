import type { Session } from "@supabase/supabase-js";
import { createClient } from "./client";

/**
 * 익명 세션을 확보한다.
 *
 * 이 서비스는 아이디·비밀번호·이메일을 받지 않는다. 접속하면 계정이 생긴다.
 * 세션은 브라우저에 저장되므로 새로고침해도 같은 계정이 유지된다.
 *
 * 알려진 한계: 브라우저 저장소를 지우면 계정을 잃는다.
 * MVP에서는 감수하고 안내 문구로 알린다(복구 코드는 v2).
 */
export async function ensureAnonymousSession(): Promise<Session> {
  const supabase = createClient();

  const { data: existing } = await supabase.auth.getSession();
  if (existing.session) return existing.session;

  const { data, error } = await supabase.auth.signInAnonymously();
  if (error) throw error;
  if (!data.session) throw new Error("세션이 발급되지 않았습니다");

  return data.session;
}
