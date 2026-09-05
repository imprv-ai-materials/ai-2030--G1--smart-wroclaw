"use client";

/**
 * The one event card used everywhere it appears — the bottom strip on the map
 * and the search results inside the chat. Width-agnostic (fills its container by
 * default; the strip constrains it via `className`). The badge row wraps rather
 * than overflowing when a type label is long (e.g. "Zaginione zwierzę").
 */

import { MapPin } from "lucide-react";

import { EventStatusBadge, EventTypeBadge } from "@/components/event-badges";
import { type CityEvent } from "@/lib/events-api";
import { cn } from "@/lib/utils";

export function EventCard({
  event,
  onClick,
  selected,
  className,
}: {
  event: CityEvent;
  onClick: () => void;
  selected?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={selected ? "true" : undefined}
      className={cn(
        "group flex w-full flex-col gap-1.5 rounded-lg border bg-card/95 p-2.5 text-left shadow-sm backdrop-blur transition-all hover:-translate-y-0.5 hover:shadow-md",
        selected ? "border-foreground ring-1 ring-foreground" : "border-border",
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <EventTypeBadge type={event.type} />
        <EventStatusBadge status={event.status} />
      </div>
      <p className="line-clamp-1 text-sm font-medium">{event.title}</p>
      {event.location_text ? (
        <p className="flex items-center gap-1 text-xs text-muted-foreground">
          <MapPin className="size-3 shrink-0" />
          <span className="truncate">{event.location_text}</span>
        </p>
      ) : null}
    </button>
  );
}
