-- ===========================================================================
-- Order Supervisor - database schema
-- ---------------------------------------------------------------------------
-- Everything lives in an isolated schema ({schema}, default `order_supervisor`)
-- so it can share a database with other projects without collisions.
-- `{schema}` is substituted by app/db.py at startup from settings.db_schema.
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS {schema};

SET search_path TO {schema};

-- --- Supervisor templates -------------------------------------------------
CREATE TABLE IF NOT EXISTS {schema}.supervisors (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              TEXT NOT NULL,
    base_instruction  TEXT NOT NULL,
    available_actions  JSONB NOT NULL DEFAULT '[]'::jsonb,   -- allowed tool names
    default_wake_minutes  INTEGER NOT NULL DEFAULT 60,        -- default sleep cadence
    wake_aggressiveness   TEXT NOT NULL DEFAULT 'balanced',   -- passive | balanced | aggressive
    model_config       JSONB NOT NULL DEFAULT '{{}}'::jsonb,  -- optional model overrides
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- --- Runs (one per order = one Temporal workflow) -----------------------
CREATE TABLE IF NOT EXISTS {schema}.runs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supervisor_id     UUID NOT NULL REFERENCES {schema}.supervisors(id),
    order_id          TEXT NOT NULL,
    workflow_id       TEXT NOT NULL UNIQUE,                  -- Temporal workflow id
    status            TEXT NOT NULL DEFAULT 'starting',      -- starting|running|sleeping|paused|completed|terminated
    sleep_state       TEXT NOT NULL DEFAULT 'awake',         -- awake|sleeping
    next_wake_at      TIMESTAMPTZ,
    order_context     JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    run_instructions  JSONB NOT NULL DEFAULT '[]'::jsonb,    -- extra per-run instructions
    memory_summary    TEXT NOT NULL DEFAULT '',              -- compact rolling summary
    wakeup_guidance   TEXT NOT NULL DEFAULT '',              -- agent-authored classifier hints
    final_output      JSONB,                                 -- {{summary, actions, learnings, feedback}}
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS runs_status_idx ON {schema}.runs(status);
CREATE INDEX IF NOT EXISTS runs_order_idx  ON {schema}.runs(order_id);

-- --- Single activity log ------------------------------------------------
-- Stores everything: incoming events, wake/sleep decisions, agent actions,
-- agent reasoning, manual instructions, and final outputs.
CREATE TABLE IF NOT EXISTS {schema}.activities (
    id          BIGSERIAL PRIMARY KEY,
    run_id      UUID NOT NULL REFERENCES {schema}.runs(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,   -- event | wake_decision | sleep_decision |
                                 -- agent_action | agent_reasoning | instruction | final_output | system
    title       TEXT NOT NULL,
    payload     JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    important    BOOLEAN NOT NULL DEFAULT false,   -- kept in compact memory
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS activities_run_idx  ON {schema}.activities(run_id, id);
CREATE INDEX IF NOT EXISTS activities_kind_idx ON {schema}.activities(run_id, kind);
