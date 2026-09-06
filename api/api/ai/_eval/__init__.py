"""Shared, cross-agent evaluation harness.

One runner scores any agent at any version on a chosen dataset, driven by that
agent's `evaluations/*.yaml` spec. See `api/api/ai/evaluate.py` for the CLI and
`harness.py` for the engine + per-agent adapters.
"""
