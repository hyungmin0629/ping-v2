"""
주간 보고서 · Drive 토큰 **한 번만** 발급한다.

    python report/gdrive_auth.py --client client_secret.json

브라우저가 열리고 구글 로그인·동의를 한 번 하면 끝이다. 그 뒤로는 이 명령을
다시 칠 일이 없다 — 리프레시 토큰으로 사람 없이 갱신된다.

⚠️ **동의 화면을 '테스트'로 두면 리프레시 토큰이 7일 만에 만료된다.**
   Google Cloud 콘솔 → API 및 서비스 → OAuth 동의 화면에서 **'앱 게시'
   (프로덕션)** 를 눌러야 무인 실행이 유지된다. 이걸 안 해서 "일주일은
   되다가 갑자기 멈추는" 일이 흔하다.

⚠️ 발급된 토큰은 **비밀이다.** `report/.gdrive_token.json` 은 .gitignore
   에 들어 있다. GitHub Actions 용 한 줄 문자열도 함께 찍어 준다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOKEN_FILE = HERE / ".gdrive_token.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--client", default=None,
                    help="콘솔에서 받은 OAuth 클라이언트 JSON 경로. "
                         "없으면 저장소 루트의 client_secret*.json 을 찾는다")
    args = ap.parse_args()

    if args.client:
        client = Path(args.client)
    else:
        # 콘솔이 주는 파일 이름은 client_secret_1234-....apps.googleusercontent.com.json
        # 처럼 길다. 받은 그대로 폴더에 두게 두고 **스크립트가 찾는다** —
        # 이름을 바꾸라고 시키면 거기서 한 번 더 틀린다.
        found = sorted(ROOT.glob("client_secret*.json"))
        if len(found) > 1:
            names = "\n  ".join(f.name for f in found)
            sys.exit(f"client_secret*.json 이 여러 개입니다. --client 로 하나를 고르세요:\n  {names}")
        client = found[0] if found else ROOT / "client_secret.json"

    if not client.exists():
        sys.exit(
            f"OAuth 클라이언트 파일을 못 찾았습니다 (찾은 곳: {ROOT})\n"
            "Google Cloud 콘솔 → Google 인증 플랫폼 → 클라이언트 →\n"
            "  'OAuth 클라이언트 만들기' → 유형 **데스크톱 앱** → JSON 다운로드\n"
            "받은 파일을 **이름 그대로** 저장소 루트에 두고 다시 실행하세요.\n"
            "자세한 절차는 docs/ops/ops-weekly-report.md"
        )

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(client), SCOPES)
    # access_type=offline + prompt=consent 여야 **리프레시 토큰이 온다.**
    # 이미 동의한 계정은 prompt 없이는 리프레시 토큰을 다시 주지 않는다.
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    print(f"✅ 토큰을 저장했습니다 → {TOKEN_FILE}")

    if not creds.refresh_token:
        print("⚠️ 리프레시 토큰이 없습니다. 계정 권한을 지우고 다시 실행하세요.")
        return 1

    one_line = json.dumps(json.loads(creds.to_json()), ensure_ascii=False, separators=(",", ":"))
    print("\n──────────────────────────────────────────────────────────")
    print("GitHub Secrets 에 넣을 값 (이름: GDRIVE_TOKEN_JSON)")
    print("──────────────────────────────────────────────────────────")
    print(one_line)
    print("──────────────────────────────────────────────────────────")
    print("저장소 → Settings → Secrets and variables → Actions → New repository secret")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
