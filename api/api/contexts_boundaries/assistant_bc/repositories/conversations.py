import abc
from typing import Any

from api.adapters.db import DBClient
from api.contexts_boundaries.assistant_bc.models import (
    ACTIVE_RUN_STATUSES,
    AssistantRun,
    Conversation,
    Message,
    MessageRole,
    RunEvent,
    RunStatus,
)
from api.contexts_boundaries.assistant_bc.repositories.tables import (
    assistant_runs_table,
    conversations_table,
    messages_table,
    run_events_table,
)


class AbstractConversationsRepository(abc.ABC):
    #
    # CONVERSATIONS
    #
    @abc.abstractmethod
    def create_conversation(self, citizen_id: int, title: str | None = None) -> Conversation: ...

    @abc.abstractmethod
    def get_conversation(self, conversation_id: int) -> Conversation | None: ...

    @abc.abstractmethod
    def list_conversations(self, citizen_id: int) -> list[Conversation]: ...

    @abc.abstractmethod
    def update_conversation(self, conversation_id: int, values: dict[str, Any]) -> Conversation | None: ...

    @abc.abstractmethod
    def delete_conversation(self, conversation_id: int) -> bool: ...

    #
    # MESSAGES
    #
    @abc.abstractmethod
    def create_message(
        self, conversation_id: int, role: MessageRole, content: str = "", run_id: int | None = None
    ) -> Message: ...

    @abc.abstractmethod
    def get_messages(self, conversation_id: int) -> list[Message]: ...

    #
    # RUNS
    #
    @abc.abstractmethod
    def create_run(self, conversation_id: int, user_message_id: int) -> AssistantRun: ...

    @abc.abstractmethod
    def get_run(self, run_id: int) -> AssistantRun | None: ...

    @abc.abstractmethod
    def get_active_run(self, conversation_id: int) -> AssistantRun | None: ...

    @abc.abstractmethod
    def update_run(self, run_id: int, **values: Any) -> AssistantRun | None: ...

    #
    # RUN EVENTS
    #
    @abc.abstractmethod
    def append_run_event(
        self, run_id: int, conversation_id: int, type: str, data: dict[str, Any] | None = None
    ) -> RunEvent: ...

    @abc.abstractmethod
    def get_run_events(self, run_id: int, since: int = 0) -> list[RunEvent]: ...


class ConversationsRepository(AbstractConversationsRepository):
    def __init__(self, db_client: DBClient) -> None:
        self._db = db_client

    #
    # CONVERSATIONS
    #
    def create_conversation(self, citizen_id: int, title: str | None = None) -> Conversation:
        row = self._db.create_one(
            conversations_table,
            values={"citizen_id": citizen_id, "title": title},
        )
        return Conversation.from_dict(row)

    def get_conversation(self, conversation_id: int) -> Conversation | None:
        row = self._db.get_one(conversations_table, {"id": conversation_id})
        return Conversation.from_dict(row) if row else None

    def list_conversations(self, citizen_id: int) -> list[Conversation]:
        rows = self._db.get_many(
            conversations_table,
            criteria={"citizen_id": citizen_id},
            order_by="-updated_at",
        )
        return [Conversation.from_dict(r) for r in rows]

    def update_conversation(self, conversation_id: int, values: dict[str, Any]) -> Conversation | None:
        if values:
            self._db.update_one(conversations_table, {"id": conversation_id}, values)
        return self.get_conversation(conversation_id)

    def delete_conversation(self, conversation_id: int) -> bool:
        return self._db.delete_many(conversations_table, {"id": conversation_id})

    #
    # MESSAGES
    #
    def create_message(
        self, conversation_id: int, role: MessageRole, content: str = "", run_id: int | None = None
    ) -> Message:
        row = self._db.create_one(
            messages_table,
            values={
                "conversation_id": conversation_id,
                "role": role.value,
                "content": content,
                "run_id": run_id,
            },
        )
        # conversations.updated_at is bumped by the `messages_touch_conversation`
        # DB trigger (see the assistant migration) so the sidebar re-sorts on the
        # newest activity — no manual UPDATE here.
        return Message.from_dict(row)

    def get_messages(self, conversation_id: int) -> list[Message]:
        rows = self._db.get_many(
            messages_table,
            criteria={"conversation_id": conversation_id},
            order_by="created_at",
        )
        return [Message.from_dict(r) for r in rows]

    #
    # RUNS
    #
    def create_run(self, conversation_id: int, user_message_id: int) -> AssistantRun:
        row = self._db.create_one(
            assistant_runs_table,
            values={
                "conversation_id": conversation_id,
                "status": RunStatus.QUEUED.value,
                "user_message_id": user_message_id,
            },
        )
        return AssistantRun.from_dict(row)

    def get_run(self, run_id: int) -> AssistantRun | None:
        row = self._db.get_one(assistant_runs_table, {"id": run_id})
        return AssistantRun.from_dict(row) if row else None

    def get_active_run(self, conversation_id: int) -> AssistantRun | None:
        rows = self._db.get_many(
            assistant_runs_table,
            criteria={"conversation_id": conversation_id, "status__in": list(ACTIVE_RUN_STATUSES)},
            order_by="-id",
            limit=1,
        )
        return AssistantRun.from_dict(rows[0]) if rows else None

    def update_run(self, run_id: int, **values: Any) -> AssistantRun | None:
        if values:
            self._db.update_one(assistant_runs_table, {"id": run_id}, values)
        return self.get_run(run_id)

    #
    # RUN EVENTS
    #
    def append_run_event(
        self, run_id: int, conversation_id: int, type: str, data: dict[str, Any] | None = None
    ) -> RunEvent:
        row = self._db.create_one(
            run_events_table,
            values={
                "run_id": run_id,
                "conversation_id": conversation_id,
                "type": type,
                "data": data or {},
            },
        )
        return RunEvent.from_dict(row)

    def get_run_events(self, run_id: int, since: int = 0) -> list[RunEvent]:
        criteria: dict[str, Any] = {"run_id": run_id}
        if since:
            criteria["id__gt"] = since
        rows = self._db.get_many(run_events_table, criteria=criteria, order_by="id")
        return [RunEvent.from_dict(r) for r in rows]
