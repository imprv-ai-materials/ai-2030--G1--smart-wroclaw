/**
 * Client for the chat orchestrator (the "main agent"). One synchronous turn:
 * POST /chat/turn → a Markdown `reply` plus intent-specific data. On `search`
 * the caller applies `filters` to the map; on `add` it can render the draft +
 * missing fields; `answer` is a plain Q&A reply.
 */

import { api } from "@/lib/api-client";
import type { CityEvent } from "@/lib/events-api";

export type ChatIntent = "search" | "add" | "answer";

export type ChatTurnStatus = "ok" | "blocked" | "login_required" | "email_unconfirmed";

export type ChatTurnFilters = {
  type_?: string | null;
  category?: string | null;
  district?: string | null;
  q?: string | null;
};

// One inline follow-up widget the chat renders to collect a missing field.
export type ChatFormFieldWidget = "select" | "text" | "textarea" | "datetime";
export type ChatFormField = {
  field: string;
  label: string;
  widget: ChatFormFieldWidget;
  required: boolean;
  options?: { value: string; label: string }[];
  placeholder?: string;
};

export type ChatTurnResult = {
  conversation_id: number;
  status: ChatTurnStatus;
  reply: string;
  reason?: string | null;
  intent?: ChatIntent | null;
  filters?: ChatTurnFilters | null;
  results?: CityEvent[] | null;
  draft?: Record<string, unknown> | null;
  missing_fields?: string[] | null;
  duplicates?: CityEvent[] | null;
  form?: ChatFormField[] | null;
  ready?: boolean | null;
  created?: CityEvent | null;
};

export type ChatTurnInput = {
  text?: string;
  conversationId?: number | null;
  fields?: Record<string, unknown>;
  action?: "confirm";
};

export type ChatConversationSummary = {
  id: number;
  title: string | null;
  created_at: string;
  updated_at: string;
};

export type ChatMessageOut = {
  id: number;
  role: "USER" | "ASSISTANT";
  content: string;
  data: Record<string, unknown>;
  created_at: string;
};

export const chatApi = {
  // `auth: true` attaches the bearer when the resident is logged in, so the
  // conversation can be tied to their account (anonymous otherwise). A turn can
  // carry prose (`text`), inline-form answers (`fields`), or a confirm `action`.
  turn: ({ text, conversationId, fields, action }: ChatTurnInput) =>
    api.post<ChatTurnResult>(
      "/chat/turn",
      {
        text: text ?? "",
        conversation_id: conversationId ?? undefined,
        fields: fields ?? undefined,
        action: action ?? undefined,
      },
      { auth: true },
    ),

  listConversations: () =>
    api.get<ChatConversationSummary[]>("/chat/conversations", { auth: true }),

  getMessages: (conversationId: number) =>
    api.get<ChatMessageOut[]>(`/chat/conversations/${conversationId}/messages`, {
      auth: true,
    }),
};
