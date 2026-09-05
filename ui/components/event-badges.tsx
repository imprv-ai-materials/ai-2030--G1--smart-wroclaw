import { Badge } from "@/components/ui/badge";
import { EventGlyph } from "@/components/event-glyph";
import {
  EVENT_STATUS_LABELS,
  EVENT_TYPE_LABELS,
  type EventStatus,
  type EventType,
} from "@/lib/events-api";

export function EventTypeBadge({ type }: { type: EventType }) {
  // Same shape glyph as the map pins + legend, so a symbol reads the same
  // wherever it appears (map, cards, detail page).
  return (
    <Badge variant="outline" className="gap-1">
      <EventGlyph type={type} className="size-3" />
      {EVENT_TYPE_LABELS[type]}
    </Badge>
  );
}

export function EventStatusBadge({ status }: { status: EventStatus }) {
  // Active stands out (filled grayscale); the rest are quieter outlines.
  return (
    <Badge variant={status === "ACTIVE" ? "default" : "secondary"}>
      {EVENT_STATUS_LABELS[status]}
    </Badge>
  );
}
