-- Production PostgreSQL / Supabase DDL for ORCA Agentic Workflow Runtime
-- Enforces Row-Level Security (RLS) tenant isolation, durable step checkpoints, and idempotency keys
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS marts;

CREATE TABLE IF NOT EXISTS core.tenant_workflow_contracts (
    resolved_entity_id VARCHAR(32) PRIMARY KEY,
    canonical_workflow_code VARCHAR(32) NOT NULL,
    tenant_partner_id VARCHAR(32) NOT NULL,
    partner_organization_name TEXT NOT NULL,
    distributor_channel TEXT NOT NULL,
    workflow_domain VARCHAR(64) NOT NULL,
    contract_version VARCHAR(16) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS core.workflow_step_checkpoints (
    mention_id VARCHAR(32) PRIMARY KEY,
    resolved_entity_id VARCHAR(32) NOT NULL REFERENCES core.tenant_workflow_contracts(resolved_entity_id),
    tenant_partner_id VARCHAR(32) NOT NULL,
    doc_id VARCHAR(32) NOT NULL,
    protocol_stage VARCHAR(64) NOT NULL,
    execution_date DATE NOT NULL,
    a2a_task_state VARCHAR(32) NOT NULL,
    idempotency_key CHAR(64) NOT NULL,
    stated_coverage_usd BIGINT NOT NULL,
    verified_coverage_usd BIGINT NOT NULL,
    recovered_from_checkpoint BOOLEAN NOT NULL DEFAULT FALSE,
    is_superseded BOOLEAN NOT NULL DEFAULT FALSE,
    file_name TEXT NOT NULL,
    file_sha256 CHAR(64) NOT NULL,
    page_number INT NOT NULL,
    line_number INT NOT NULL,
    verbatim_quote TEXT NOT NULL,
    evidence_embedding vector(768)
);

ALTER TABLE core.tenant_workflow_contracts ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.workflow_step_checkpoints ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_contracts_isolation_policy ON core.tenant_workflow_contracts
    USING (tenant_partner_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_checkpoints_isolation_policy ON core.workflow_step_checkpoints
    USING (tenant_partner_id = current_setting('app.current_tenant_id', true));

CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_tenant_date
    ON core.workflow_step_checkpoints (tenant_partner_id, resolved_entity_id, execution_date);
