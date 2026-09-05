/**
 * Typed client for the "Zapytaj o miasto" assistant (city maintenance Q&A).
 *
 * Runs are asynchronous: POST a run, then poll the active run + its events
 * until the run reaches `done`, at which point the assistant message is
 * appended and the thread can be refetched. See `hooks/use-run-poll.ts`.
 */

import { api } from "@/lib/api-client";

export type MessageRole = "USER" | "ASSISTANT";

export type RunStatus = "queued" | "running" | "done" | "failed" | "cancelled";

export type Conversation = {
  id: number;
  citizen_id: number;
  title: string;
  created_at: string;
  updated_at: string;
};

/** List item shape (includes a short preview of the latest message). */
export type ConversationSummary = {
  id: number;
  title: string;
  preview: string | null;
  created_at: string;
  updated_at: string;
};

export type Message = {
  id: number;
  conversation_id: number;
  role: MessageRole;
  content: string;
  created_at: string;
};

export type AssistantRun = {
  id: string;
  conversation_id: number;
  status: RunStatus;
  error: string | null;
  created_at: string;
  finished_at: string | null;
};

export type RunEvent = {
  id: number;
  run_id: string;
  type: string;
  data: unknown;
  created_at: string;
};

export const assistantApi = {
  listConversations: () =>
    api.get<{ conversations: ConversationSummary[] }>("/conversations"),

  createConversation: (body?: { title?: string }) =>
    api.post<Conversation>("/conversations", body ?? {}),

  getConversation: (id: number) => api.get<Conversation>(`/conversations/${id}`),

  deleteConversation: (id: number) => api.delete<void>(`/conversations/${id}`),

  listMessages: (id: number) =>
    api.get<{ messages: Message[] }>(`/conversations/${id}/messages`),

  startRun: (id: number, prompt: string) =>
    api.post<{ run: AssistantRun; user_message: Message }>(
      `/conversations/${id}/runs`,
      { prompt },
    ),

  getActiveRun: (id: number) =>
    api.get<AssistantRun | null>(`/conversations/${id}/runs/active`),

  getRun: (id: number, runId: string) =>
    api.get<AssistantRun>(`/conversations/${id}/runs/${runId}`),

  getRunEvents: (id: number, runId: string, since = 0) =>
    api.get<{ events: RunEvent[]; last_event_id: number }>(
      `/conversations/${id}/runs/${runId}/events?since=${since}`,
    ),
};
