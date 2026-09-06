"""Persistence for agent runs + their component steps (see migration 0008).

The worker (the main agent's Inngest function) opens a run, appends one step per
component as it completes, then finalizes the run onto the assistant message it
produced. The API reads runs back to expose them (ADMIN) and rehydrate the trace.
"""

from datetime import datetime, timezone
from typing import Any

from api.adapters.db import DBClient
from api.contexts_boundaries.chat_bc.models import AgentRun, AgentRunStep, RunStatus
from api.contexts_boundaries.chat_bc.repositories.tables.runs import (
    agent_run_steps_table,
    agent_runs_table,
)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class AgentRunsRepository:
    def __init__(self, db_client: DBClient) -> None:
        self._db = db_client

    def create_run(self, conversation_id: int, intent: str | None = None) -> AgentRun:
        row = self._db.create_one(
            agent_runs_table,
            {"conversation_id": conversation_id, "intent": intent, "status": RunStatus.RUNNING.value},
        )
        return AgentRun.from_dict(row)

    def add_step(
        self,
        run_id: int,
        seq: int,
        component: str,
        *,
        status: RunStatus = RunStatus.DONE,
        input: Any = None,
        output: Any = None,
        models: list[str] | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> AgentRunStep:
        row = self._db.create_one(
            agent_run_steps_table,
            {
                "run_id": run_id,
                "seq": seq,
                "component": component,
                "status": status.value,
                "input": input,
                "output": output,
                "models": models or [],
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "finished_at": _now() if status is not RunStatus.RUNNING else None,
            },
        )
        return AgentRunStep.from_dict(row)

    def finalize_run(
        self,
        run_id: int,
        *,
        message_id: int | None,
        status: RunStatus,
        intent: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        error: str | None = None,
    ) -> None:
        self._db.update_one(
            agent_runs_table,
            {"id": run_id},
            {
                "message_id": message_id,
                "status": status.value,
                "intent": intent,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "error": error,
                "finished_at": _now(),
            },
        )

    def get_run(self, run_id: int) -> AgentRun | None:
        row = self._db.get_one(agent_runs_table, {"id": run_id})
        if row is None:
            return None
        return AgentRun.from_dict(row, steps=self._steps(run_id))

    def get_run_for_message(self, message_id: int) -> AgentRun | None:
        row = self._db.get_one(agent_runs_table, {"message_id": message_id})
        if row is None:
            return None
        return AgentRun.from_dict(row, steps=self._steps(row["id"]))

    def _steps(self, run_id: int) -> list[AgentRunStep]:
        rows = self._db.get_many(agent_run_steps_table, {"run_id": run_id}, order_by="seq")
        return [AgentRunStep.from_dict(r) for r in rows]
