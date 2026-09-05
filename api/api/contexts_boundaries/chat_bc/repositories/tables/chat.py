from pypika.queries import Table

# See migration 0006_chat. Conversations are anonymous (user_id NULL) until
# the resident logs in to file an event.
chat_conversations_table = Table("chat_conversations")
chat_messages_table = Table("chat_messages")
