"""track agent runs + their steps (streamed over WS, associated to messages)

Revision ID: 0008_agent_runs
Revises: 0007_user_role
Create Date: 2026-09-06 13:00:00.000000

Each chat turn fires the main agent as an Inngest function; this records the run
and one row per component STEP (guardrails / extractor / router / lane / geo) as
they complete — the durable backing for the live WebSocket stream and the admin
trace. A run is associated with the assistant `chat_messages` row it produces
(`message_id`, stamped on finalize).
"""

from api.adapters.db.migrations.versions import execute

revision = "0008_agent_runs"
down_revision = "0007_user_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute(
        """
        CREATE TABLE agent_runs (
            id                BIGSERIAL PRIMARY KEY,
            conversation_id   BIGINT NOT NULL REFERENCES chat_conversations (id) ON DELETE CASCADE,
            message_id        BIGINT REFERENCES chat_messages (id) ON DELETE SET NULL,
            status            TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'done', 'error')),
            intent            TEXT,
            prompt_tokens     INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            error             TEXT,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at       TIMESTAMPTZ
        );
        """
    )
    execute("CREATE INDEX agent_runs_conversation_id_idx ON agent_runs (conversation_id);")
    execute("CREATE INDEX agent_runs_message_id_idx ON agent_runs (message_id);")

    execute(
        """
        CREATE TABLE agent_run_steps (
            id                BIGSERIAL PRIMARY KEY,
            run_id            BIGINT NOT NULL REFERENCES agent_runs (id) ON DELETE CASCADE,
            seq               INTEGER NOT NULL,
            component         TEXT    NOT NULL,
            status            TEXT    NOT NULL DEFAULT 'done' CHECK (status IN ('running', 'done', 'error')),
            input             JSONB,
            output            JSONB,
            models            JSONB   NOT NULL DEFAULT '[]',
            prompt_tokens     INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at       TIMESTAMPTZ
        );
        """
    )
    execute("CREATE INDEX agent_run_steps_run_id_idx ON agent_run_steps (run_id);")


def downgrade() -> None:
    execute("DROP TABLE IF EXISTS agent_run_steps;")
    execute("DROP TABLE IF EXISTS agent_runs;")
