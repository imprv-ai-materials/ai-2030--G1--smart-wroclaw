"use client";

/**
 * Profile — the resident's chat history. Opened from the avatar menu after
 * login. Each conversation resumes on the map via `/?chat=<id>`.
 */

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, LogIn, MessagesSquare } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";
import { chatApi } from "@/lib/chat-api";
import { cn, formatDateTime } from "@/lib/utils";

export default function ProfilePage() {
  const { token, isLoading: authLoading } = useAuth();

  const conversations = useQuery({
    queryKey: ["chat-conversations"],
    queryFn: () => chatApi.listConversations(),
    enabled: !!token,
  });

  const list = conversations.data ?? [];

  return (
    <div className="mx-auto w-full max-w-md px-4 py-6 md:max-w-2xl md:py-10">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Wróć do mapy
      </Link>

      <h1 className="mt-4 text-2xl font-semibold tracking-tight">Moje rozmowy</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Historia Twoich rozmów z asystentem miasta.
      </p>

      {authLoading || (!!token && conversations.isLoading) ? (
        <div className="mt-6 space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      ) : !token ? (
        <div className="mt-8 flex flex-col items-center gap-3 rounded-xl border border-dashed p-8 text-center">
          <LogIn className="size-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Zaloguj się, aby zobaczyć historię rozmów.
          </p>
          <Link
            href="/auth/login"
            className={cn(buttonVariants({ variant: "default" }), "w-full max-w-xs")}
          >
            Zaloguj się
          </Link>
        </div>
      ) : list.length === 0 ? (
        <p className="mt-8 rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
          Nie masz jeszcze żadnych rozmów.
        </p>
      ) : (
        <ul className="mt-6 space-y-2">
          {list.map((conversation) => (
            <li key={conversation.id}>
              <Link
                href={`/?chat=${conversation.id}`}
                className="group flex items-center gap-3 rounded-xl border bg-card p-3.5 transition-colors hover:bg-muted/50"
              >
                <MessagesSquare className="size-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">
                    {conversation.title || "Rozmowa"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatDateTime(conversation.updated_at)}
                  </p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
