from pypika.queries import Table

agent_runs_table = Table("agent_runs")
agent_run_steps_table = Table("agent_run_steps")
# See migration 0008_agent_runs:
#   agent_runs      (id, conversation_id, message_id, status, intent, tokens, error, …)
#   agent_run_steps (id, run_id, seq, component, status, input, output, models, tokens, …)
