"use client";

/**
 * Real, minimalist map of Wrocław. Renders OpenStreetMap data via OpenFreeMap's
 * grayscale styles (positron in light mode, dark in dark mode), so it stays
 * strictly black & white and follows the app theme — free, no API key, no
 * limits. Each geolocated event is plotted with a simple grayscale glyph,
 * distinguished by shape:
 *   ISSUE = triangle, ALARM = circle, VENUE = square, PROMOTION = diamond,
 *   MISSING_PET = paw, HAZARD = octagon, OUTAGE = bolt, ROADWORKS = cone,
 *   COMMUNITY = paired circles.
 *
 * The interactive MapLibre canvas lives in ./city-map-canvas and is loaded
 * client-side only (it touches `window`); this wrapper stays SSR-safe and owns
 * the legend + empty state.
 */

import dynamic from "next/dynamic";

import { EventGlyph } from "@/components/event-glyph";
import { cn } from "@/lib/utils";
import {
  EVENT_TYPE_LABELS,
  type CityEvent,
  type EventType,
} from "@/lib/events-api";

const MapCanvas = dynamic(
  () => import("./city-map-canvas").then((m) => m.CityMapCanvas),
  {
    ssr: false,
    loading: () => (
      <div className="size-full min-h-64 w-full animate-pulse rounded-xl border bg-muted" />
    ),
  },
);

export function CityMap({
  events,
  interactive = true,
  showLegend = true,
  showEmptyHint = true,
  className,
  canvasClassName,
  onEventClick,
  focus,
  myReporterId,
}: {
  events: CityEvent[];
  interactive?: boolean;
  showLegend?: boolean;
  /**
   * Show the "no located events" note under the canvas. Off for the full-canvas
   * map (e.g. the home screen), where the canvas fills its box via `h-full` and
   * an appended note would overflow the container — the surrounding UI already
   * signals emptiness there.
   */
  showEmptyHint?: boolean;
  className?: string;
  /** Overrides the canvas box (e.g. `h-full rounded-none border-0` to fill). */
  canvasClassName?: string;
  /** Forwarded to the canvas; replaces the default pin navigation. */
  onEventClick?: (id: number) => void;
  /** Forwarded to the canvas; flies the map to this point when it changes. */
  focus?: { id: number; lng: number; lat: number } | null;
  /** The logged-in resident's id; their own events render in the accent colour. */
  myReporterId?: number | null;
}) {
  const pins = events.filter(
    (e): e is CityEvent & { lat: number; lng: number } =>
      e.lat != null && e.lng != null,
  );

  return (
    <div className={cn("w-full", className)}>
      <MapCanvas
        events={pins}
        interactive={interactive}
        onEventClick={onEventClick}
        focus={focus}
        myReporterId={myReporterId}
        className={cn(
          "h-64 w-full overflow-hidden rounded-xl border",
          canvasClassName,
        )}
      />

      {showLegend ? (
        <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
          {(Object.keys(EVENT_TYPE_LABELS) as EventType[]).map((type) => (
            <li key={type} className="flex items-center gap-1.5">
              <EventGlyph type={type} className="size-3.5 text-foreground" />
              {EVENT_TYPE_LABELS[type]}
            </li>
          ))}
        </ul>
      ) : null}

      {showEmptyHint && pins.length === 0 ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Brak zdarzeń z lokalizacją na mapie.
        </p>
      ) : null}
    </div>
  );
}
