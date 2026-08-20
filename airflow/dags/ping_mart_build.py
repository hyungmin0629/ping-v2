"""
ping_mart_build · raw 가 갱신되면 품질을 보고 마트를 다시 굽는다

[[ops-p5-p7]] 의 "매번 도는 네 줄" 중 뒤의 둘이다.

    ① pipeline/extract_load.py   ─┐ ping_raw_load 가 한다
    ② pipeline/verify_load.py    ─┘
    ③ qa/quality_check.py        ─┐ 이 DAG 가 한다
    ④ bigquery/build.py --layer mart ─┘

**`ping_raw_load` 를 고치지 않고 잇는다.** 그쪽에 outlet 을 달거나
TriggerDagRunOperator 를 넣으면 두 DAG 가 서로를 알아야 하는데, 적재는
마트가 없어도 혼자 의미가 있는 일이다. 대신 이 DAG 가 Airflow 메타DB 를
들여다보는 `ExternalTaskSensor` 로 **한쪽에서만** 기다린다.

⚠️ **stg 는 다시 굽지 않는다.** 뷰라서 데이터를 갖고 있지 않다 — ①이 끝나면
   이미 최신이다. `bigquery/staging/*.sql` 을 고쳤을 때만 손으로
   `--layer stg` 를 돌린다.

⚠️ **품질 검증이 깨지면 마트를 굽지 않는다.** 대시보드가 옛 숫자를 보여주는
   것이 틀린 숫자를 보여주는 것보다 낫다. 마트는 `CREATE OR REPLACE` 라
   굽기 전까지 지난번 표가 그대로 살아 있다.

⚠️ **`quality_source` 는 ③ 에만 걸린다.** ④ 마트에는 원천 개념이 없다 —
   `build.py --layer mart` 에 `--source` 인자가 아예 없고, 여덟 표를 통째로
   다시 구우면 두 원천이 **한 표에 `source` 컬럼으로 갈려** 들어간다.
   즉 `local` 로 트리거하든 `supabase` 로 트리거하든 ④ 가 하는 일은 같다.

합성(local)은 재생성했을 때만 **손으로 트리거**한다 — 값이 안 변하는데
매일 구울 이유가 없다. 손으로 트리거하면 적재 대기를 건너뛴다(아래 branch).
"""

from __future__ import annotations

import pendulum
from airflow.models.dag import DAG
from airflow.models.param import Param
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.trigger_rule import TriggerRule

PROJECT = "/opt/project"
PYTHON = "python"

# 앞 DAG 와 **같은 시각**에 건다. ExternalTaskSensor 는 논리적 날짜(logical date)
# 로 짝을 찾으므로, 스케줄이 어긋나면 execution_delta 를 따로 계산해야 한다.
# 같은 크론을 쓰면 그 계산이 필요 없다.
UPSTREAM_DAG = "ping_raw_load"
UPSTREAM_TASK = "verify"
SCHEDULE = "0 4 * * *"


def _skip_wait_if_manual(**context) -> str:
    """손으로 트리거한 실행은 앞 DAG 를 기다리지 않는다.

    합성(local)을 다시 구울 때는 그날 `ping_raw_load` 가 돌았을 이유가 없다.
    기다리게 두면 짝이 없는 논리적 날짜를 붙들고 타임아웃까지 간다.
    """
    return "skip_wait" if context["dag_run"].run_type == "manual" else "wait_for_raw_load"


with DAG(
    dag_id="ping_mart_build",
    description="품질 검증 뒤 BigQuery mart 를 다시 굽는다 (ping_raw_load 다음)",
    schedule=SCHEDULE,
    start_date=pendulum.datetime(2026, 8, 20, tz="Asia/Seoul"),
    catchup=False,
    max_active_runs=1,  # 마트를 두 번 동시에 구우면 서로를 덮어쓴다
    default_args={
        "retries": 1,
        "retry_delay": pendulum.duration(minutes=10),
    },
    params={
        # ⚠️ 이 값은 **③ 품질 검증에만** 걸린다. ④ 마트 굽기에는 원천 개념이 없다 —
        #    `build.py --layer mart` 에는 `--source` 인자 자체가 없고, 여덟 표를
        #    통째로 다시 구우면 두 원천이 **한 표에 `source` 컬럼으로 갈려** 들어간다.
        #    그래서 이름을 `source` 가 아니라 `quality_source` 로 둔다 — DAG 전체의
        #    범위를 정하는 값으로 읽히면 안 된다.
        "quality_source": Param(
            "supabase",
            type="string",
            enum=["supabase", "local"],
            description="③ 품질 검증이 raw 에서 어느 원천을 볼지. ④ 마트는 이 값과 무관하게 통째로 다시 굽는다",
        ),
        "max_scan_gib": Param(
            20.0,
            type="number",
            description="품질 검증 예상 스캔량 상한. 합성은 행이 많아 넉넉히 준다(예: 60)",
        ),
    },
    tags=["ping-v2", "mart", "p6"],
) as dag:

    branch = BranchPythonOperator(
        task_id="branch_on_run_type",
        python_callable=_skip_wait_if_manual,
    )

    # 앞 DAG 의 마지막 태스크가 성공할 때까지 기다린다.
    # mode="reschedule" 이라 기다리는 동안 슬롯을 붙들지 않는다.
    wait_for_raw_load = ExternalTaskSensor(
        task_id="wait_for_raw_load",
        external_dag_id=UPSTREAM_DAG,
        external_task_id=UPSTREAM_TASK,
        allowed_states=["success"],
        # 앞이 실패하면 여기서 **바로** 실패한다. 두 시간을 기다린 끝에
        # 타임아웃으로 죽으면 원인이 적재였다는 것이 로그에서 사라진다.
        failed_states=["failed", "upstream_failed", "skipped"],
        mode="reschedule",
        poke_interval=120,
        timeout=60 * 60 * 2,
    )

    skip_wait = EmptyOperator(task_id="skip_wait")

    # ③ 믿어도 되는지 — **매일은 증분으로만** 본다.
    #
    #   필수값·시각  행 하나로 판정된다. 최근에 바뀐 행만 보면 된다.
    #                `updated_at` 이 파티션 컬럼이라 가지치기가 걸려 스캔이
    #                8.098 + 2.290 GiB → **0.001 GiB** 로 떨어진다(2026-08-20 실측).
    #   유일성·참조  표 전체를 봐야 답이 나온다. 여기서 빼고 `ping_quality_full`
    #                이 주 1회 전부 본다.
    #
    # ⚠️ **--kinds 로 나누는 것이 핵심이다.** 안 걸러지는 검사가 같은 UNION ALL
    #    묶음에 있으면 같은 컬럼을 다시 읽어 가지치기 효과가 통째로 사라진다 —
    #    실제로 섞어 돌렸을 때 11.655 → 11.697 GiB 로 **오히려 늘었다.**
    #
    # ⚠️ 창을 2일로 잡았다. 하루로 잡으면 실행이 늦거나 재시도로 밀렸을 때
    #    그 사이에 바뀐 행이 아무 검사도 안 받고 지나간다.
    #
    # 위반이 있으면 종료 코드 1 이라 여기서 멈춘다.
    # --yes 를 붙이지 않는다. 스캔량이 상한을 넘으면 조용히 돈이 나가는 대신
    # 태스크가 실패해서 눈에 띄어야 한다.
    quality_check = BashOperator(
        task_id="quality_check",
        bash_command=(
            f"cd {PROJECT} && {PYTHON} qa/quality_check.py"
            " --source {{ params.quality_source }}"
            " --kinds 필수값,시각 --since-days 2"
            " --max-scan-gib {{ params.max_scan_gib }}"
        ),
        # 앞의 둘 중 하나만 지나오면 된다(하나는 늘 skipped 다).
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    # ④ 마트를 통째로 다시 굽는다. CREATE OR REPLACE 라 여러 번 돌려도 같다 —
    # 그래서 재시도가 안전하다. 굽는 동안에도 대시보드에는 옛 표가 보인다.
    build_mart = BashOperator(
        task_id="build_mart",
        bash_command=f"cd {PROJECT} && {PYTHON} bigquery/build.py --layer mart",
    )

    branch >> [wait_for_raw_load, skip_wait] >> quality_check >> build_mart
