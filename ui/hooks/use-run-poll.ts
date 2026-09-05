"use client";

import { useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { assistantApi, type RunStatus } from "@/lib/assistant-api";

const POLL_MS = 1200;

const isInFlight = (status?: RunStatus) =>
  status === "queued" || status === "running";

/** Shared react-query keys for the assistant surface. */
export const assistantKeys = {
  conversations: ["assistant", "conversations"] as const,
  messages: (id: number | null) => ["assistant", "messages", id] as const,
  activeRun: (id: number | null) => ["assistant", "active-run", id] as const,
  events: (id: number | null, runId: string | null) =>
    ["assistant", "events", id, runId] as const,
};

/**
 * Polls a conversation's active run (and its events) every ~1.2s while a run
 * is in flight. When the run finishes, the message thread is invalidated so the
 * assistant's answer is refetched. Returns `isRunning` for the "myśli…" state.
 */
export function useRunPoll(conversationId: number | null) {
  const queryClient = useQueryClient();
  const lastEventId = useRef(0);
  const wasInFlight = useRef(false);

  const activeRun = useQuery({
    queryKey: assistantKeys.activeRun(conversationId),
    queryFn: () => assistantApi.getActiveRun(conversationId as number),
    enabled: conversationId != null,
    refetchInterval: (query) =>
      isInFlight(query.state.data?.status ?? undefined) ? POLL_MS : false,
  });

  const run = activeRun.data ?? null;
  const runId = run?.id ?? null;
  const running = isInFlight(run?.status);

  // Poll run events while the run is in flight (used for progress signalling).
  const events = useQuery({
    queryKey: assistantKeys.events(conversationId, runId),
    queryFn: async () => {
      const res = await assistantApi.getRunEvents(
        conversationId as number,
        runId as string,
        lastEventId.current,
      );
      if (res.last_event_id) lastEventId.current = res.last_event_id;
      return res.events;
    },
    enabled: conversationId != null && runId != null && running,
    refetchInterval: () => (running ? POLL_MS : false),
  });

  // When a run transitions out of flight, the assistant answer is ready.
  useEffect(() => {
    if (wasInFlight.current && !running) {
      queryClient.invalidateQueries({
        queryKey: assistantKeys.messages(conversationId),
      });
      lastEventId.current = 0;
    }
    wasInFlight.current = running;
  }, [running, conversationId, queryClient]);

  return { run, isRunning: running, events: events.data ?? [] };
}
