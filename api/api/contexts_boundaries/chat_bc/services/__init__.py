"""Chat bounded-context services.

The chat "main agent" no longer lives here — it moved to `api/ai/main_agent` as a
versioned, composed agent (`AbstractMainAgent`). The chat REST + Inngest surfaces
resolve it off the container as `bootstrap.main_agent` and call `run_turn(...)`.
"""
