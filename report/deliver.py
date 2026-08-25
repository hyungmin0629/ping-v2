"""
주간 보고서 · ③ 배송 층 — PDF 를 지정 Google Drive 폴더에 올린다.

    python report/deliver.py                                   # 가장 최근 PDF
    python report/deliver.py --file report/out/PING-weekly-2026-08-17.pdf
    python report/deliver.py --dry-run                         # 올리지 않고 점검만

──────────────────────────────────────────────────────────────────────
⚠️ **서비스 계정(`credentials.json`)으로는 못 올린다.**

서비스 계정은 개인 드라이브 저장 할당량이 없다. 폴더를 공유해 줘도
업로드가 `storageQuotaExceeded` 로 떨어진다 — 파일 소유자가 서비스 계정이
되는데, 그 계정에는 담을 공간이 없기 때문이다. 공유 드라이브(Workspace)가
있으면 되지만 개인 Gmail 에는 없다.

그래서 **본인 계정 OAuth 리프레시 토큰**을 쓴다. 발급은 `gdrive_auth.py`
가 한 번만 하고, 그 뒤로는 사람 없이 갱신된다.

⚠️ 토큰은 두 곳 중 하나에서 읽는다.
    ① 환경변수 `GDRIVE_TOKEN_JSON`  ← GitHub Actions 는 이쪽
    ② 파일 `report/.gdrive_token.json`  ← 로컬은 이쪽 (.gitignore 됨)

⚠️ 권한 범위는 `drive.file` 하나다 — **이 앱이 만든 파일만** 보고 고친다.
   드라이브의 나머지는 읽을 수도 없다. 지난주 PDF 를 찾아 새 버전으로
   덮는 것은 그것도 이 앱이 만든 파일이라 가능하다.
──────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
TOKEN_FILE = HERE / ".gdrive_token.json"

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def load_credentials():
    """리프레시 토큰으로 자격을 만든다. 만료됐으면 조용히 갱신한다."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    raw = os.getenv("GDRIVE_TOKEN_JSON", "").strip()
    if raw:
        info = json.loads(raw)
        source = "환경변수 GDRIVE_TOKEN_JSON"
    elif TOKEN_FILE.exists():
        info = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        source = str(TOKEN_FILE)
    else:
        sys.exit(
            "Drive 토큰이 없습니다.\n"
            "  로컬:   .venv\\Scripts\\python.exe report/gdrive_auth.py\n"
            "  Actions: 저장소 Secrets 에 GDRIVE_TOKEN_JSON 을 넣으세요.\n"
            "  절차는 docs/ops/ops-weekly-report.md"
        )

    creds = Credentials.from_authorized_user_info(info, SCOPES)
    if not creds.valid:
        if not (creds.expired and creds.refresh_token):
            sys.exit(f"토큰이 유효하지 않습니다({source}). gdrive_auth.py 로 다시 발급하세요.")
        creds.refresh(Request())
        # 갱신된 액세스 토큰을 파일에도 반영한다. 환경변수 경로에서는 건너뛴다
        # (CI 의 파일 시스템은 실행이 끝나면 사라진다).
        if not raw:
            TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    print(f"Drive 자격 확인 ({source})")
    return creds


def latest_pdf() -> Path:
    found = sorted(OUT.glob("PING-weekly-*.pdf"))
    if not found:
        sys.exit("report/out 에 PDF 가 없습니다. 먼저 render.py 를 돌리세요.")
    return found[-1]


def upload(path: Path, folder_id: str) -> dict:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = load_credentials()
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    media = MediaFileUpload(str(path), mimetype="application/pdf", resumable=False)

    # 같은 이름이 이미 있으면 **파일을 늘리지 않고 새 버전으로** 올린다.
    # 링크가 유지돼야 "지난주 보고서" 를 가리킨 메모가 안 깨진다.
    q = (f"name = '{path.name}' and '{folder_id}' in parents and trashed = false")
    hit = drive.files().list(q=q, fields="files(id,name)", pageSize=1).execute().get("files", [])

    if hit:
        file_id = hit[0]["id"]
        meta = drive.files().update(
            fileId=file_id, media_body=media,
            fields="id,name,webViewLink,modifiedTime").execute()
        meta["_action"] = "새 버전"
    else:
        meta = drive.files().create(
            body={"name": path.name, "parents": [folder_id]},
            media_body=media,
            fields="id,name,webViewLink,modifiedTime").execute()
        meta["_action"] = "새 파일"
    return meta


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="올릴 PDF. 없으면 report/out 의 가장 최근 것")
    ap.add_argument("--folder", default=os.getenv("GDRIVE_WEEKLY_FOLDER_ID", "").strip())
    ap.add_argument("--dry-run", action="store_true", help="자격과 파일만 확인하고 올리지 않는다")
    args = ap.parse_args()

    path = Path(args.file) if args.file else latest_pdf()
    if not path.exists():
        sys.exit(f"파일이 없습니다: {path}")
    if not args.folder:
        sys.exit("GDRIVE_WEEKLY_FOLDER_ID 가 없습니다 (.env 또는 Actions 환경변수).")

    size_kb = path.stat().st_size / 1024
    print(f"올릴 파일 {path.name} ({size_kb:,.0f} KB) → 폴더 {args.folder}")
    if args.dry_run:
        load_credentials()
        print("(--dry-run) 업로드하지 않았습니다.")
        return 0

    meta = upload(path, args.folder)
    print(f"✅ {meta['_action']}으로 올렸습니다 — {meta['name']}")
    print(f"   {meta.get('webViewLink', '(링크 없음)')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
