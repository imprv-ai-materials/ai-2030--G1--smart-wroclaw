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


class RunStatus(StrEnum):
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


def _jsonish(value: Any) -> Any:
    """JSONB columns come back as Python objects; guard the string case."""
    return json.loads(value) if isinstance(value, str) else value


class AgentRunStep(BaseModel):
    """One component the main agent ran within a turn — the durable twin of a
    `trace` step, streamed over the WS as it completes."""

    id: int
    run_id: int
    seq: int
    component: str
    status: RunStatus = RunStatus.DONE
    input: Any | None = None
    output: Any | None = None
    models: list[str] = Field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    created_at: datetime
    finished_at: datetime | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AgentRunStep":
        return cls(
            id=d["id"],
            run_id=d["run_id"],
            seq=d["seq"],
            component=d["component"],
            status=RunStatus(d.get("status") or RunStatus.DONE.value),
            input=_jsonish(d.get("input")),
            output=_jsonish(d.get("output")),
            models=_jsonish(d.get("models")) or [],
            prompt_tokens=d.get("prompt_tokens") or 0,
            completion_tokens=d.get("completion_tokens") or 0,
            created_at=d["created_at"],
            finished_at=d.get("finished_at"),
        )


class AgentRun(BaseModel):
    """One turn's run of the main agent — associated with the assistant message it
    produces (`message_id`), holding its component `steps`."""

    id: int
    conversation_id: int
    message_id: int | None = None
    status: RunStatus = RunStatus.RUNNING
    intent: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    steps: list[AgentRunStep] = Field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any], steps: list[AgentRunStep] | None = None) -> "AgentRun":
        return cls(
            id=d["id"],
            conversation_id=d["conversation_id"],
            message_id=d.get("message_id"),
            status=RunStatus(d.get("status") or RunStatus.RUNNING.value),
            intent=d.get("intent"),
            prompt_tokens=d.get("prompt_tokens") or 0,
            completion_tokens=d.get("completion_tokens") or 0,
            error=d.get("error"),
            created_at=d["created_at"],
            finished_at=d.get("finished_at"),
            steps=steps or [],
        )
