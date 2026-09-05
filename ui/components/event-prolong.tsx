"use client";

/**
 * Author-only expiry control for an event. User-filed events drop off the
 * map 24h after they're posted (so stale reports don't pile up); the author —
 * and only the author — can keep theirs alive here. Renders nothing for anyone
 * who isn't signed in as the event's reporter, so it's safe to drop into any
 * event view.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, CalendarPlus } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { eventsApi, type CityEvent } from "@/lib/events-api";
import { cn, eventExpiry } from "@/lib/utils";

export function EventProlong({
  event,
  className,
}: {
  event: CityEvent;
  className?: string;
}) {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const prolong = useMutation({
    mutationFn: () => eventsApi.prolongEvent(event.id),
    onSuccess: (updated) => {
      toast.success("Przedłużono zdarzenie o 24 godziny");
      // Refresh the single event and every feed it might appear in.
      queryClient.setQueryData(["events", event.id], updated);
      queryClient.invalidateQueries({ queryKey: ["events"] });
    },
    onError: () => toast.error("Nie udało się przedłużyć zdarzenia"),
  });

  // Only the reporter sees this — a resident can only prolong their own events.
  const isMine = event.reporter_id != null && user?.id === event.reporter_id;
  if (!isMine) return null;

  const expiry = eventExpiry(event.expires_at);

  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 rounded-lg border bg-muted/40 px-3 py-2.5",
        className,
      )}
    >
      <div className="flex min-w-0 items-center gap-2 text-sm">
        <CalendarClock
          className="size-4 shrink-0"
          style={{ color: "var(--mine)" }}
        />
        <span className="min-w-0">
          <span className="font-medium">Twoje zdarzenie</span>
          {expiry.label ? (
            <span
              className="ml-1.5 text-muted-foreground"
              style={expiry.expired ? { color: "var(--mine)" } : undefined}
            >
              · {expiry.label}
            </span>
          ) : null}
        </span>
      </div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="shrink-0 gap-1.5"
        disabled={prolong.isPending}
        onClick={() => prolong.mutate()}
      >
        <CalendarPlus className="size-4" />
        {prolong.isPending ? "Przedłużanie…" : "Przedłuż o 24h"}
      </Button>
    </div>
  );
}
