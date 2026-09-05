"""Conversation lifecycle for the assistant Q&A layer.

A thin orchestration layer over `ConversationsRepository`: ownership checks +
title derivation. Heavy lifting (the actual answer) happens in the run/agent.
"""

from typing import Any

from api.contexts_boundaries.assistant_bc.models import Conversation, Message, MessageRole
from api.contexts_boundaries.assistant_bc.repositories import AbstractConversationsRepository
from api.shared.exceptions import AccessDeniedError, NotFoundError


class ConversationsService:
    def __init__(self, repository: AbstractConversationsRepository, title_max_chars: int = 60) -> None:
        self._repo = repository
        self._title_max = title_max_chars

    def create_conversation(self, citizen_id: int, title: str | None = None) -> Conversation:
        return self._repo.create_conversation(citizen_id=citizen_id, title=title)

    def list_conversations(self, citizen_id: int) -> list[Conversation]:
        return self._repo.list_conversations(citizen_id)

    def get_owned_or_raise(self, conversation_id: int, citizen_id: int) -> Conversation:
        conversation = self._repo.get_conversation(conversation_id)
        if conversation is None:
            raise NotFoundError(f"conversation {conversation_id} not found")
        if conversation.citizen_id != citizen_id:
            raise AccessDeniedError(f"conversation {conversation_id} not owned by citizen {citizen_id}")
        return conversation

    def delete_conversation(self, conversation_id: int, citizen_id: int) -> bool:
        self.get_owned_or_raise(conversation_id, citizen_id)
        return self._repo.delete_conversation(conversation_id)

    def list_messages(self, conversation_id: int, citizen_id: int) -> list[Message]:
        self.get_owned_or_raise(conversation_id, citizen_id)
        return self._repo.get_messages(conversation_id)

    def preview(self, conversation: Conversation) -> str:
        return conversation.title or "Nowe pytanie"

    def ensure_title(self, conversation: Conversation, prompt: str) -> None:
        """Set the conversation title from the first question if it has none."""
        if conversation.title:
            return
        title = prompt.strip().splitlines()[0][: self._title_max] if prompt.strip() else None
        if title:
            self._repo.update_conversation(conversation.id, {"title": title})

    #
    # used by the background run executor
    #
    def history(self, conversation_id: int) -> list[dict[str, str]]:
        """Prior turns as {role, content} for the LLM — prose only."""
        return [
            {"role": m.role.value, "content": m.content} for m in self._repo.get_messages(conversation_id) if m.content
        ]

    def create_assistant_message(self, conversation_id: int, content: str, run_id: int) -> Message:
        return self._repo.create_message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=content,
            run_id=run_id,
        )

    def update_conversation(self, conversation_id: int, citizen_id: int, values: dict[str, Any]) -> Conversation:
        self.get_owned_or_raise(conversation_id, citizen_id)
        return self._repo.update_conversation(conversation_id, values)
