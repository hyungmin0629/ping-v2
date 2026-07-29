import { createClient } from "./supabase/client";

/** 단계마다 올린다. user_session.app_version 이 varchar(20) 이라 짧게 유지한다. */
const APP_VERSION = "w5";

/**
 * 접속 기록을 남긴다.
 *
 * 리텐션을 추정이 아니라 실측하려면 "언제 켰는가"가 실제로 쌓여야 한다.
 * 시각은 서버가 찍는다 — 클라이언트가 정할 수 있으면 지표가 통째로 오염된다.
 * 30분 안의 재접속은 같은 세션으로 묶인다. (db/rls/session_log.sql)
 *
 * 실패해도 화면을 막지 않는다. 로그를 못 남기는 것이 서비스를 못 쓰는 것보다 낫다.
 */
export async function touchSession(): Promise<void> {
  try {
    const supabase = createClient();
    await supabase.rpc("touch_session", {
      p_platform: "WEB",
      p_app_version: APP_VERSION,
    });
  } catch {
    // 무시한다
  }
}
