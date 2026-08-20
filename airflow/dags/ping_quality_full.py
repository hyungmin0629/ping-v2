"""
ping_quality_full · 주 1회 raw 품질 전수 검사

`ping_mart_build` 는 매일 **증분으로만** 본다(필수값·시각 · 최근 2일).
그것이 못 보는 것을 이 DAG 가 주 1회 전부 훑어서 메운다.

**증분이 원리적으로 못 잡는 것 둘**

- **유일성 · 참조** — 표 전체를 봐야 답이 나온다. 새 행의 PK 가 옛 행과
  부딪히는지, 자식의 부모가 옛 행 중에 있는지는 최근 조각만 봐서는 모른다.
- ⚠️ **워터마크가 멈춘 채로 컬럼이 추가된 경우** — 이게 더 고약하다.
  필수값 검사는 원래 이걸 잡으라고 만든 것인데(`updated_at` 이 안 움직여 증분이
  아무것도 못 가져온 상태), **바로 그 상황에서는 "최근에 바뀐 행"이 비어 있어
  증분 검사가 통과해 버린다.** 전수 검사만이 이걸 본다.

그래서 이 DAG 는 **`--kinds` 도 `--since-days` 도 주지 않는다.** 전부 본다.

⚠️ **마트를 막지 않는다.** 여기서 잡히는 것은 대개 오늘 들어온 행이 아니라
   과거에 쌓인 문제다. 대시보드를 멈춰 세우는 대신 **DAG 실패로 알린다.**
   오늘 적재를 믿을 수 있는가는 `ping_mart_build` 의 증분 검사가 이미 답한다.
"""

from __future__ import annotations

import pendulum
from airflow.models.dag import DAG
from airflow.models.param import Param
from airflow.operators.bash import BashOperator

PROJECT = "/opt/project"
PYTHON = "python"

with DAG(
    dag_id="ping_quality_full",
    description="주 1회 raw 전수 품질 검사 (증분이 못 보는 것을 메운다)",
    # 일요일 새벽 5시 KST. 적재(4시)와 마트 굽기가 끝난 뒤에 본다.
    # ⚠️ start_date 에 tz 를 박았으므로 이 크론은 **KST 로 해석된다.**
    #    tz 를 안 박으면 UTC 가 되어 9시간 어긋난다.
    schedule="0 5 * * 0",
    start_date=pendulum.datetime(2026, 8, 20, tz="Asia/Seoul"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 1,
        "retry_delay": pendulum.duration(minutes=30),
    },
    params={
        "source": Param(
            "supabase",
            type="string",
            enum=["supabase", "local"],
            description="어느 원천을 검사하나",
        ),
        "max_scan_gib": Param(
            20.0,
            type="number",
            description="예상 스캔량 상한. 전수라 증분보다 훨씬 크다(supabase 11.7 GiB · 2026-08-20 실측)",
        ),
    },
    tags=["ping-v2", "qa", "p5"],
) as dag:

    quality_full = BashOperator(
        task_id="quality_full",
        bash_command=(
            f"cd {PROJECT} && {PYTHON} qa/quality_check.py"
            " --source {{ params.source }}"
            " --max-scan-gib {{ params.max_scan_gib }}"
        ),
    )
