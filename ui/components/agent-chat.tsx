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
import { chatApi } from "@/lib/chat-api";
import type { ChatFormField, ChatTrace, ChatTurnInput, ChatTurnStatus } from "@/lib/chat-api";
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
};

function readChatId(): number | null {
  if (typeof window === "undefined") return null;
  const raw = new URLSearchParams(window.location.search).get("chat");
  const id = raw ? Number(raw) : NaN;
  return Number.isFinite(id) && id > 0 ? id : null;
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
        if (cancelled) return;
        setMessages(
          msgs.map((m) => {
            if (m.role === "USER") {
              return { role: "user" as const, content: m.content };
            }
            const data = m.data ?? {};
            return {
              role: "assistant" as const,
              content: m.content,
              form: (data.form as ChatFormField[] | undefined) ?? undefined,
              ready: (data.ready as boolean | undefined) ?? undefined,
              status: (data.status as ChatTurnStatus | undefined) ?? undefined,
              trace: (data.trace as ChatTrace | undefined) ?? undefined,
            };
          }),
        );
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

  // One turn, whatever its shape: prose from the box, inline-form answers, or a
  // confirm click. `displayText` is what the resident's bubble shows.
  async function sendTurn(input: ChatTurnInput & { displayText: string }) {
    if (pending) return;
    setMessages((m) => [...m, { role: "user", content: input.displayText }]);
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
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: res.reply,
          // Search results, add-time duplicate candidates, and a freshly-filed
          // event all render as the same clickable event cards.
          results:
            res.results ??
            (res.created ? [res.created] : res.duplicates) ??
            undefined,
          form: res.form ?? undefined,
          ready: res.ready ?? undefined,
          status: res.status,
          trace: res.trace ?? undefined,
        },
      ]);
      if (res.intent === "search" && res.filters && onSearch) {
        onSearch({
          type: (res.filters.type_ as EventType) ?? undefined,
          category: (res.filters.category as ReportCategory) ?? undefined,
          district: res.filters.district ?? undefined,
          q: res.filters.q ?? undefined,
        });
      }
    } catch (err) {
      toast.error(err instanceof APIError ? err.message : "Coś poszło nie tak.");
    } finally {
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
            {pending ? (
              <div className="flex items-center gap-2 self-start rounded-2xl bg-muted px-4 py-2.5 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
                Myślę…
              </div>
            ) : null}
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
        {isUser ? message.content : <MarkdownMessage content={message.content} />}
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
            {step.input ? (
              <div className="break-all font-mono">
                <span className="opacity-60">in </span>
                {step.input}
              </div>
            ) : null}
            {step.output ? (
              <div className="break-all font-mono">
                <span className="opacity-60">out </span>
                {step.output}
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
