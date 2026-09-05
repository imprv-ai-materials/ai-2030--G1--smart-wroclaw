/**
 * The canonical grayscale event glyphs, distinguished purely by shape:
 *   ISSUE = triangle, ALARM = circle, VENUE = square, PROMOTION = diamond,
 *   MISSING_PET = paw, HAZARD = octagon, OUTAGE = bolt, ROADWORKS = cone,
 *   COMMUNITY = paired circles.
 *
 * These are the same shapes the MapLibre pins draw (as a string in
 * ./city-map-canvas). Keeping the JSX version here lets the map legend AND the
 * type badges (event cards, detail page) share one source of truth, so a symbol
 * means the same thing wherever it appears.
 *
 * Pure SVG, no hooks or browser APIs — safe to render from server components.
 */

import { type EventType } from "@/lib/events-api";

/** A single grayscale marker glyph centered at (x, y). */
export function Glyph({
  type,
  x,
  y,
}: {
  type: EventType;
  x: number;
  y: number;
}) {
  const s = 6;
  // Solid, no stroke — matches the no-stroke map pins (city-map-canvas `glyph()`)
  // and reads cleanly at badge size, where a surface-coloured separation stroke
  // would show as a mismatched halo and hollow out thin shapes (e.g. the bolt).
  const common = { className: "fill-foreground" };
  switch (type) {
    case "ISSUE":
      return (
        <polygon
          {...common}
          points={`${x},${y - s} ${x - s},${y + s} ${x + s},${y + s}`}
        />
      );
    case "ALARM":
      return <circle {...common} cx={x} cy={y} r={s - 1} />;
    case "VENUE":
      return (
        <rect
          {...common}
          x={x - s + 1}
          y={y - s + 1}
          width={(s - 1) * 2}
          height={(s - 1) * 2}
        />
      );
    case "PROMOTION":
      return (
        <polygon
          {...common}
          points={`${x},${y - s} ${x + s},${y} ${x},${y + s} ${x - s},${y}`}
        />
      );
    case "MISSING_PET":
      // Paw: a pad ellipse + four toe beans.
      return (
        <g strokeLinejoin="round">
          <ellipse {...common} cx={x} cy={y + 2.5} rx={3.9} ry={3.1} />
          <circle {...common} cx={x - 4} cy={y - 1} r={1.7} />
          <circle {...common} cx={x - 1.3} cy={y - 3.7} r={1.7} />
          <circle {...common} cx={x + 1.9} cy={y - 3.7} r={1.7} />
          <circle {...common} cx={x + 4.2} cy={y - 1} r={1.6} />
        </g>
      );
    case "HAZARD":
      // Octagon (stop-sign) with a hollow centre.
      return (
        <g>
          <polygon
            {...common}
            strokeLinejoin="round"
            points={`${x - 2.5},${y - s} ${x + 2.5},${y - s} ${x + s},${y - 2.5} ${x + s},${y + 2.5} ${x + 2.5},${y + s} ${x - 2.5},${y + s} ${x - s},${y + 2.5} ${x - s},${y - 2.5}`}
          />
          <circle className="fill-background" cx={x} cy={y} r={1.5} />
        </g>
      );
    case "OUTAGE":
      // Lightning bolt.
      return (
        <polygon
          {...common}
          strokeLinejoin="round"
          points={`${x + 0.8},${y - s} ${x - 3.4},${y + 0.9} ${x - 0.5},${y + 0.9} ${x - 1.5},${y + s} ${x + 3.8},${y - 1.3} ${x + 0.5},${y - 1.3}`}
        />
      );
    case "ROADWORKS":
      // Cone silhouette (trapezoid, wide base).
      return (
        <polygon
          {...common}
          strokeLinejoin="round"
          points={`${x - 2.8},${y - 5.5} ${x + 2.8},${y - 5.5} ${x + s},${y + 5.5} ${x - s},${y + 5.5}`}
        />
      );
    case "COMMUNITY":
      // Two overlapping circles — a pair of people.
      return (
        <g>
          <circle {...common} cx={x - 3} cy={y} r={3.6} />
          <circle {...common} cx={x + 3} cy={y} r={3.6} />
        </g>
      );
  }
}

/**
 * Small, non-projected glyph in a 16×16 box — used by the map legend and by the
 * event type badge. Size/spacing come from `className` (e.g. "size-3.5").
 */
export function EventGlyph({
  type,
  className,
}: {
  type: EventType;
  className?: string;
}) {
  return (
    <svg viewBox="0 0 16 16" className={className} aria-hidden>
      <Glyph type={type} x={8} y={8} />
    </svg>
  );
}
