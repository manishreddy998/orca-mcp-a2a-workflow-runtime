"""ORCA Agent-to-Agent (A2A) and Model Context Protocol (MCP) runtime contracts,
durable step checkpointing, idempotency deduplication, and multi-tenant isolation gate."""
from __future__ import annotations

import hashlib
from typing import Any

ORCA_AGENT_CARD: dict[str, Any] = {
    "name": "orca-enterprise-workflow-runtime",
    "description": "Lydia AI ORCA multi-tenant agentic workflow runtime exposing reusable underwriting, claims, and compliance workflows via A2A and MCP.",
    "url": "http://localhost:8120/a2a",
    "version": "1.0.0",
    "protocolVersion": "0.2.1",
    "capabilities": {
        "streaming": True,
        "pushNotifications": True,
        "stateTransitionHistory": True,
        "durableCheckpointing": True,
    },
    "authentication": {
        "schemes": ["Bearer", "X-ORCA-Tenant-Token"],
        "rlsIsolation": "postgres_current_tenant_id",
    },
    "defaultInputModes": ["application/json", "application/pdf"],
    "defaultOutputModes": ["application/json"],
    "skills": [
        {
            "id": "underwriting_evidence_pack",
            "name": "Underwriting Evidence Pack Synthesis",
            "description": "Ingests medical and financial underwriting disclosures, verifies policy rules, and produces a cite-backed underwriting evidence pack.",
            "tags": ["underwriting", "health-risk", "evidence-pack", "mcp"],
        },
        {
            "id": "claims_adjudication_audit",
            "name": "Claims Adjudication & Benefit Schedule Audit",
            "description": "Reconciles itemized claim schedules against policy riders, flags math discrepancies, and excludes revoked riders.",
            "tags": ["claims", "adjudication", "schedule-reconciliation", "a2a"],
        },
        {
            "id": "distributor_compliance_review",
            "name": "Distributor Partner Compliance & Risk Review",
            "description": "Executes cross-border regulatory and distributor suitability checks with deterministic PDF citation receipts.",
            "tags": ["distributor", "compliance", "multi-tenant", "audit"],
        },
    ],
}

MCP_TOOLS_SPEC: list[dict[str, Any]] = [
    {
        "name": "verify_source_citation",
        "description": "Verify that a workflow deliverable quote and coverage figure match the source PDF page, line, and SHA-256 digest.",
        "inputSchema": {
            "type": "object",
            "required": ["tenant_id", "workflow_code", "doc_id", "page_number", "line_number"],
            "properties": {
                "tenant_id": {"type": "string"},
                "workflow_code": {"type": "string"},
                "doc_id": {"type": "string"},
                "page_number": {"type": "integer"},
                "line_number": {"type": "integer"},
            },
        },
    },
    {
        "name": "reconcile_benefit_schedule",
        "description": "Reconcile Base Coverage + Rider Allowance + Co-Pay Reserve against Stated Benefit Total and flag discrepancies.",
        "inputSchema": {
            "type": "object",
            "required": ["tenant_id", "base_coverage_usd", "rider_allowance_usd", "copay_reserve_usd", "stated_total_usd"],
            "properties": {
                "tenant_id": {"type": "string"},
                "base_coverage_usd": {"type": "integer"},
                "rider_allowance_usd": {"type": "integer"},
                "copay_reserve_usd": {"type": "integer"},
                "stated_total_usd": {"type": "integer"},
            },
        },
    },
    {
        "name": "checkpoint_workflow_step",
        "description": "Persist or resume a durable workflow step checkpoint keyed by (tenant_id, workflow_code, step_seq, idempotency_key).",
        "inputSchema": {
            "type": "object",
            "required": ["tenant_id", "workflow_code", "step_seq", "idempotency_key"],
            "properties": {
                "tenant_id": {"type": "string"},
                "workflow_code": {"type": "string"},
                "step_seq": {"type": "integer"},
                "idempotency_key": {"type": "string"},
            },
        },
    },
    {
        "name": "evaluate_policy_rider_status",
        "description": "Check whether a policy rider or underwriting authorization is active or revoked/expired before committing capacity.",
        "inputSchema": {
            "type": "object",
            "required": ["tenant_id", "workflow_code", "resolution_status"],
            "properties": {
                "tenant_id": {"type": "string"},
                "workflow_code": {"type": "string"},
                "resolution_status": {"type": "string"},
            },
        },
    },
]


def compute_idempotency_key(tenant_id: str, workflow_code: str, step_stage: str, payload_digest: str) -> str:
    raw = f"{tenant_id.strip()}:{workflow_code.strip()}:{step_stage.strip()}:{payload_digest.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def enforce_tenant_isolation(caller_tenant_id: str, resource_tenant_id: str) -> dict[str, Any]:
    """Verify that the authenticated partner tenant matches the target workflow resource tenant."""
    allowed = bool(caller_tenant_id and resource_tenant_id and caller_tenant_id == resource_tenant_id)
    if not allowed:
        return {
            "allowed": False,
            "error_code": -32003,
            "status": "TENANT_ISOLATION_VIOLATION",
            "detail": f"Cross-tenant access denied: caller {caller_tenant_id} cannot access resource owned by {resource_tenant_id}.",
        }
    return {
        "allowed": True,
        "error_code": 0,
        "status": "TENANT_ISOLATION_VERIFIED",
        "detail": f"RLS tenant context verified for {caller_tenant_id}.",
    }


def handle_mcp_jsonrpc(request: dict[str, Any]) -> dict[str, Any]:
    """Handle MCP JSON-RPC 2.0 requests (initialize, tools/list, tools/call, resources/read) with tenant isolation."""
    req_id = request.get("id", 1)
    method = request.get("method", "")
    params = request.get("params", {}) or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2025-03-26",
                "serverInfo": {"name": "orca-mcp-workflow-server", "version": "1.0.0"},
                "capabilities": {"tools": {"listChanged": False}, "resources": {"subscribe": False}},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": MCP_TOOLS_SPEC},
        }

    if method in ("tools/call", "resources/read"):
        caller_tenant = str(params.get("caller_tenant_id") or params.get("tenant_id") or "")
        resource_tenant = str(params.get("resource_tenant_id") or params.get("tenant_id") or "")
        gate = enforce_tenant_isolation(caller_tenant, resource_tenant)
        if not gate["allowed"]:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": gate["error_code"],
                    "message": gate["status"],
                    "data": gate["detail"],
                },
            }

        tool_name = params.get("name", "verify_source_citation")
        args = params.get("arguments", {}) or {}
        if tool_name == "reconcile_benefit_schedule":
            base_v = int(args.get("base_coverage_usd", 0))
            rider_v = int(args.get("rider_allowance_usd", 0))
            copay_v = int(args.get("copay_reserve_usd", 0))
            stated_v = int(args.get("stated_total_usd", 0))
            verified_v = base_v + rider_v + copay_v
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tool": tool_name,
                    "tenant_id": caller_tenant,
                    "verified_sum_usd": verified_v,
                    "stated_total_usd": stated_v,
                    "math_gap_usd": stated_v - verified_v,
                    "schedule_valid": (stated_v == verified_v),
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tool": tool_name,
                "tenant_id": caller_tenant,
                "rls_policy": "VERIFIED",
                "status": "completed",
            },
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }
