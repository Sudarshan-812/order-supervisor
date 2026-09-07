-- Order Supervisor schema.
--
-- Run this as is in any Postgres 13+ (a SQL editor or psql). It creates the
-- three tables in the public schema. Enum-like columns are plain TEXT with a
-- CHECK so the POC stays migration free. The backend also runs this file on
-- startup; every statement is idempotent.

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- for gen_random_uuid() on a bare Postgres


-- Supervisor templates. A run points at one.
CREATE TABLE IF NOT EXISTS supervisors (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              TEXT NOT NULL,
    base_instruction  TEXT NOT NULL,
    model_config      JSONB NOT NULL DEFAULT '{}'::jsonb,  -- allowed_actions, default_wake_minutes, wake_aggressiveness, model overrides
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- One row per supervised order, which is one long-running Temporal workflow.
CREATE TABLE IF NOT EXISTS runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        TEXT NOT NULL,
    supervisor_id   UUID NOT NULL REFERENCES supervisors(id),
    status          TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'sleeping', 'completed', 'terminated')),
    memory_summary  TEXT NOT NULL DEFAULT '',
    workflow_id     TEXT UNIQUE,   -- Temporal workflow id, set on start; lets the API signal the run
    next_wake_at    TIMESTAMPTZ,   -- when the scheduled wake fires (for the UI)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS runs_status_idx   ON runs (status);
CREATE INDEX IF NOT EXISTS runs_order_id_idx ON runs (order_id);


-- One append-only log per run: incoming events, wake/sleep decisions, agent
-- actions, manual instructions, and the final output.
CREATE TABLE IF NOT EXISTS activity_log (
    id          BIGSERIAL PRIMARY KEY,
    run_id      UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    type        TEXT NOT NULL CHECK (type IN (
                    'incoming_event',
                    'wake_decision',
                    'agent_action',
                    'manual_instruction',
                    'final_output'
                )),
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS activity_log_run_id_idx ON activity_log (run_id, id);
CREATE INDEX IF NOT EXISTS activity_log_type_idx   ON activity_log (run_id, type);


-- Keep runs.updated_at current on every UPDATE.
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS runs_set_updated_at ON runs;
CREATE TRIGGER runs_set_updated_at
    BEFORE UPDATE ON runs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
