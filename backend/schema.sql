-- ===========================================================================
-- Order Supervisor - Supabase schema
-- ---------------------------------------------------------------------------
-- Run this as-is in the Supabase SQL editor (or `psql`). It creates the three
-- tables the POC needs in the `public` schema.
--
-- Enum-like columns are plain TEXT + CHECK so the POC stays migration-free.
-- A few operational columns beyond the base spec are marked [ops] and can be
-- dropped if unused.
-- ===========================================================================

-- gen_random_uuid() lives in pgcrypto; Supabase enables it by default, this is
-- just belt-and-braces for a bare Postgres.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- --- Supervisor templates ------------------------------------------------
-- Reusable "what kind of supervisor is this" definitions. A run points at one.
CREATE TABLE IF NOT EXISTS supervisors (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              TEXT NOT NULL,
    base_instruction  TEXT NOT NULL,
    model_config      JSONB NOT NULL DEFAULT '{}'::jsonb,   -- {provider, model, temperature, ...}
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()    -- [ops]
);

-- --- Runs -----------------------------------------------------------------
-- One row per supervised order == one long-running Temporal workflow.
CREATE TABLE IF NOT EXISTS runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        TEXT NOT NULL,
    supervisor_id   UUID NOT NULL REFERENCES supervisors(id),
    status          TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'sleeping', 'completed', 'terminated')),
    memory_summary  TEXT NOT NULL DEFAULT '',

    workflow_id     TEXT UNIQUE,     -- [ops] Temporal workflow id, set on start; lets the API signal the run
    next_wake_at    TIMESTAMPTZ,     -- [ops] when the workflow's scheduled wake-up fires (for UI display)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),   -- [ops]
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()    -- [ops]
);

CREATE INDEX IF NOT EXISTS runs_status_idx   ON runs (status);
CREATE INDEX IF NOT EXISTS runs_order_id_idx ON runs (order_id);

-- --- Activity log -------------------------------------------------------
-- The single append-only log of everything that happens on a run: events in,
-- wake/sleep decisions, agent actions, manual instructions, final output.
CREATE TABLE IF NOT EXISTS activity_log (
    id          BIGSERIAL PRIMARY KEY,
    run_id      UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    type        TEXT NOT NULL
                    CHECK (type IN (
                        'incoming_event',
                        'wake_decision',
                        'agent_action',
                        'manual_instruction',
                        'final_output'
                    )),
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()    -- [ops] timeline ordering
);

CREATE INDEX IF NOT EXISTS activity_log_run_id_idx ON activity_log (run_id, id);
CREATE INDEX IF NOT EXISTS activity_log_type_idx   ON activity_log (run_id, type);

-- --- keep runs.updated_at fresh ---------------------------------------- [ops]
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
