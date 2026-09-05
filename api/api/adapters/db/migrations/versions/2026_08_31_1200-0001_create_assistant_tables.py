"""create assistant Q&A tables

Revision ID: 0001_assistant
Revises:
Create Date: 2026-08-31 12:00:00.000000

Citizens ask maintenance questions in a conversation; each question is one
background "run" that produces an assistant answer. `run_events` is an
append-only log the UI tails for live status.
"""

from api.adapters.db.migrations.versions import execute

revision = "0001_assistant"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute("""
        CREATE TABLE conversations (
            id          BIGSERIAL PRIMARY KEY,
            citizen_id  BIGINT      NOT NULL,
            title       TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)
    execute("CREATE INDEX conversations_citizen_id_idx ON conversations (citizen_id);")

    execute("""
        CREATE TABLE messages (
            id               BIGSERIAL PRIMARY KEY,
            conversation_id  BIGINT      NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
            run_id           BIGINT,
            role             TEXT        NOT NULL CHECK (role IN ('USER', 'ASSISTANT', 'SYSTEM')),
            content          TEXT        NOT NULL DEFAULT '',
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)
    execute("CREATE INDEX messages_conversation_id_idx ON messages (conversation_id);")

    execute("""
        CREATE TABLE assistant_runs (
            id                    BIGSERIAL PRIMARY KEY,
            conversation_id       BIGINT      NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
            status                TEXT        NOT NULL DEFAULT 'queued'
                                  CHECK (status IN ('queued', 'running', 'done', 'failed', 'cancelled')),
            user_message_id       BIGINT      REFERENCES messages (id) ON DELETE SET NULL,
            assistant_message_id  BIGINT      REFERENCES messages (id) ON DELETE SET NULL,
            error                 TEXT,
            cancel_requested      BOOLEAN     NOT NULL DEFAULT FALSE,
            created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            started_at            TIMESTAMPTZ,
            finished_at           TIMESTAMPTZ
        );
        """)
    execute("CREATE INDEX assistant_runs_conversation_id_idx ON assistant_runs (conversation_id);")
    # At most one in-flight run per conversation.
    execute("""
        CREATE UNIQUE INDEX assistant_runs_one_active_per_conversation
            ON assistant_runs (conversation_id) WHERE status IN ('queued', 'running');
        """)

    execute("""
        CREATE TABLE run_events (
            id               BIGSERIAL PRIMARY KEY,
            run_id           BIGINT      NOT NULL REFERENCES assistant_runs (id) ON DELETE CASCADE,
            conversation_id  BIGINT      NOT NULL,
            type             TEXT        NOT NULL,
            data             JSONB       NOT NULL DEFAULT '{}',
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)
    execute("CREATE INDEX run_events_run_id_idx ON run_events (run_id);")

    # Keep conversations.updated_at fresh whenever a message is added, so the
    # sidebar re-sorts on newest activity (repository relies on this trigger).
    execute("""
        CREATE OR REPLACE FUNCTION messages_touch_conversation() RETURNS trigger AS $$
        BEGIN
            UPDATE conversations SET updated_at = now() WHERE id = NEW.conversation_id;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)
    execute("""
        CREATE TRIGGER messages_touch_conversation_trg
            AFTER INSERT ON messages
            FOR EACH ROW EXECUTE FUNCTION messages_touch_conversation();
        """)


def downgrade() -> None:
    execute("DROP TRIGGER IF EXISTS messages_touch_conversation_trg ON messages;")
    execute("DROP FUNCTION IF EXISTS messages_touch_conversation();")
    execute("DROP TABLE IF EXISTS run_events;")
    execute("DROP TABLE IF EXISTS assistant_runs;")
    execute("DROP TABLE IF EXISTS messages;")
    execute("DROP TABLE IF EXISTS conversations;")
