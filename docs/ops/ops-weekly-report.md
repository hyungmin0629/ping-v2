---
title: 주간 보고서 — 한 번 설정하고 매주 자동으로 받는다
date: 2026-08-25
group: 운영
status: active
tags: [운영, 보고서, 파이프라인, Drive]
---

# 주간 보고서

매주 월요일 아침, 지난주(월~일)의 3쪽짜리 PDF 가 Google Drive 폴더에 쌓인다.
사람이 할 일은 **처음 한 번의 설정뿐**이다.

> 폴더: [PING 주간보고서](https://drive.google.com/drive/folders/1li2Y9wfc65yUT08lyod7Xq7xU1us3fma)

실행 위치를 왜 CI 로 정했는지는 [[weekly-report-runs-in-ci]],
작은 표본을 어떻게 다루는지는 [[weekly-report-suppresses-small-denominators]].

---

## 무엇이 어떤 순서로 도는가

```
월요일 05:30 KST  (GitHub Actions · .github/workflows/weekly-report.yml)
  ① pipeline/extract_load.py    Supabase → BigQuery raw (증분)
  ② pipeline/verify_load.py     행 수 대조 — 증분은 조용히 틀린다
  ③ qa/quality_check.py         최근 9일치 필수값·시각 검증
  ④ bigquery/build.py --layer mart
  ⑤ report/collect.py           mart → JSON  (스캔 0.18 GiB)
  ⑥ report/render.py            JSON → HTML → PDF
  ⑦ report/deliver.py           PDF → Drive 폴더
```

층이 나뉜 이유는 하나다 — **숫자가 이상할 때 어디가 틀렸는지 알기 위해서.**
JSON 만 열어보면 그림을 뜯어보지 않아도 된다.

| 층 | 파일 | 고칠 일이 생기면 |
|---|---|---|
| 숫자 | `report/queries/*.sql` · `collect.py` | 지표의 정의가 바뀔 때 |
| 그림 | `report/template/weekly.html` · `charts.py` · `render.py` | 배치·색·문구 |
| 배송 | `report/deliver.py` | 폴더·파일명·권한 |

---

## 처음 한 번만 — 설정 (약 10분)

### 1. Drive 폴더를 팀원에게 공유한다

폴더는 이미 만들어져 있다(위 링크). 열어서 **공유 → 사람 추가**로 팀원
Gmail 계정을 뷰어로 넣는다. 파일은 매주 이 폴더 안에 생기고 폴더의 공유
설정을 그대로 물려받는다.

### 2. OAuth 클라이언트를 만든다

⚠️ **서비스 계정(`credentials.json`)으로는 Drive 에 못 올린다.** 서비스
계정은 개인 드라이브 저장 할당량이 없어서 업로드가 `storageQuotaExceeded`
로 떨어진다. 그래서 **본인 계정 토큰**을 쓴다.

[console.cloud.google.com](https://console.cloud.google.com) → 프로젝트
`ping-v2-503916` 에서:

1. **API 및 서비스 → 라이브러리** → `Google Drive API` 검색 → **사용 설정**
2. **API 및 서비스 → OAuth 동의 화면** → 만들고 나서 **`앱 게시`(프로덕션)** 를 누른다
   - ⚠️ **여기가 제일 잘 걸리는 곳이다.** '테스트' 상태로 두면 리프레시 토큰이
     **7일 만에 만료**된다. 일주일은 잘 되다가 갑자기 멈추는 원인이 이것이다.
3. **사용자 인증 정보 → 사용자 인증 정보 만들기 → OAuth 클라이언트 ID**
   → 유형 **데스크톱 앱** → 만들고 **JSON 다운로드**
4. 받은 파일을 저장소 루트에 `client_secret.json` 으로 둔다(.gitignore 됨)

### 3. 토큰을 발급한다 (로컬에서 한 번)

```
.venv\Scripts\python.exe report/gdrive_auth.py --client client_secret.json
```

브라우저가 열린다. 본인 계정으로 로그인하고 허용하면 끝이다.
화면에 **GitHub Secrets 에 넣을 한 줄**이 찍힌다.

### 4. GitHub Secrets 에 넣는다

저장소 → **Settings → Secrets and variables → Actions → New repository secret**

| 이름 | 값 |
|---|---|
| `GDRIVE_TOKEN_JSON` | 3번에서 찍힌 한 줄 |
| `GCP_SA_KEY` | `credentials.json` 파일 내용 전체 |
| `SUPABASE_DB_URL` | `.env` 의 같은 값 (퍼센트 인코딩된 상태 그대로) |

폴더 ID 는 워크플로에 이미 박혀 있다. 폴더를 바꾸려면 같은 화면의
**Variables** 탭에 `GDRIVE_WEEKLY_FOLDER_ID` 를 넣으면 그쪽이 이긴다.

### 5. 손으로 한 번 돌려본다

저장소 → **Actions → 주간 보고서 → Run workflow**.
초록불이 뜨고 Drive 폴더에 PDF 가 생기면 설정이 끝난 것이다.
이후로는 매주 월요일에 저절로 돈다.

---

## 평소에 하는 일 — 없다

보고서가 안 왔다면 그 자체가 신호다. 확인 순서:

1. **메일함** — 워크플로가 실패하면 GitHub 이 저장소 소유자에게 메일을 보낸다.
2. **Actions 탭** — 어느 단계에서 멈췄는지 로그가 남는다.
3. 실패한 단계별 뜻:

| 멈춘 곳 | 뜻 | 할 일 |
|---|---|---|
| 적재 / 적재 대조 | Supabase 접속 실패 또는 행 수 불일치 | 비밀번호 만료·풀러 주소 확인([[supabase-session-pooler]]) |
| 품질 검증 | 최근 9일 데이터에 위반 | 위반 내용이 로그에 찍힌다. 마트를 굽지 않고 멈춘다 |
| Drive 업로드 | 토큰 만료 | 동의 화면이 '테스트'로 돌아갔는지 확인 → 3번 다시 |

⚠️ **PDF 는 실패해도 Actions 산출물(Artifacts)에 90일간 남는다.** 업로드만
실패한 주는 거기서 내려받으면 된다.

⚠️ **저장소가 60일간 조용하면 GitHub 이 스케줄을 끈다.** 끄기 전에 메일이
온다. 그때 Actions 탭에서 다시 켜면 된다.

---

## 손으로 돌리고 싶을 때

로컬에서 한 단계씩(전부 `.venv`):

```
python report/collect.py --week 2026-08-17
python report/render.py
python report/deliver.py
```

`--source local` 을 주면 합성 데이터로 같은 보고서가 나온다 — 유저가 많을 때
보고서가 어떤 모양인지 보고 싶을 때 쓴다.

Actions 에서 특정 주를 다시 뽑으려면 **Run workflow** 의 `week` 칸에 날짜를
넣는다. 마트가 이미 최신이면 `skip_pipeline` 을 켜서 ①~④를 건너뛴다.

---

## 보고서에 무엇이 실리나

| 쪽 | 내용 | 읽는 마트 |
|---|---|---|
| 1 | WAU · 참여율 · W2 리텐션 · 신규 · 매출 · 미처리 신고 / 8주 추이 / 전주 대비 / 핵심 요약 | `mart_user_activity` · `mart_daily` · `mart_user` |
| 2 | Activation 퍼널 · 수신→이름공개 퍼널 · 첫 투표 코호트 · 세그먼트 | `mart_funnel_step` · `mart_user` |
| 3 | 매출 4종 · 하트 유입/소비 · 적체 추이 · 신고 알림 | `mart_heart_flow` · `mart_report` · `mart_daily` |

⚠️ **`raw` 는 읽지 않는다.** `collect.py` 가 실행 전에 예상 스캔량을 재고
상한(5 GiB)을 넘으면 **한 줄도 실행하지 않고** 멈춘다. 실측 0.18 GiB.

⚠️ 1쪽의 '10문항' 막대만 **단위가 세션(건)** 이다. 나머지는 사람 수다.
`mart_distribution` 의 '문항 도달'이 세션 그레인이라 그렇다 — 라벨에 (건)을 박아 뒀다.

⚠️ 매출은 `is_revenue` 만 센다. MVP 충전 버튼은 스텁이라 하트만 들어오고
돈은 오지 않는다. 3쪽에서 스텁 건수는 따로 적힌다.
