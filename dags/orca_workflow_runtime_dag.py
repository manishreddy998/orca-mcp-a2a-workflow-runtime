"""Apache Airflow / Cloud Composer DAG for the ORCA MCP & A2A multi-tenant workflow runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class SimpleDAG:
    dag_id: str
    schedule_interval: str
    start_date: datetime
    catchup: bool = False
    default_args: dict = field(default_factory=dict)
    tasks: list[str] = field(default_factory=list)


dag = SimpleDAG(
    dag_id="orca_mcp_a2a_workflow_runtime_pipeline",
    schedule_interval="0 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={"owner": "orca-platform-eng", "retries": 3, "retry_delay": timedelta(minutes=2)},
    tasks=[
        "ingest_partner_evidence_pdfs_beam",
        "execute_a2a_mcp_workflow_steps_async",
        "dbt_build_staging_and_rls_checks",
        "resolve_partner_entities_and_idempotency_graph",
        "dbt_build_checkpoint_chains_and_marts",
        "verify_contract_receipts_and_eval_gate",
    ],
)
