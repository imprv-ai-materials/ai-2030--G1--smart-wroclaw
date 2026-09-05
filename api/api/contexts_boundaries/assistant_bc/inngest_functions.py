"""Background execution of an assistant Q&A turn.

The REST layer persists the user message + a queued run and fires
`smart_wroclaw/assistant.run`. This function — hosted on the worker — runs the
agent and writes the answer back. The blocking LLM call is offloaded to a thread
so it never stalls the worker's event loop.
"""

import anyio.to_thread
import inngest
from api.bootstrap import get_bootstrap
from api.inngest_app import EVENT_ASSISTANT_RUN, inngest_client


@inngest_client.create_function(
    fn_id="assistant-run",
    trigger=inngest.TriggerEvent(event=EVENT_ASSISTANT_RUN),
    # One in-flight execution per run id; a duplicate event is a no-op.
    singleton=inngest.Singleton(key="event.data.run_id", mode="skip"),
    retries=1,
)
async def assistant_run(ctx: inngest.Context) -> dict:
    run_id = int(ctx.event.data["run_id"])
    bootstrap = get_bootstrap()
    await anyio.to_thread.run_sync(bootstrap.assistant_runs_service.execute_run, run_id)
    run = bootstrap.assistant_runs_service.get_run(run_id)
    return {"run_id": run_id, "status": run.status.value if run else "unknown"}


ASSISTANT_INNGEST_FUNCTIONS = [assistant_run]
