"use client";

/**
 * Interactive MapLibre GL canvas — the client-only half of <CityMap>. Loaded
 * via next/dynamic({ ssr: false }) because MapLibre touches `window`.
 *
 * Basemap: OpenFreeMap (https://openfreemap.org) — genuinely free, no API key,
 * no registration, no request limits. We use its grayscale "positron" style in
 * light mode and "dark" in dark mode, so the map stays strictly black & white
 * and follows the app theme. Events are plotted as the same grayscale glyphs
 * used elsewhere, drawn as SVG marker elements that read their fill from the
 * `--foreground`/`--background` CSS variables (theme-aware for free).
 */

import "maplibre-gl/dist/maplibre-gl.css";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import * as maplibregl from "maplibre-gl";

import { cn } from "@/lib/utils";
import {
  EVENT_TYPE_LABELS,
  type CityEvent,
  type EventType,
} from "@/lib/events-api";

// MapLibre decodes vector tiles in a Web Worker it loads from
// `new URL('./maplibre-gl-worker.mjs', import.meta.url)`. Next/Turbopack doesn't
// emit that chunk, so the browser gets the app's HTML shell instead of JS and
// the worker never starts (tiles stay blank). We serve the worker + its shared
// chunk from /public (copied there by the "sync-map-worker" npm script) and
// point MapLibre at it. Same-origin, correct MIME → the worker loads.
maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");

// OpenFreeMap grayscale styles (free, keyless). Attribution is baked into the
// style JSON and rendered automatically by MapLibre.
const STYLE = {
  light: "https://tiles.openfreemap.org/styles/positron",
  dark: "https://tiles.openfreemap.org/styles/dark",
} as const;

// MapLibre uses [lng, lat] order. Rynek-ish center as a fallback view.
const WROCLAW: [number, number] = [17.0385, 51.1079];

export type LocatedEvent = CityEvent & { lat: number; lng: number };

// -- Grayscale SVG glyphs (mirror the legend shapes) -------------------------

function glyph(type: EventType, mine = false): string {
  const c = 12; // glyph is drawn in a 24×24 box, knocked out of the disc below
  const s = 6;
  // The glyph is the "hole" in the filled disc: knocked out in the colour that
  // contrasts the disc fill (background for grayscale pins, `--mine-foreground`
  // for the resident's accent-coloured pins). `hole` is the reverse — a cut that
  // shows the disc colour through again (e.g. the HAZARD centre dot).
  const knockout = mine ? "var(--mine-foreground)" : "var(--background)";
  const discFill = mine ? "var(--mine)" : "var(--foreground)";
  const style = `fill:${knockout};stroke:none;stroke-linejoin:round`;
  const hole = `fill:${discFill};stroke:none`;
  switch (type) {
    case "ISSUE":
      return `<polygon points="${c},${c - s} ${c - s},${c + s} ${c + s},${c + s}" style="${style}"/>`;
    case "ALARM":
      return `<circle cx="${c}" cy="${c}" r="${s - 1}" style="${style}"/>`;
    case "VENUE":
      return `<rect x="${c - s + 1}" y="${c - s + 1}" width="${(s - 1) * 2}" height="${(s - 1) * 2}" style="${style}"/>`;
    case "PROMOTION":
      return `<polygon points="${c},${c - s} ${c + s},${c} ${c},${c + s} ${c - s},${c}" style="${style}"/>`;
    case "MISSING_PET":
      // Paw: pad ellipse + four toes.
      return (
        `<ellipse cx="${c}" cy="${c + 2.5}" rx="3.9" ry="3.1" style="${style}"/>` +
        `<circle cx="${c - 4}" cy="${c - 1}" r="1.7" style="${style}"/>` +
        `<circle cx="${c - 1.3}" cy="${c - 3.7}" r="1.7" style="${style}"/>` +
        `<circle cx="${c + 1.9}" cy="${c - 3.7}" r="1.7" style="${style}"/>` +
        `<circle cx="${c + 4.2}" cy="${c - 1}" r="1.6" style="${style}"/>`
      );
    case "HAZARD":
      // Octagon with a hollow centre.
      return (
        `<polygon points="${c - 2.5},${c - s} ${c + 2.5},${c - s} ${c + s},${c - 2.5} ${c + s},${c + 2.5} ${c + 2.5},${c + s} ${c - 2.5},${c + s} ${c - s},${c + 2.5} ${c - s},${c - 2.5}" style="${style}"/>` +
        `<circle cx="${c}" cy="${c}" r="1.5" style="${hole}"/>`
      );
    case "OUTAGE":
      // Lightning bolt.
      return `<polygon points="${c + 0.8},${c - s} ${c - 3.4},${c + 0.9} ${c - 0.5},${c + 0.9} ${c - 1.5},${c + s} ${c + 3.8},${c - 1.3} ${c + 0.5},${c - 1.3}" style="${style}"/>`;
    case "ROADWORKS":
      // Cone silhouette (trapezoid).
      return `<polygon points="${c - 2.8},${c - 5.5} ${c + 2.8},${c - 5.5} ${c + s},${c + 5.5} ${c - s},${c + 5.5}" style="${style}"/>`;
    case "COMMUNITY":
      // Two overlapping circles.
      return (
        `<circle cx="${c - 3}" cy="${c}" r="3.6" style="${style}"/>` +
        `<circle cx="${c + 3}" cy="${c}" r="3.6" style="${style}"/>`
      );
  }
}

export function CityMapCanvas({
  events,
  interactive,
  className,
  onEventClick,
  focus,
  myReporterId,
}: {
  events: LocatedEvent[];
  interactive: boolean;
  className?: string;
  /** If provided, replaces the default "navigate to /events/:id" pin behavior. */
  onEventClick?: (id: number) => void;
  /** When set, the map flies to this point (e.g. the selected event). */
  focus?: { id: number; lng: number; lat: number } | null;
  /** The logged-in resident's id; their own events render in the accent colour. */
  myReporterId?: number | null;
}) {
  const router = useRouter();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);

  // Create the map once, on mount.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: isDark ? STYLE.dark : STYLE.light,
      center: WROCLAW,
      zoom: 11,
      interactive,
      attributionControl: { compact: true },
    });
    if (interactive) {
      map.addControl(
        new maplibregl.NavigationControl({ showCompass: false }),
        "top-right",
      );
    }
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // Created once; theme + markers are handled by the effects below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Swap the basemap style when the app theme changes. HTML markers persist
  // across setStyle, so they don't need to be re-added here.
  useEffect(() => {
    mapRef.current?.setStyle(isDark ? STYLE.dark : STYLE.light);
  }, [isDark]);

  // (Re)plot markers and fit the view whenever the events change. Keyed on a
  // stable signature so unrelated parent re-renders don't churn the markers.
  // `mine` is part of the key so pins recolour the moment the resident logs in.
  const signature = events
    .map(
      (e) =>
        `${e.id}:${e.lat}:${e.lng}:${e.type}:${e.title}:${
          myReporterId != null && e.reporter_id === myReporterId ? "m" : ""
        }`,
    )
    .join("|");
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    const coords: [number, number][] = [];
    for (const e of events) {
      const mine = myReporterId != null && e.reporter_id === myReporterId;
      const el = document.createElement("div");
      el.className = "event-marker";
      el.style.filter = "drop-shadow(0 1px 2px rgba(0,0,0,0.35))";
      // A filled disc (with a background ring to separate it from the map) and
      // the glyph knocked out of it — bigger + high-contrast so it's easy to
      // spot on the pale basemap. The resident's own events are filled with the
      // `--mine` accent instead of the grayscale foreground so they stand out.
      const disc = mine
        ? "fill:var(--mine);stroke:var(--background);stroke-width:1.5"
        : "fill:var(--foreground);stroke:var(--background);stroke-width:1.5";
      el.innerHTML = `<svg viewBox="0 0 24 24" width="${mine ? 38 : 34}" height="${mine ? 38 : 34}" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="11" style="${disc}"/>${glyph(e.type, mine)}</svg>`;
      el.title = `${EVENT_TYPE_LABELS[e.type]}: ${e.title}${mine ? " (Twoje zdarzenie)" : ""}`;
      if (interactive) {
        el.style.cursor = "pointer";
        el.setAttribute("role", "button");
        el.tabIndex = 0;
        const go = () =>
          onEventClick ? onEventClick(e.id) : router.push(`/events/${e.id}`);
        el.addEventListener("click", go);
        el.addEventListener("keydown", (ev) => {
          if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            go();
          }
        });
      }
      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([e.lng, e.lat])
        .addTo(map);
      markersRef.current.push(marker);
      coords.push([e.lng, e.lat]);
    }

    if (coords.length === 1) {
      map.easeTo({ center: coords[0], zoom: 14, duration: 0 });
    } else if (coords.length > 1) {
      const bounds = coords.reduce(
        (b, c) => b.extend(c),
        new maplibregl.LngLatBounds(coords[0], coords[0]),
      );
      map.fitBounds(bounds, { padding: 40, maxZoom: 15, duration: 0 });
    }
    // `events`, `interactive`, `router` are captured; `signature` gates re-runs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  // Fly to a focused event (e.g. when its card/pin is clicked). Offsets the
  // target so the pin lands in the area still visible beside the open panel:
  // left of the right-side panel on desktop, above the bottom sheet on mobile.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focus) return;
    const isDesktop =
      typeof window !== "undefined" &&
      window.matchMedia("(min-width: 768px)").matches;
    map.flyTo({
      center: [focus.lng, focus.lat],
      zoom: Math.max(map.getZoom(), 15),
      offset: isDesktop ? [-210, 0] : [0, -120],
      duration: 800,
      essential: true,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fly only when the focused id changes
  }, [focus?.id]);

  return <div ref={containerRef} className={cn(className)} />;
}
