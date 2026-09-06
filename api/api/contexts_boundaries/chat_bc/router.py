"""REST seam for the chat orchestrator (the "main agent").

POST /chat/turn runs one interactive turn synchronously, PERSISTS it, and returns
the structured result plus the `conversation_id`. Conversations are anonymous
until the resident logs in (a valid bearer), at which point the account is
attached — so a filed report can be tied to a real user. Prior turns are
replayed to the orchestrator as memory (so a report continues across turns).
"""

from typing import Any

import inngest
from api.bootstrap import Bootstrap, get_bootstrap_dep
from api.contexts_boundaries.auth_bc.dependencies import authenticate, optional_user
from api.contexts_boundaries.auth_bc.models import User
from api.contexts_boundaries.chat_bc import ChatConversation, ChatMessage, ChatRole
from api.contexts_boundaries.chat_bc.schemas import ChatTurnRequest, ChatTurnResponse
from api.inngest_app import EVENT_EVENT_GEOCODE, inngest_client
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder

chat_router = APIRouter(prefix="/chat", tags=["chat"])

_HISTORY_LIMIT = 20


def _prior_draft(messages: list[ChatMessage]) -> dict[str, Any] | None:
    """The report accumulated so far — the most recent assistant turn's stored
    draft (the add flow persists it so widget answers survive across turns)."""
    for message in reversed(messages):
        if message.role == ChatRole.ASSISTANT and isinstance(message.data, dict):
            draft = message.data.get("draft")
            if draft:
                return draft
    return None


@chat_router.post("/turn", response_model=ChatTurnResponse)
async def chat_turn(
    body: ChatTurnRequest,
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
    current: User | None = Depends(optional_user),
) -> Any:
    repo = bootstrap.chat_repository
    user_id = current.id if current else None

    conversation = repo.get_conversation(body.conversation_id) if body.conversation_id else None
    if conversation is None:
        conversation = repo.create_conversation(user_id=user_id)
    elif user_id is not None and conversation.user_id is None:
        # The resident just logged in — attach the account to their conversation.
        repo.attach_user(conversation.id, user_id)

    messages = repo.list_messages(conversation.id, limit=_HISTORY_LIMIT)
    # Memory = the conversation so far (before this turn), each assistant turn
    # carrying its intent so the router can continue a flow in progress.
    history = [{"role": m.role.value, "content": m.content, "intent": m.data.get("intent")} for m in messages]
    prior_draft = _prior_draft(messages)

    repo.add_message(
        conversation.id,
        ChatRole.USER,
        body.text,
        data={"fields": body.fields, "action": body.action} if (body.fields or body.action) else None,
    )

    result = bootstrap.main_agent.run_turn(
        body.text,
        history,
        fields=body.fields,
        action=body.action,
        prior_draft=prior_draft,
        reporter_id=user_id,
        reporter_confirmed=bool(current and current.email_confirmed),
    )

    # An event was just filed — enrich its coordinates in the background (HERE).
    created = result.get("created")
    if result.get("geocode") and created is not None:
        await inngest_client.send(inngest.Event(name=EVENT_EVENT_GEOCODE, data={"event_id": created.id}))

    repo.add_message(
        conversation.id,
        ChatRole.ASSISTANT,
        result.get("reply", ""),
        data=jsonable_encoder(
            {
                "intent": result.get("intent"),
                "filters": result.get("filters"),
                "missing_fields": result.get("missing_fields"),
                # Persist the accumulated draft so the next turn keeps the
                # inline-form answers (they aren't recoverable from text alone),
                # plus the interactive state so a reload rehydrates the widgets.
                "draft": result.get("draft"),
                "form": result.get("form"),
                "ready": result.get("ready"),
                "status": result.get("status"),
                "created_event_id": created.id if created is not None else None,
            }
        ),
    )
    if conversation.title is None and body.text.strip():
        repo.set_title(conversation.id, body.text[:60])

    # `geocode` is an internal signal to this endpoint, not part of the API.
    result.pop("geocode", None)
    return {"conversation_id": conversation.id, **result}


@chat_router.get("/conversations", response_model=list[ChatConversation])
def list_conversations(
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
    current: User = Depends(authenticate),
) -> list[ChatConversation]:
    """The logged-in resident's conversation history (profile page)."""
    return bootstrap.chat_repository.list_conversations(current.id)


@chat_router.get("/conversations/{conversation_id}/messages", response_model=list[ChatMessage])
def conversation_messages(
    conversation_id: int,
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
    current: User | None = Depends(optional_user),
) -> list[ChatMessage]:
    repo = bootstrap.chat_repository
    conversation = repo.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rozmowa nie istnieje")
    # Owned conversations are private to their owner; an anonymous conversation is
    # reachable by anyone holding its id (the id is the only key).
    if conversation.user_id is not None and (current is None or current.id != conversation.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="brak dostępu do rozmowy")
    return repo.list_messages(conversation_id, limit=200)
