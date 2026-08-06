"""팀원용 BigQuery 접속 시험 노트북을 생성한다."""
import json
from pathlib import Path

PROJECT = "ping-v2-503916"
LOC = "asia-northeast3"

cells = []


def md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)})


def code(text):
    cells.append({
        "cell_type": "code", "execution_count": None, "metadata": {},
        "outputs": [], "source": text.strip("\n").splitlines(keepends=True),
    })


md("""
# BigQuery 접속 시험

이 노트북을 **위에서 아래로 한 칸씩** 실행하면 접속이 제대로 됐는지 확인된다.
전부 통과하면 분석을 시작해도 된다.

| | |
|---|---|
| 프로젝트 | `ping-v2-503916` · 리전 `asia-northeast3` |
| 데이터셋 | `raw` — 40개 표 · 1억 2,373만 행 |

자세한 규칙과 주의사항은 **`docs/ops/ops-bigquery-team-access.md`** 에 있다.

> 이 노트북을 전부 실행하면 **0.19 GiB** 를 읽는다. 월 무료 한도(1,024 GiB)의
> **0.02%** 라 몇 번을 돌려도 괜찮다.

---

## 시작 전에 — 터미널에서 한 번만

**① Google Cloud CLI 설치** — <https://cloud.google.com/sdk/docs/install>

**② 본인 계정 인증** (브라우저가 열리면 팀 Gmail 로 로그인)

```
gcloud auth application-default login
```

**③ 요금이 청구될 프로젝트 지정**

```
gcloud auth application-default set-quota-project ping-v2-503916
```

> ⚠️ **`gcloud init` 의 로그인과 ②는 다른 것이다.**
> `gcloud init` 은 gcloud **명령어**가 쓸 로그인이고,
> ②는 **파이썬 라이브러리**가 쓸 자격증명이다. 둘 다 해야 한다.
""")

md("""
## 0. 패키지 확인

없으면 아래 주석을 풀어 한 번 실행한다.
""")

code("""
# !pip install google-cloud-bigquery google-cloud-bigquery-storage db-dtypes pandas

import google.auth
import pandas as pd
from google.cloud import bigquery

print("google-cloud-bigquery", bigquery.__version__)
print("pandas              ", pd.__version__)
""")

md("""
## 1. 누구로 접속하는가

**여기서 걸러야 할 것이 있다.** 아래가 `서비스 계정` 으로 나오면 누군가에게 받은
**키 파일을 쓰고 있다는 뜻**이다. 그러면 모든 쿼리가 그 계정이 한 것으로 기록돼
누가 무엇을 했는지 사라진다. `사용자 계정` 이 나와야 정상이다.
""")

code("""
creds, detected_project = google.auth.default()
kind = type(creds).__module__

if "service_account" in kind:
    print("[!] 서비스 계정 (키 파일)")
    print("    ", getattr(creds, "service_account_email", "?"))
    print()
    print("    분석에는 이 경로를 쓰지 않는다.")
    print("    터미널에서 아래를 실행해 본인 계정으로 바꾼다:")
    print("      gcloud auth application-default login")
    print("      gcloud auth application-default set-quota-project ping-v2-503916")
else:
    print("[o] 사용자 계정 (본인 Google 로그인) - 정상")

print()
print("자동 감지된 프로젝트 :", detected_project)
print("요금 청구 프로젝트   :", getattr(creds, "quota_project_id", None))
""")

md("""
### 요금 청구 프로젝트가 `None` 이면

위 ③ 명령을 안 한 것이다. 터미널에서 실행하고 **커널을 다시 시작**한다.

```
gcloud auth application-default set-quota-project ping-v2-503916
```
""")

md("""
## 2. 접속

여기서 오류가 안 나면 권한까지 정상이다.
""")

code(f"""
PROJECT = "{PROJECT}"
LOCATION = "{LOC}"

bq = bigquery.Client(project=PROJECT, location=LOCATION)

tables = list(bq.list_tables(f"{{PROJECT}}.raw"))
rows = sum(bq.get_table(t).num_rows for t in tables)
print(f"raw 데이터셋 : 표 {{len(tables)}}개 · {{rows:,}}행")
""")

md("""
## 3. 쿼리 비용을 미리 재는 습관

BigQuery 는 **읽은 데이터 양**으로 과금한다(월 1 TiB 무료). 실행하기 전에
얼마나 읽을지 미리 알 수 있다 — 이걸 `dry run` 이라고 하고 **공짜다.**

큰 표를 만질 때는 항상 먼저 재 본다.
""")

code("""
def cost(sql: str) -> float:
    \"\"\"실행하지 않고 스캔량만 잰다. 공짜다.\"\"\"
    cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    gb = bq.query(sql, job_config=cfg).total_bytes_processed / 2**30
    print(f"이 쿼리는 {gb:.3f} GiB 를 읽습니다  (월 1024 GiB 무료)")
    return gb


# 필요한 열만 읽으면 스캔량이 준다. WHERE 로는 안 줄어든다.
cost("SELECT gender FROM `ping-v2-503916.raw.app_user`")
cost("SELECT * FROM `ping-v2-503916.raw.app_user`")
""")

md("""
## 4. 첫 쿼리 — pandas 로 받기

`_source` 로 어느 데이터를 볼지 먼저 정한다.

| 값 | 뜻 |
|---|---|
| `'local'` | 합성 데이터 (2만 명 · 12개월) |
| `'supabase'` | 실유저 (23명) |
""")

code("""
df = bq.query(\"\"\"
    SELECT gender, count(*) AS n
    FROM `ping-v2-503916.raw.app_user`
    WHERE _source = 'local'
      AND _deleted_at IS NULL
    GROUP BY gender
    ORDER BY n DESC
\"\"\").to_dataframe()

df
""")

md("""
## ⚠️ 규칙 ① — `_source` 없이 조인하지 않는다

한 표에 **실유저와 합성이 같이** 들어 있고, 둘 다 id 가 1부터라 **겹친다.**
`JOIN ... ON a.id = b.id` 만 쓰면 둘이 섞이는데 **오류가 나지 않는다.**
숫자만 조용히 커진다.

직접 세어 보자.
""")

code("""
df = bq.query(\"\"\"
    SELECT
      (SELECT count(*)
         FROM `ping-v2-503916.raw.vote_session` v
         JOIN `ping-v2-503916.raw.app_user` u
           ON v.user_id = u.id)                          AS without_source,
      (SELECT count(*)
         FROM `ping-v2-503916.raw.vote_session` v
         JOIN `ping-v2-503916.raw.app_user` u
           ON v.user_id = u.id AND v._source = u._source) AS with_source
\"\"\").to_dataframe()

bad, good = int(df.without_source[0]), int(df.with_source[0])
print(f"_source 없이 : {bad:,} 행")
print(f"_source 넣고 : {good:,} 행")
print(f"차이         : {bad - good:,} 행이 부풀려진다")
""")

md("""
## ⚠️ 규칙 ③ — 시각은 UTC 로 저장돼 있다

KST 로 바꾸지 않으면 시간대 분포가 **9시간 밀린다.** 밤에 몰리는 서비스가
낮에 몰리는 것처럼 보인다.

`voted_at` 은 큰 표라 먼저 비용을 재고 실행한다.
""")

code("""
sql = \"\"\"
    SELECT
      extract(hour from voted_at)                          AS hour_utc,
      extract(hour from voted_at at time zone 'Asia/Seoul') AS hour_kst,
      count(*) AS n
    FROM `ping-v2-503916.raw.vote_item`
    WHERE _source = 'local' AND voted_at IS NOT NULL
    GROUP BY 1, 2
\"\"\"

cost(sql)
h = bq.query(sql).to_dataframe()

top_utc = h.groupby("hour_utc")["n"].sum().idxmax()
top_kst = h.groupby("hour_kst")["n"].sum().idxmax()
print(f"\\n안 바꾸면 봉우리가 {top_utc}시 (틀림)")
print(f"KST 로 바꾸면   {top_kst}시 (맞음 - 밤에 몰린다)")
""")

code("""
import matplotlib.pyplot as plt

by_kst = h.groupby("hour_kst")["n"].sum().sort_index()
by_utc = h.groupby("hour_utc")["n"].sum().sort_index()

fig, ax = plt.subplots(figsize=(9, 3.2))
ax.plot(by_utc.index, by_utc.values, "--", label="UTC (wrong)", alpha=.55)
ax.plot(by_kst.index, by_kst.values, "-", label="KST (correct)", linewidth=2)
ax.set_xlabel("hour"); ax.set_ylabel("votes"); ax.set_xticks(range(0, 24, 2))
ax.legend(); ax.grid(alpha=.25)
plt.tight_layout(); plt.show()
""")

md("""
## 여기까지 오류가 없으면 준비 끝

**분석을 시작하기 전에 두 가지를 먼저 읽는다.**

1. `docs/ops/ops-bigquery-team-access.md` — 쿼리 규칙 넷과 비용
2. `EDA-final-12m-v5.pdf` **13장** — 이 데이터로 **할 수 없는 분석 7가지**

특히 2번이 중요하다. 설계상 차이가 없게 만들어진 항목들이라
**검정하면 반드시 "차이 없음"이 나온다.** 차이가 나오면 발견이 아니라 실수다.

---

## 잘 안 될 때

| 증상 | 원인과 해결 |
|---|---|
| `DefaultCredentialsError` | 인증 ②를 안 했다. `gcloud auth application-default login` |
| `403 ... does not have bigquery.jobs.create` | 요금 청구 프로젝트 미지정. ③ 실행 후 **커널 재시작** |
| `403 Access Denied ... raw` | 이 프로젝트에 권한이 없는 계정으로 로그인했다. 팀 Gmail 인지 확인 |
| `gcloud` 를 못 찾음 | 설치 후 터미널을 **새로 열어야** 한다 |
| `NotFound: Dataset ... raw` | 리전이 다르다. `location="asia-northeast3"` 인지 확인 |
| 위 1번이 `서비스 계정` 으로 나옴 | 키 파일을 쓰고 있다. ②③ 을 실행하고 커널 재시작 |
| `to_dataframe()` 에서 dtype 오류 | `pip install db-dtypes` |
""")

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = Path(r"c:/Users/user/Documents/project/ping-v2/notebooks/00-bigquery-connection-test.ipynb")
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")

# 셀 id 를 채운다 — 없으면 최신 nbformat 에서 하드 에러가 된다
import nbformat

_, normalized = nbformat.validator.normalize(nbformat.read(str(out), as_version=4))
nbformat.write(normalized, str(out))
nbformat.validate(nbformat.read(str(out), as_version=4))
print("wrote", out, f"({len(cells)} cells) · validated")
