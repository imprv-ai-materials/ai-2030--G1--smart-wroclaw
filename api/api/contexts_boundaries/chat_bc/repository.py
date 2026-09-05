from typing import Any

from api.adapters.db import DBClient
from api.contexts_boundaries.chat_bc.models import (
    ChatConversation,
    ChatMessage,
    ChatRole,
)
from api.contexts_boundaries.chat_bc.tables import (
    chat_conversations_table,
    chat_messages_table,
)


class ChatRepository:
    """Persistence for the unified chat: conversations + their turns."""

    def __init__(self, db_client: DBClient) -> None:
        self._db = db_client

    # -- conversations ---------------------------------------------------------
    def create_conversation(
        self, citizen_id: int | None = None, title: str | None = None
    ) -> ChatConversation:
        row = self._db.create_one(
            chat_conversations_table,
            values={"citizen_id": citizen_id, "title": title},
        )
        return ChatConversation.from_dict(row)

    def get_conversation(self, conversation_id: int) -> ChatConversation | None:
        row = self._db.get_one(chat_conversations_table, {"id": conversation_id})
        return ChatConversation.from_dict(row) if row else None

    def list_conversations(self, citizen_id: int) -> list[ChatConversation]:
        rows = self._db.get_many(
            chat_conversations_table,
            criteria={"citizen_id": citizen_id},
            order_by="-updated_at",
            limit=100,
        )
        return [ChatConversation.from_dict(r) for r in rows]

    def attach_citizen(self, conversation_id: int, citizen_id: int) -> None:
        """Stamp the account onto a (previously anonymous) conversation."""
        self._db.update_one(
            chat_conversations_table, {"id": conversation_id}, {"citizen_id": citizen_id}
        )

    def set_title(self, conversation_id: int, title: str) -> None:
        self._db.update_one(chat_conversations_table, {"id": conversation_id}, {"title": title})

    # -- messages --------------------------------------------------------------
    def add_message(
        self,
        conversation_id: int,
        role: ChatRole,
        content: str,
        data: dict[str, Any] | None = None,
    ) -> ChatMessage:
        row = self._db.create_one(
            chat_messages_table,
            values={
                "conversation_id": conversation_id,
                "role": role.value,
                "content": content,
                "data": data or {},
            },
        )
        return ChatMessage.from_dict(row)

    def list_messages(self, conversation_id: int, limit: int = 50) -> list[ChatMessage]:
        rows = self._db.get_many(
            chat_messages_table,
            criteria={"conversation_id": conversation_id},
            order_by="created_at",
            limit=limit,
        )
        return [ChatMessage.from_dict(r) for r in rows]
