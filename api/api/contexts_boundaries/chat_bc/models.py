import json
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ChatRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class ChatConversation(BaseModel):
    id: int
    user_id: int | None = None  # None → anonymous, until login attaches it
    title: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ChatConversation":
        return cls(
            id=d["id"],
            user_id=d.get("user_id"),
            title=d.get("title"),
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )


class ChatMessage(BaseModel):
    id: int
    conversation_id: int
    role: ChatRole
    content: str
    # The assistant turn's structured payload (intent, filters, missing fields…).
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ChatMessage":
        data = d.get("data")
        if isinstance(data, str):
            data = json.loads(data)
        return cls(
            id=d["id"],
            conversation_id=d["conversation_id"],
            role=ChatRole(d["role"]),
            content=d["content"],
            data=data or {},
            created_at=d["created_at"],
        )
