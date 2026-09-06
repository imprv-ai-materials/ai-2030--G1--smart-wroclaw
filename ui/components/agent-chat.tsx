"use client";

/**
 * The unified chat for the home entry point — talks to the orchestrator
 * (`/chat/turn`, one synchronous turn). The orchestrator routes each message to
 * search / add / answer; on a search it hands back filters, which we lift to the
 * parent via `onSearch` so the map + strip update. Replies render as Markdown.
 */

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { LogIn, Loader2, SendHorizonal } from "lucide-react";
import { toast } from "sonner";

import { AddEventForm } from "@/components/add-event-form";
import { MarkdownMessage } from "@/components/markdown-message";
import { EventCard } from "@/components/event-card";
import { Button, buttonVariants } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { APIError } from "@/lib/api-client";
import { chatApi, chatSocketUrl } from "@/lib/chat-api";
import type { ChatFormField, ChatProgress, ChatTrace, ChatTurnInput, ChatTurnStatus } from "@/lib/chat-api";
import type {
  CityEvent,
  EventFilters,
  EventType,
  ReportCategory,
} from "@/lib/events-api";
import { cn } from "@/lib/utils";

type ChatMsg = {
  role: "user" | "assistant";
  content: string;
  results?: CityEvent[];
  // Add-flow interactive state carried on the assistant turn.
  form?: ChatFormField[];
  ready?: boolean;
  status?: ChatTurnStatus;
  // Per-turn agent trace — present only for ADMIN accounts (the API gates it).
  trace?: ChatTrace;
  // The server message id (to match live WS progress) + a "still thinking" flag +
  // the streamed component names.
  messageId?: number;
  pending?: boolean;
  liveSteps?: string[];
};

function readChatId(): number | null {
  if (typeof window === "undefined") return null;
  const raw = new URLSearchParams(window.location.search).get("chat");
  const id = raw ? Number(raw) : NaN;
  return Number.isFinite(id) && id > 0 ? id : null;
}

type ServerMessage = { id: number; role: "USER" | "ASSISTANT"; content: string; data?: Record<string, unknown> };

/** A persisted message → the chat's view model (assistant payload lives in `data`). */
function toChatMsg(m: ServerMessage): ChatMsg {
  if (m.role === "USER") return { role: "user", content: m.content, messageId: m.id };
  const data = m.data ?? {};
  return {
    role: "assistant",
    content: m.content,
    messageId: m.id,
    pending: data.status === "pending" && !m.content,
    results:
      (data.results as CityEvent[] | undefined) ??
      (data.created ? [data.created as CityEvent] : (data.duplicates as CityEvent[] | undefined)) ??
      undefined,
    form: (data.form as ChatFormField[] | undefined) ?? undefined,
    ready: (data.ready as boolean | undefined) ?? undefined,
    status: (data.status as ChatTurnStatus | undefined) ?? undefined,
    trace: (data.trace as ChatTrace | undefined) ?? undefined,
  };
}

export function AgentChat({
  seed = "",
  onSearch,
  onOpenEvent,
}: {
  seed?: string;
  onSearch?: (filters: EventFilters) => void;
  onOpenEvent?: (event: CityEvent) => void;
}) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState(seed);
  const [pending, setPending] = useState(false);
  // Resume the conversation named in `?chat=<id>` (the server keeps the history).
  const [conversationId, setConversationId] = useState<number | null>(readChatId);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.focus();
    ta.setSelectionRange(ta.value.length, ta.value.length);
  }, []);

  // On resume (opened with a ?chat=<id>), load the stored turns so the
  // conversation shows its history.
  const resumedId = useRef(conversationId);
  useEffect(() => {
    const id = resumedId.current;
    if (id == null) return;
    let cancelled = false;
    chatApi
      .getMessages(id)
      .then((msgs) => {
        if (!cancelled) setMessages(msgs.map(toChatMsg));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  // Live progress over the WebSocket: the worker streams a `step` per component,
  // then `done` when the assistant message is finalized (we refetch server truth).
  const onSearchRef = useRef(onSearch);
  onSearchRef.current = onSearch;
  useEffect(() => {
    if (conversationId == null) return;
    const ws = new WebSocket(chatSocketUrl(conversationId));
    ws.onmessage = (ev) => {
      let msg: ChatProgress;
      try {
        msg = JSON.parse(ev.data as string) as ChatProgress;
      } catch {
        return;
      }
      if (msg.type === "step") {
        setMessages((ms) =>
          ms.map((m) =>
            m.messageId === msg.message_id ? { ...m, liveSteps: [...(m.liveSteps ?? []), msg.component] } : m,
          ),
        );
      } else if (msg.type === "done") {
        chatApi
          .getMessages(conversationId)
          .then((all) => {
            setMessages(all.map(toChatMsg));
            const fin = all.find((mm) => mm.id === msg.message_id);
            const data = (fin?.data ?? {}) as Record<string, unknown>;
            if (data.intent === "search" && data.filters && onSearchRef.current) {
              const f = data.filters as Record<string, unknown>;
              onSearchRef.current({
                type: (f.type_ as EventType) ?? undefined,
                category: (f.category as ReportCategory) ?? undefined,
                district: (f.district as string) ?? undefined,
                q: (f.q as string) ?? undefined,
              });
            }
          })
          .catch(() => {});
        setPending(false);
      }
    };
    return () => ws.close();
  }, [conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

  // One turn, whatever its shape: prose from the box, inline-form answers, or a
  // confirm click. `displayText` is what the resident's bubble shows.
  async function sendTurn(input: ChatTurnInput & { displayText: string }) {
    if (pending) return;
    // Optimistically show the resident's message + a pending assistant bubble the
    // WebSocket fills as the worker streams progress; `pending` clears on `done`.
    setMessages((m) => [
      ...m,
      { role: "user", content: input.displayText },
      { role: "assistant", content: "", pending: true, liveSteps: [] },
    ]);
    setPending(true);
    try {
      const res = await chatApi.turn({
        text: input.text,
        fields: input.fields,
        action: input.action,
        conversationId,
      });
      if (res.conversation_id) {
        setConversationId(res.conversation_id);
        const url = new URL(window.location.href);
        url.searchParams.set("chat", String(res.conversation_id));
        window.history.replaceState(null, "", url);
      }
      // Tag the pending bubble with its server id so incoming WS steps match it.
      setMessages((m) =>
        m.map((mm) => (mm.pending && mm.messageId == null ? { ...mm, messageId: res.message_id ?? undefined } : mm)),
      );
    } catch (err) {
      toast.error(err instanceof APIError ? err.message : "Coś poszło nie tak.");
      setMessages((m) => m.filter((mm) => !mm.pending));
      setPending(false);
    }
  }

  function submitText() {
    const text = input.trim();
    if (!text || pending) return;
    setInput("");
    void sendTurn({ text, displayText: text });
  }

  function handleSubmitForm(values: Record<string, string>, summary: string) {
    void sendTurn({ fields: values, displayText: summary });
  }

  function handleConfirm() {
    void sendTurn({ action: "confirm", displayText: "Potwierdzam zgłoszenie" });
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-2 text-center">
            <h3 className="text-base font-semibold">Asystent miasta</h3>
            <p className="max-w-xs text-sm text-muted-foreground">
              Zgłoś awarię lub zdarzenie, wyszukaj co dzieje się w mieście albo
              zapytaj o Wrocław — napisz naturalnie.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {messages.map((message, i) => (
              <ChatBubble
                key={i}
                message={message}
                isLast={i === messages.length - 1}
                pending={pending}
                onOpenEvent={onOpenEvent}
                onSubmitForm={handleSubmitForm}
                onConfirm={handleConfirm}
              />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <form
        className="flex items-end gap-2 border-t p-3"
        onSubmit={(e) => {
          e.preventDefault();
          submitText();
        }}
      >
        <Textarea
          ref={taRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submitText();
            }
          }}
          placeholder="Napisz wiadomość…"
          rows={1}
          className="max-h-40 min-h-11 flex-1 resize-none"
          disabled={pending}
        />
        <Button
          type="submit"
          size="icon"
          aria-label="Wyślij"
          disabled={!input.trim() || pending}
        >
          {pending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <SendHorizonal className="size-4" />
          )}
        </Button>
      </form>
    </div>
  );
}

function ChatBubble({
  message,
  isLast,
  pending,
  onOpenEvent,
  onSubmitForm,
  onConfirm,
}: {
  message: ChatMsg;
  isLast: boolean;
  pending: boolean;
  onOpenEvent?: (event: CityEvent) => void;
  onSubmitForm: (values: Record<string, string>, summary: string) => void;
  onConfirm: () => void;
}) {
  const isUser = message.role === "user";
  // Interactive controls only live on the most recent assistant turn — older
  // widgets are historical and shouldn't accept new input.
  const interactive = !isUser && isLast;
  return (
    <div className={cn("flex flex-col gap-1.5", isUser ? "items-end" : "items-start")}>
      <div
        className={cn(
          "max-w-[90%] rounded-2xl px-4 py-2.5 text-sm",
          isUser
            ? "bg-primary whitespace-pre-wrap text-primary-foreground"
            : "bg-muted text-foreground",
        )}
      >
        {isUser ? (
          message.content
        ) : message.pending ? (
          <PendingProgress steps={message.liveSteps ?? []} />
        ) : (
          <MarkdownMessage content={message.content} />
        )}
      </div>

      {message.results && message.results.length > 0 ? (
        <div className="flex w-full flex-col gap-1.5">
          {message.results.slice(0, 6).map((event) => (
            <EventCard
              key={event.id}
              event={event}
              onClick={() => onOpenEvent?.(event)}
            />
          ))}
          {message.results.length > 6 ? (
            <p className="px-1 text-xs text-muted-foreground">
              …i {message.results.length - 6} więcej na mapie
            </p>
          ) : null}
        </div>
      ) : null}

      {/* Inline follow-up widgets for the missing fields. */}
      {interactive && message.form && message.form.length > 0 ? (
        <div className="w-full pt-0.5">
          <AddEventForm
            fields={message.form}
            disabled={pending}
            onSubmit={onSubmitForm}
          />
        </div>
      ) : null}

      {/* Draft complete — confirm, log in, or a note about e-mail confirmation. */}
      {interactive && message.ready ? (
        message.status === "login_required" ? (
          <Link
            href="/auth/login"
            className={cn(buttonVariants({ size: "sm" }), "gap-2")}
          >
            <LogIn className="size-4" />
            Zaloguj się, aby dodać
          </Link>
        ) : message.status === "email_unconfirmed" ? (
          <Link
            href="/auth/change-password"
            className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
          >
            Potwierdź adres e-mail
          </Link>
        ) : (
          <Button size="sm" disabled={pending} onClick={onConfirm}>
            Potwierdź zgłoszenie
          </Button>
        )
      ) : null}

      {/* ADMIN-only per-turn agent trace (component · data · tokens · model). The
          API only sends `trace` to ADMIN accounts, so this simply renders when present. */}
      {!isUser && message.trace ? <AgentTrace trace={message.trace} /> : null}
    </div>
  );
}

function asText(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

function AgentTrace({ trace }: { trace: ChatTrace }) {
  return (
    <details className="w-full max-w-[90%] self-start text-xs text-muted-foreground">
      <summary className="inline-flex cursor-pointer select-none items-center py-0.5 list-none marker:content-none [&::-webkit-details-marker]:hidden hover:text-foreground hover:underline">
        Trace — {trace.steps.length}{" "}
        {trace.steps.length === 1 ? "komponent" : "komponenty"} · {trace.llm_calls} wyw. LLM ·{" "}
        {trace.total_tokens} tok.
      </summary>
      <div className="mt-1.5 space-y-2 border-l pl-3">
        {trace.steps.map((step, i) => (
          <div key={i} className="space-y-0.5">
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-mono font-semibold text-foreground">{step.component}</span>
              <span className="font-mono tabular-nums">
                {step.models.length ? step.models.join(", ") : "—"} · {step.prompt_tokens}+
                {step.completion_tokens} tok
              </span>
            </div>
            {step.input != null ? (
              <div className="break-all font-mono">
                <span className="opacity-60">in </span>
                {asText(step.input)}
              </div>
            ) : null}
            {step.output != null ? (
              <div className="break-all font-mono">
                <span className="opacity-60">out </span>
                {asText(step.output)}
              </div>
            ) : null}
          </div>
        ))}
        <div className="border-t pt-1 font-mono tabular-nums">
          Σ {trace.prompt_tokens}+{trace.completion_tokens} = {trace.total_tokens} tokenów
        </div>
      </div>
    </details>
  );
}

// Live "still thinking" indicator — the current pipeline stage, streamed over the WS.
function PendingProgress({ steps }: { steps: string[] }) {
  const LABELS: Record<string, string> = {
    guardrails_agent: "Sprawdzam temat",
    event_extractor: "Rozumiem wiadomość",
    router_agent: "Wybieram działanie",
    geo_resolver: "Ustalam lokalizację",
    search_agent: "Szukam zdarzeń",
    analytics_agent: "Liczę",
    report_agent: "Przygotowuję zgłoszenie",
    "events_service.create": "Zapisuję zgłoszenie",
  };
  const last = steps[steps.length - 1];
  return (
    <span className="inline-flex items-center gap-2 text-muted-foreground">
      <Loader2 className="size-4 animate-spin" />
      {last ? `${LABELS[last] ?? last}…` : "Myślę…"}
    </span>
  );
}
