from datetime import datetime

from api.contexts_boundaries.assistant_bc.models import AssistantRun, Message, RunEvent
from pydantic import BaseModel, Field


class ConversationSummary(BaseModel):
    id: int
    title: str | None = None
    preview: str
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]


class ConversationCreateRequest(BaseModel):
    title: str | None = None


class MessagesResponse(BaseModel):
    messages: list[Message]


class RunStartRequest(BaseModel):
    prompt: str = Field(min_length=1)


class RunStartResponse(BaseModel):
    run: AssistantRun
    user_message: Message


class RunEventsResponse(BaseModel):
    events: list[RunEvent]
    last_event_id: int
