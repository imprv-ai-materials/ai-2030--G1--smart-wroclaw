from datetime import datetime
from typing import Any

from api.contexts_boundaries.assistant_bc.models.enums import MessageRole, RunStatus
from pydantic import BaseModel, Field


class Conversation(BaseModel):
    """A citizen's Q&A thread about city maintenance in Wrocław."""

    id: int
    citizen_id: int
    title: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Conversation":
        return cls(
            id=data["id"],
            citizen_id=data["citizen_id"],
            title=data.get("title"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


class Message(BaseModel):
    id: int
    conversation_id: int
    run_id: int | None = None
    role: MessageRole
    content: str = ""
    created_at: datetime

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        return cls(
            id=data["id"],
            conversation_id=data["conversation_id"],
            run_id=data.get("run_id"),
            role=MessageRole(data["role"]),
            content=data.get("content") or "",
            created_at=data["created_at"],
        )


class AssistantRun(BaseModel):
    """One question→answer turn, executed in the background by Inngest."""

    id: int
    conversation_id: int
    status: RunStatus
    user_message_id: int | None = None
    assistant_message_id: int | None = None
    error: str | None = None
    cancel_requested: bool = False
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssistantRun":
        return cls(
            id=data["id"],
            conversation_id=data["conversation_id"],
            status=RunStatus(data["status"]),
            user_message_id=data.get("user_message_id"),
            assistant_message_id=data.get("assistant_message_id"),
            error=data.get("error"),
            cancel_requested=bool(data.get("cancel_requested")),
            created_at=data["created_at"],
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
        )


class RunEvent(BaseModel):
    """Append-only lifecycle log the UI tails for live run status."""

    id: int
    run_id: int
    conversation_id: int
    type: str
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunEvent":
        return cls(
            id=data["id"],
            run_id=data["run_id"],
            conversation_id=data["conversation_id"],
            type=data["type"],
            data=data.get("data") or {},
            created_at=data["created_at"],
        )
