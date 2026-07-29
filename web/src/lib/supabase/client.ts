import { createBrowserClient } from "@supabase/ssr";

/**
 * 브라우저에서 쓰는 Supabase 클라이언트.
 *
 * 여기 들어가는 anon 키는 웹페이지 소스에 그대로 노출된다. 숨길 수 없는 값이다.
 * 그래서 데이터 보호는 이 키가 아니라 DB의 RLS 정책이 담당한다.
 * (db/rls/policies.sql, 검증은 db/rls/verify.py)
 *
 * service_role 키는 RLS를 통째로 무시하므로 절대 이 파일 근처에 두지 않는다.
 */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
