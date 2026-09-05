"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, SendHorizonal, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { assistantApi, type Message } from "@/lib/assistant-api";
import { APIError } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { assistantKeys, useRunPoll } from "@/hooks/use-run-poll";

export default function AssistantPage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [input, setInput] = useState("");

  const conversations = useQuery({
    queryKey: assistantKeys.conversations,
    queryFn: () => assistantApi.listConversations(),
  });

  // Auto-select the first conversation once the list loads.
  useEffect(() => {
    if (selectedId == null && conversations.data?.conversations.length) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot sync from loaded list
      setSelectedId(conversations.data.conversations[0].id);
    }
  }, [conversations.data, selectedId]);

  const messages = useQuery({
    queryKey: assistantKeys.messages(selectedId),
    queryFn: () => assistantApi.listMessages(selectedId as number),
    enabled: selectedId != null,
  });

  const { isRunning } = useRunPoll(selectedId);

  const createConversation = useMutation({
    mutationFn: (title?: string) => assistantApi.createConversation({ title }),
    onSuccess: (conv) => {
      queryClient.invalidateQueries({ queryKey: assistantKeys.conversations });
      setSelectedId(conv.id);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const deleteConversation = useMutation({
    mutationFn: (id: number) => assistantApi.deleteConversation(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: assistantKeys.conversations });
      if (selectedId === id) setSelectedId(null);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const startRun = useMutation({
    mutationFn: ({ conversationId, prompt }: { conversationId: number; prompt: string }) =>
      assistantApi.startRun(conversationId, prompt),
    onSuccess: (_data, { conversationId }) => {
      queryClient.invalidateQueries({ queryKey: assistantKeys.messages(conversationId) });
      queryClient.invalidateQueries({ queryKey: assistantKeys.activeRun(conversationId) });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  async function handleSend() {
    const prompt = input.trim();
    if (!prompt || startRun.isPending) return;

    let conversationId = selectedId;
    if (conversationId == null) {
      const conv = await createConversation.mutateAsync(prompt.slice(0, 60));
      conversationId = conv.id;
    }
    setInput("");
    await startRun.mutateAsync({ conversationId, prompt });
  }

  const list = conversations.data?.conversations ?? [];

  return (
    <div className="mx-auto grid h-[calc(100svh-3.5rem)] w-full max-w-6xl grid-cols-1 gap-0 md:grid-cols-[280px_1fr]">
      {/* Conversation list */}
      <aside className="hidden flex-col border-r md:flex">
        <div className="flex items-center justify-between px-4 py-3">
          <h2 className="text-sm font-semibold">Rozmowy</h2>
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label="Nowa rozmowa"
            onClick={() => {
              setSelectedId(null);
              setInput("");
            }}
          >
            <Plus className="size-4" />
          </Button>
        </div>
        <div className="flex-1 space-y-1 overflow-y-auto px-2 pb-4">
          {conversations.isLoading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))
          ) : list.length === 0 ? (
            <p className="px-2 py-4 text-sm text-muted-foreground">
              Brak rozmów. Zadaj pierwsze pytanie.
            </p>
          ) : (
            list.map((conv) => (
              <button
                key={conv.id}
                onClick={() => setSelectedId(conv.id)}
                className={cn(
                  "group flex w-full items-start gap-2 rounded-lg px-2.5 py-2 text-left transition-colors",
                  selectedId === conv.id
                    ? "bg-muted"
                    : "hover:bg-muted/60",
                )}
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {conv.title || "Nowa rozmowa"}
                  </p>
                  {conv.preview ? (
                    <p className="truncate text-xs text-muted-foreground">
                      {conv.preview}
                    </p>
                  ) : null}
                </div>
                <span
                  role="button"
                  tabIndex={-1}
                  aria-label="Usuń rozmowę"
                  className="mt-0.5 rounded p-0.5 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:text-destructive"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteConversation.mutate(conv.id);
                  }}
                >
                  <Trash2 className="size-4" />
                </span>
              </button>
            ))
          )}
        </div>
      </aside>

      {/* Message thread + composer */}
      <section className="flex min-h-0 flex-col">
        <MessageThread
          messages={messages.data?.messages ?? []}
          isLoading={selectedId != null && messages.isLoading}
          isEmpty={selectedId == null}
          isRunning={isRunning}
        />

        <div className="border-t p-4">
          <form
            className="mx-auto flex w-full max-w-3xl items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void handleSend();
            }}
          >
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void handleSend();
                }
              }}
              placeholder="Zapytaj o utrzymanie miasta, np. „Kiedy odbierane są odpady bio na Nadodrzu?”"
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
      </section>
    </div>
  );
}

function MessageThread({
  messages,
  isLoading,
  isEmpty,
  isRunning,
}: {
  messages: Message[];
  isLoading: boolean;
  isEmpty: boolean;
  isRunning: boolean;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isRunning]);

  if (isEmpty) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 px-4 text-center">
        <h1 className="text-2xl font-semibold">Zapytaj o miasto</h1>
        <p className="max-w-md text-muted-foreground">
          Asystent AI odpowie na pytania o utrzymanie Wrocławia. Zacznij od pytania
          poniżej — nowa rozmowa utworzy się automatycznie.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6">
        {isLoading ? (
          <>
            <Skeleton className="h-16 w-2/3" />
            <Skeleton className="ml-auto h-16 w-1/2" />
          </>
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
        )}
        {isRunning ? (
          <div className="flex items-center gap-2 self-start rounded-2xl bg-muted px-4 py-2.5 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Asystent myśli…
          </div>
        ) : null}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "USER";
  return (
    <div
      className={cn(
        "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap",
        isUser
          ? "self-end bg-primary text-primary-foreground"
          : "self-start bg-muted text-foreground",
      )}
    >
      {message.content}
    </div>
  );
}

function errorMessage(err: unknown) {
  if (err instanceof APIError) return err.message;
  return "Wystąpił błąd. Spróbuj ponownie.";
}
