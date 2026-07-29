"""
ping_raw_load · Supabase → BigQuery raw 증분 적재

실유저 데이터만 돌린다. 합성 데이터(786만 행)는 한 번 만들어지고 변하지
않으므로 스케줄에 넣을 이유가 없다 — 필요할 때 손으로 한 번 돌린다:

    python pipeline/extract_load.py --source local

적재 로직은 DAG 안에 두지 않고 pipeline/ 의 스크립트를 부른다.
Airflow 없이도 같은 명령으로 돌릴 수 있어야 디버깅이 된다.
"""

from __future__ import annotations

import pendulum
from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

PROJECT = "/opt/project"
PYTHON = "python"

with DAG(
    dag_id="ping_raw_load",
    description="Supabase 실유저 데이터를 BigQuery raw 로 증분 적재",
    # 한국 시간 기준. 클로즈드 테스트는 저녁에 몰리므로 새벽에 하루치를 턴다.
    schedule="0 4 * * *",
    start_date=pendulum.datetime(2026, 7, 30, tz="Asia/Seoul"),
    catchup=False,  # 증분 워터마크가 시간을 관리한다. 지난 날짜를 되돌릴 이유가 없다
    max_active_runs=1,  # 두 개가 겹치면 같은 워터마크를 두 번 읽는다
    default_args={
        "retries": 2,
        "retry_delay": pendulum.duration(minutes=5),
    },
    tags=["ping-v2", "raw"],
) as dag:

    extract_load = BashOperator(
        task_id="extract_load",
        bash_command=f"cd {PROJECT} && {PYTHON} pipeline/extract_load.py --source supabase",
    )

    # 증분 적재는 조용히 틀린다. 워터마크가 한 번 어긋나면 그 뒤로 계속
    # 빠진 채 흐르고 쿼리는 아무 오류 없이 답을 준다. 그래서 매번 센다.
    verify = BashOperator(
        task_id="verify",
        bash_command=f"cd {PROJECT} && {PYTHON} pipeline/verify_load.py --source supabase",
    )

    extract_load >> verify
