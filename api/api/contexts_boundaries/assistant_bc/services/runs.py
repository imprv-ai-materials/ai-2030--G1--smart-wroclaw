"""Run lifecycle for the assistant Q&A turns.

`start_run` is the synchronous half (persist the user message + a queued run);
the REST layer then fires the Inngest event and the worker calls
`execute_run`, which runs the agent and writes the answer back. Every state
transition is mirrored into `run_events` so the UI can poll live status.
"""

from dataclasses import dataclass
from datetime import datetime

from api.ai.assistant_agent import AbstractAssistantAgent
from api.contexts_boundaries.assistant_bc.models import (
    AssistantRun,
    Message,
    MessageRole,
    RunEvent,
    RunStatus,
)
from api.contexts_boundaries.assistant_bc.repositories import AbstractConversationsRepository
from api.contexts_boundaries.assistant_bc.services.conversations import ConversationsService
from api.shared.exceptions import ConflictError
from loguru import logger


class ActiveRunExistsError(ConflictError):
    pass


@dataclass
class StartRunResult:
    run: AssistantRun
    user_message: Message


class RunsService:
    def __init__(
        self,
        repository: AbstractConversationsRepository,
        conversations_service: ConversationsService,
        agent: AbstractAssistantAgent,
    ) -> None:
        self._repo = repository
        self._conversations = conversations_service
        self._agent = agent

    def start_run(self, conversation_id: int, prompt: str) -> StartRunResult:
        if self._repo.get_active_run(conversation_id) is not None:
            raise ActiveRunExistsError("a run is already in progress for this conversation")
        user_message = self._repo.create_message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=prompt,
        )
        run = self._repo.create_run(conversation_id=conversation_id, user_message_id=user_message.id)
        self._repo.append_run_event(run.id, conversation_id, type="queued")
        return StartRunResult(run=run, user_message=user_message)

    def get_run(self, run_id: int) -> AssistantRun | None:
        return self._repo.get_run(run_id)

    def get_active_run(self, conversation_id: int) -> AssistantRun | None:
        return self._repo.get_active_run(conversation_id)

    def get_run_events(self, run_id: int, since: int = 0) -> list[RunEvent]:
        return self._repo.get_run_events(run_id, since=since)

    #
    # WORKER — the background execution of one turn
    #
    def execute_run(self, run_id: int) -> None:
        run = self._repo.get_run(run_id)
        if run is None:
            logger.warning("execute_run: run {} vanished", run_id)
            return
        if run.status != RunStatus.QUEUED:
            logger.info("execute_run: run {} not queued (status={}) — skipping", run_id, run.status)
            return

        conversation_id = run.conversation_id
        self._repo.update_run(run_id, status=RunStatus.RUNNING.value, started_at=datetime.utcnow())
        self._repo.append_run_event(run_id, conversation_id, type="running")
        try:
            question = self._current_question(run)
            history = self._conversations.history(conversation_id)
            answer = self._agent.answer(question=question, history=history)
            message = self._conversations.create_assistant_message(conversation_id, content=answer, run_id=run_id)
            self._repo.update_run(
                run_id,
                status=RunStatus.DONE.value,
                assistant_message_id=message.id,
                finished_at=datetime.utcnow(),
            )
            self._repo.append_run_event(run_id, conversation_id, type="done", data={"message_id": message.id})
        except Exception as exc:  # noqa: BLE001
            logger.exception("assistant run {} failed", run_id)
            self._repo.update_run(run_id, status=RunStatus.FAILED.value, error=str(exc), finished_at=datetime.utcnow())
            self._repo.append_run_event(run_id, conversation_id, type="failed", data={"error": str(exc)})

    def _current_question(self, run: AssistantRun) -> str:
        if run.user_message_id is None:
            return ""
        for m in self._repo.get_messages(run.conversation_id):
            if m.id == run.user_message_id:
                return m.content
        return ""
