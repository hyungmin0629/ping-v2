import type { Session } from "@supabase/supabase-js";
import { createClient } from "./client";

/**
 * 익명 세션을 확보한다.
 *
 * 이 서비스는 아이디·비밀번호·이메일을 받지 않는다. 접속하면 계정이 생긴다.
 * 세션은 브라우저에 저장되므로 새로고침해도 같은 계정이 유지된다.
 *
 * 저장된 세션을 그대로 믿지 않고 서버에 한 번 확인한다.
 * 서버에서 계정이 지워졌는데(예: 개발 중 초기화) 브라우저에는 토큰이 남아 있으면,
 * 모든 조회가 401 로 깨지면서 원인을 찾기 어려운 상태가 된다.
 * 그럴 때는 조용히 새 익명 계정을 만든다.
 *
 * 알려진 한계: 브라우저 저장소를 지우면 계정을 잃는다.
 * MVP 에서는 감수하고 안내 문구로 알린다(복구 코드는 v2).
 */
export async function ensureAnonymousSession(): Promise<Session> {
  const supabase = createClient();

  const { data: cached } = await supabase.auth.getSession();
  if (cached.session) {
    // 토큰이 서버에서도 유효한지 확인한다
    const { error } = await supabase.auth.getUser();
    if (!error) return cached.session;
    await supabase.auth.signOut();
  }

  const { data, error } = await supabase.auth.signInAnonymously();
  if (error) throw error;
  if (!data.session) throw new Error("세션이 발급되지 않았습니다");

  return data.session;
}
