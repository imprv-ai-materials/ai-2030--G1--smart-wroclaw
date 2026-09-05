"""REST router for the assistant Q&A layer (mounted under /api/v1).

  GET    /conversations                              list the citizen's threads
  POST   /conversations                              open a new thread
  GET    /conversations/{id}                          fetch a thread
  DELETE /conversations/{id}                          delete a thread
  GET    /conversations/{id}/messages                 list messages
  POST   /conversations/{id}/runs                     ask a question (fires Inngest)
  GET    /conversations/{id}/runs/active              current queued/running run (or null)
  GET    /conversations/{id}/runs/{run_id}            fetch a run
  GET    /conversations/{id}/runs/{run_id}/events     tail run events (?since=<event_id>)

The endpoints only ever persist + `inngest_client.send(...)`; the LLM answer is
produced on the worker (see inngest_functions.py).
"""

import inngest
from api.bootstrap import Bootstrap
from api.contexts_boundaries.assistant_bc.models import AssistantRun, Conversation
from api.contexts_boundaries.assistant_bc.rest.schemas import (
    ConversationCreateRequest,
    ConversationListResponse,
    ConversationSummary,
    MessagesResponse,
    RunEventsResponse,
    RunStartRequest,
    RunStartResponse,
)
from api.contexts_boundaries.assistant_bc.services import ActiveRunExistsError
from api.contexts_boundaries.auth_bc import CitizenContext, citizen, get_bootstrap_dep
from api.inngest_app import EVENT_ASSISTANT_RUN, inngest_client
from api.shared.exceptions import AccessDeniedError, NotFoundError
from fastapi import APIRouter, Depends, HTTPException, status

conversations_router = APIRouter(prefix="/conversations", tags=["assistant"])


def _owned(bootstrap: Bootstrap, conversation_id: int, ctx: CitizenContext) -> Conversation:
    try:
        return bootstrap.conversations_service.get_owned_or_raise(conversation_id, ctx.citizen_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rozmowa nie istnieje") from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="brak dostępu") from exc


@conversations_router.get("", response_model=ConversationListResponse)
def list_conversations(
    ctx: CitizenContext = Depends(citizen),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> ConversationListResponse:
    svc = bootstrap.conversations_service
    return ConversationListResponse(
        conversations=[
            ConversationSummary(
                id=c.id,
                title=c.title,
                preview=svc.preview(c),
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in svc.list_conversations(ctx.citizen_id)
        ]
    )


@conversations_router.post("", response_model=Conversation)
def create_conversation(
    body: ConversationCreateRequest,
    ctx: CitizenContext = Depends(citizen),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> Conversation:
    return bootstrap.conversations_service.create_conversation(citizen_id=ctx.citizen_id, title=body.title)


@conversations_router.get("/{conversation_id}", response_model=Conversation)
def get_conversation(
    conversation_id: int,
    ctx: CitizenContext = Depends(citizen),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> Conversation:
    return _owned(bootstrap, conversation_id, ctx)


@conversations_router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int,
    ctx: CitizenContext = Depends(citizen),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> None:
    _owned(bootstrap, conversation_id, ctx)
    bootstrap.conversations_service.delete_conversation(conversation_id, ctx.citizen_id)


@conversations_router.get("/{conversation_id}/messages", response_model=MessagesResponse)
def list_messages(
    conversation_id: int,
    ctx: CitizenContext = Depends(citizen),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> MessagesResponse:
    _owned(bootstrap, conversation_id, ctx)
    return MessagesResponse(messages=bootstrap.conversations_repository.get_messages(conversation_id))


@conversations_router.post(
    "/{conversation_id}/runs", response_model=RunStartResponse, status_code=status.HTTP_202_ACCEPTED
)
async def start_run(
    conversation_id: int,
    body: RunStartRequest,
    ctx: CitizenContext = Depends(citizen),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> RunStartResponse:
    conversation = _owned(bootstrap, conversation_id, ctx)
    bootstrap.conversations_service.ensure_title(conversation, body.prompt)
    try:
        result = bootstrap.assistant_runs_service.start_run(conversation_id=conversation_id, prompt=body.prompt)
    except ActiveRunExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trwa już inne pytanie") from exc

    await inngest_client.send(
        inngest.Event(name=EVENT_ASSISTANT_RUN, data={"run_id": result.run.id, "conversation_id": conversation_id})
    )
    return RunStartResponse(run=result.run, user_message=result.user_message)


@conversations_router.get("/{conversation_id}/runs/active", response_model=AssistantRun | None)
def get_active_run(
    conversation_id: int,
    ctx: CitizenContext = Depends(citizen),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> AssistantRun | None:
    _owned(bootstrap, conversation_id, ctx)
    return bootstrap.assistant_runs_service.get_active_run(conversation_id)


@conversations_router.get("/{conversation_id}/runs/{run_id}", response_model=AssistantRun)
def get_run(
    conversation_id: int,
    run_id: int,
    ctx: CitizenContext = Depends(citizen),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> AssistantRun:
    _owned(bootstrap, conversation_id, ctx)
    run = bootstrap.assistant_runs_service.get_run(run_id)
    if run is None or run.conversation_id != conversation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run nie istnieje")
    return run


@conversations_router.get("/{conversation_id}/runs/{run_id}/events", response_model=RunEventsResponse)
def get_run_events(
    conversation_id: int,
    run_id: int,
    since: int = 0,
    ctx: CitizenContext = Depends(citizen),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> RunEventsResponse:
    _owned(bootstrap, conversation_id, ctx)
    run = bootstrap.assistant_runs_service.get_run(run_id)
    if run is None or run.conversation_id != conversation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run nie istnieje")
    events = bootstrap.assistant_runs_service.get_run_events(run_id, since=since)
    last_event_id = events[-1].id if events else since
    return RunEventsResponse(events=events, last_event_id=last_event_id)
