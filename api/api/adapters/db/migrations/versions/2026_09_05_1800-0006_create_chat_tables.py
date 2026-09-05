"""create chat orchestrator tables

Revision ID: 0006_chat
Revises: 0005_city_events_extra
Create Date: 2026-09-05 18:00:00.000000

The unified chat ("main agent") stores every turn. Conversations are ANONYMOUS
(`user_id` NULL) until the resident logs in — filing an event requires auth,
at which point the account is stamped onto the conversation.
"""

from api.adapters.db.migrations.versions import execute

revision = "0006_chat"
down_revision = "0005_city_events_extra"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute("""
        CREATE TABLE chat_conversations (
            id          BIGSERIAL PRIMARY KEY,
            user_id     BIGINT REFERENCES users (id) ON DELETE SET NULL,
            title       TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)
    execute("CREATE INDEX chat_conversations_user_id_idx ON chat_conversations (user_id);")

    execute("""
        CREATE TABLE chat_messages (
            id               BIGSERIAL PRIMARY KEY,
            conversation_id  BIGINT      NOT NULL REFERENCES chat_conversations (id) ON DELETE CASCADE,
            role             TEXT        NOT NULL CHECK (role IN ('USER', 'ASSISTANT')),
            content          TEXT        NOT NULL DEFAULT '',
            data             JSONB       NOT NULL DEFAULT '{}',
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)
    execute("CREATE INDEX chat_messages_conversation_id_idx ON chat_messages (conversation_id);")

    # Bump the conversation's updated_at on each new message so the profile list
    # re-sorts on newest activity.
    execute("""
        CREATE OR REPLACE FUNCTION chat_messages_touch_conversation() RETURNS trigger AS $$
        BEGIN
            UPDATE chat_conversations SET updated_at = now() WHERE id = NEW.conversation_id;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)
    execute("""
        CREATE TRIGGER chat_messages_touch_conversation_trg
            AFTER INSERT ON chat_messages
            FOR EACH ROW EXECUTE FUNCTION chat_messages_touch_conversation();
        """)


def downgrade() -> None:
    execute("DROP TRIGGER IF EXISTS chat_messages_touch_conversation_trg ON chat_messages;")
    execute("DROP FUNCTION IF EXISTS chat_messages_touch_conversation();")
    execute("DROP TABLE IF EXISTS chat_messages;")
    execute("DROP TABLE IF EXISTS chat_conversations;")
