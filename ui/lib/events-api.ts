/**
 * Typed client for city events shown to citizens — issues, alarms, venues and
 * promotions plotted on the map and listed on the home screen. Reading is
 * public; creating an event requires a confirmed-email bearer token.
 */

import { api } from "@/lib/api-client";

export type EventType =
  | "ISSUE"
  | "ALARM"
  | "VENUE"
  | "PROMOTION"
  | "MISSING_PET"
  | "HAZARD"
  | "OUTAGE"
  | "ROADWORKS"
  | "COMMUNITY";
export type EventStatus = "ACTIVE" | "RESOLVED" | "SCHEDULED" | "EXPIRED";

export type ReportCategory =
  | "WATER"
  | "ROADS"
  | "WASTE"
  | "GREENERY"
  | "LIGHTING"
  | "PUBLIC_TRANSPORT"
  | "OTHER";

export type EventFilters = {
  status?: EventStatus;
  type?: EventType;
  category?: ReportCategory;
  district?: string;
  q?: string;
};

export type CityEvent = {
  id: number;
  type: EventType;
  status: EventStatus;
  title: string;
  description: string;
  category: string | null;
  severity: string | null;
  location_text: string | null;
  address: string | null;
  lat: number | null;
  lng: number | null;
  source: string | null; // "CITY" | "CITIZEN" | "BUSINESS"
  reporter_id: number | null; // citizens.id when a resident filed it
  starts_at: string | null;
  ends_at: string | null;
  // Structured / reportable fields (migration 0005). `details` carries the
  // per-type long tail (animal_species, utility, discount_pct, …).
  subtype: string | null;
  district: string | null;
  resolved_at: string | null;
  expires_at: string | null;
  confirmations: number;
  verified: boolean;
  contact_phone: string | null;
  image_url: string | null;
  details: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type CreateEventInput = {
  type: EventType;
  title: string;
  description: string;
  category?: string;
  severity?: string;
  location_text?: string;
  address?: string;
  lat?: number;
  lng?: number;
  starts_at?: string;
  ends_at?: string;
  subtype?: string;
  district?: string;
  expires_at?: string;
  contact_phone?: string;
  image_url?: string;
  details?: Record<string, unknown>;
};

// -- Polish display labels ---------------------------------------------------

export const EVENT_TYPE_LABELS: Record<EventType, string> = {
  ISSUE: "Awaria",
  ALARM: "Alarm",
  VENUE: "Miejsce",
  PROMOTION: "Promocja",
  MISSING_PET: "Zaginione zwierzę",
  HAZARD: "Zagrożenie",
  OUTAGE: "Przerwa w dostawie",
  ROADWORKS: "Roboty",
  COMMUNITY: "Akcja społeczna",
};

export const EVENT_STATUS_LABELS: Record<EventStatus, string> = {
  ACTIVE: "Aktywne",
  RESOLVED: "Rozwiązane",
  SCHEDULED: "Zaplanowane",
  EXPIRED: "Zakończone",
};

/** Longer labels used in the report form's type select. */
export const EVENT_TYPE_FORM_LABELS: Record<EventType, string> = {
  ISSUE: "Awaria",
  ALARM: "Alarm",
  VENUE: "Miejsce/Wydarzenie",
  PROMOTION: "Promocja",
  MISSING_PET: "Zaginione zwierzę",
  HAZARD: "Zagrożenie",
  OUTAGE: "Przerwa w dostawie (prąd/woda/gaz)",
  ROADWORKS: "Roboty / utrudnienia",
  COMMUNITY: "Akcja społeczna / wolontariat",
};

export const EVENT_TYPE_OPTIONS = Object.keys(EVENT_TYPE_LABELS) as EventType[];

export const CATEGORY_LABELS: Record<ReportCategory, string> = {
  WATER: "Woda",
  ROADS: "Drogi",
  WASTE: "Odpady",
  GREENERY: "Zieleń",
  LIGHTING: "Oświetlenie",
  PUBLIC_TRANSPORT: "Transport",
  OTHER: "Inne",
};

export const CATEGORY_OPTIONS = Object.keys(CATEGORY_LABELS) as ReportCategory[];

export const EVENT_STATUS_OPTIONS = Object.keys(
  EVENT_STATUS_LABELS,
) as EventStatus[];

export const SOURCE_LABELS: Record<string, string> = {
  CITY: "Miasto",
  CITIZEN: "Mieszkaniec",
  BUSINESS: "Firma",
};

// -- Structured-field value translations (chips on the event card/detail) -----

export const SEVERITY_LABELS: Record<string, string> = {
  LOW: "Niski",
  MEDIUM: "Średni",
  HIGH: "Wysoki",
  CRITICAL: "Krytyczny",
};

/**
 * Polish labels for the open-ended `subtype`. Extracted subtypes may be novel,
 * so callers should fall back to a humanised form for anything not listed here.
 */
export const SUBTYPE_LABELS: Record<string, string> = {
  // ISSUE — infrastructure
  POTHOLE: "Dziura w jezdni",
  STREETLIGHT: "Oświetlenie",
  WATER_MAIN: "Magistrala wodociągowa",
  OVERFLOW_BIN: "Przepełniony kosz",
  FALLEN_TREE: "Powalone drzewo",
  SHELTER_DAMAGE: "Uszkodzona wiata",
  MARKINGS: "Oznakowanie poziome",
  OVERGROWN: "Zaniedbana zieleń",
  // ALARM
  FLOOD_WARNING: "Ostrzeżenie powodziowe",
  AIR_QUALITY: "Jakość powietrza",
  WEATHER: "Ostrzeżenie pogodowe",
  TRAM_SUSPENDED: "Zawieszony tramwaj",
  // ROADWORKS
  BRIDGE_REPAIR: "Remont mostu",
  TRACK_REPAIR: "Remont torowiska",
  STREET_CLOSURE: "Zamknięcie ulicy",
  // VENUE
  MARKET: "Targ / jarmark",
  CONCERT: "Koncert",
  EXHIBITION: "Wystawa",
  SPORT: "Wydarzenie sportowe",
  FAMILY: "Wydarzenie rodzinne",
  // PROMOTION
  FOOD: "Gastronomia",
  RETAIL: "Handel",
  LEISURE: "Rozrywka",
  // MISSING_PET
  PET_LOST: "Zaginięcie",
  PET_FOUND: "Znalezienie",
  // HAZARD
  DOWNED_POWER_LINE: "Zerwana linia energetyczna",
  AGGRESSIVE_ANIMAL: "Agresywne zwierzę",
  ICE: "Gołoledź",
  // OUTAGE
  POWER_PLANNED: "Planowa przerwa prądu",
  GAS: "Awaria gazu",
  // COMMUNITY
  CLEANUP: "Sprzątanie",
  BLOOD_DRIVE: "Zbiórka krwi",
  NEIGHBOUR_HELP: "Pomoc sąsiedzka",
};

/** Humanise an UPPER_SNAKE code as a last resort ("FOO_BAR" → "Foo bar"). */
export function humanizeCode(value: string): string {
  const spaced = value.replace(/_/g, " ").toLowerCase().trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function subtypeLabel(value: string | null | undefined): string | null {
  if (!value) return null;
  return SUBTYPE_LABELS[value] ?? humanizeCode(value);
}

/** String-safe category label — `CityEvent.category` is a plain string. */
export function categoryLabel(value: string | null | undefined): string | null {
  if (!value) return null;
  return (CATEGORY_LABELS as Record<string, string>)[value] ?? value;
}

export function severityLabel(value: string | null | undefined): string | null {
  if (!value) return null;
  return SEVERITY_LABELS[value] ?? value;
}

export function isEventType(value: string | null | undefined): value is EventType {
  return value != null && (EVENT_TYPE_OPTIONS as string[]).includes(value);
}

export const eventsApi = {
  listEvents: (params?: EventFilters) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.type) qs.set("type", params.type);
    if (params?.category) qs.set("category", params.category);
    if (params?.district) qs.set("district", params.district);
    if (params?.q) qs.set("q", params.q);
    const query = qs.toString();
    return api.get<{ events: CityEvent[] }>(`/events${query ? `?${query}` : ""}`);
  },

  getEvent: (id: number) => api.get<CityEvent>(`/events/${id}`),

  createEvent: (body: CreateEventInput) =>
    api.post<CityEvent>("/events", body, { auth: true }),

  // Extend an event's visibility window by another 24h. Author-only on the
  // server (403 otherwise); returns the updated event with its new `expires_at`.
  prolongEvent: (id: number) =>
    api.post<CityEvent>(`/events/${id}/prolong`, undefined, { auth: true }),
};
