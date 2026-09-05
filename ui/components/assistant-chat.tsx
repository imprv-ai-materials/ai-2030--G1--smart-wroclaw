"use client";

/**
 * Compact assistant chat used inside the home right-side panel. Self-contained:
 * it owns a single conversation that is created lazily on the first message,
 * then reuses the shared run-polling hook so the "myśli…" state and answer
 * refresh behave exactly like the full /assistant page.
 *
 * `seed` pre-fills the composer (e.g. "Chcę zgłosić awarię: ") so an action
 * button opens straight into the right reporting intent.
 */

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, SendHorizonal } from "lucide-react";
import { toast } from "sonner";

import { MarkdownMessage } from "@/components/markdown-message";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { assistantApi, type Message } from "@/lib/assistant-api";
import { APIError } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { assistantKeys, useRunPoll } from "@/hooks/use-run-poll";

export function AssistantChat({ seed = "" }: { seed?: string }) {
  const queryClient = useQueryClient();
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [input, setInput] = useState(seed);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Focus the composer and drop the caret after any seeded text.
  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.focus();
    const end = ta.value.length;
    ta.setSelectionRange(end, end);
  }, []);

  const messages = useQuery({
    queryKey: assistantKeys.messages(conversationId),
    queryFn: () => assistantApi.listMessages(conversationId as number),
    enabled: conversationId != null,
  });

  const { isRunning } = useRunPoll(conversationId);

  const createConversation = useMutation({
    mutationFn: (title?: string) => assistantApi.createConversation({ title }),
    onError: (err) => toast.error(errorMessage(err)),
  });

  const startRun = useMutation({
    mutationFn: ({ id, prompt }: { id: number; prompt: string }) =>
      assistantApi.startRun(id, prompt),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: assistantKeys.messages(id) });
      queryClient.invalidateQueries({ queryKey: assistantKeys.activeRun(id) });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const list = messages.data?.messages ?? [];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [list.length, isRunning]);

  async function handleSend() {
    const prompt = input.trim();
    if (!prompt || startRun.isPending) return;

    let id = conversationId;
    if (id == null) {
      const conv = await createConversation.mutateAsync(prompt.slice(0, 60));
      id = conv.id;
      setConversationId(id);
      queryClient.invalidateQueries({ queryKey: assistantKeys.conversations });
    }
    setInput("");
    await startRun.mutateAsync({ id, prompt });
  }

  const isEmpty = conversationId == null && list.length === 0;

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {isEmpty ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-2 text-center">
            <h3 className="text-base font-semibold">Zapytaj o miasto</h3>
            <p className="max-w-xs text-sm text-muted-foreground">
              Asystent AI pomoże zgłosić sprawę lub odpowie na pytania o Wrocław.
              Napisz wiadomość — rozmowa utworzy się automatycznie.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {messages.isLoading ? (
              <>
                <div className="h-14 w-2/3 animate-pulse rounded-2xl bg-muted" />
                <div className="ml-auto h-14 w-1/2 animate-pulse rounded-2xl bg-muted" />
              </>
            ) : (
              list.map((message) => <Bubble key={message.id} message={message} />)
            )}
            {isRunning ? (
              <div className="flex items-center gap-2 self-start rounded-2xl bg-muted px-4 py-2.5 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
                Asystent myśli…
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
          void handleSend();
        }}
      >
        <Textarea
          ref={taRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void handleSend();
            }
          }}
          placeholder="Napisz wiadomość…"
          rows={1}
          className="max-h-40 min-h-11 flex-1 resize-none"
          disabled={startRun.isPending}
        />
        <Button
          type="submit"
          size="icon"
          aria-label="Wyślij"
          disabled={!input.trim() || startRun.isPending}
        >
          {startRun.isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <SendHorizonal className="size-4" />
          )}
        </Button>
      </form>
    </div>
  );
}

function Bubble({ message }: { message: Message }) {
  const isUser = message.role === "USER";
  return (
    <div
      className={cn(
        "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm",
        isUser
          ? "self-end bg-primary whitespace-pre-wrap text-primary-foreground"
          : "self-start bg-muted text-foreground",
      )}
    >
      {isUser ? message.content : <MarkdownMessage content={message.content} />}
    </div>
  );
}

function errorMessage(err: unknown) {
  if (err instanceof APIError) return err.message;
  return "Wystąpił błąd. Spróbuj ponownie.";
}
