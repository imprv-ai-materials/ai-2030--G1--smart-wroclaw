/**
 * Renders the structured, "reportable" side of a CityEvent: the top-level chips
 * (category / severity / subtype / district) plus the per-type `details` JSONB,
 * with human Polish labels. This is what turns an event from free text into
 * something a citizen can read at a glance — and the app can aggregate.
 */

import {
  categoryLabel,
  severityLabel,
  subtypeLabel,
  type CityEvent,
} from "@/lib/events-api";
import { formatDateTime } from "@/lib/utils";

// -- Polish labels for known detail keys -------------------------------------

const DETAIL_LABELS: Record<string, string> = {
  animal_species: "Gatunek",
  lost_or_found: "Status",
  animal_name: "Imię",
  animal_breed: "Rasa",
  animal_color: "Umaszczenie",
  animal_size: "Wielkość",
  animal_sex: "Płeć",
  has_collar: "Obroża",
  microchipped: "Zaczipowane",
  last_seen_at: "Ostatnio widziane",
  reward: "Nagroda",
  utility: "Media",
  planned: "Przerwa planowa",
  eta_restore: "Przywrócenie ok.",
  provider: "Dostawca",
  affected_area: "Obszar",
  closure_type: "Zamknięcie",
  detour_text: "Objazd",
  affected_lines: "Linie",
  organizer: "Organizator",
  is_free: "Wstęp wolny",
  price_text: "Cena",
  ticket_url: "Bilety",
  age_restriction: "Wiek",
  business_name: "Lokal",
  business_type: "Typ lokalu",
  discount_pct: "Rabat",
  promo_code: "Kod",
  signup_url: "Zapisy",
  volunteers_needed: "Wolontariusze",
  substitute: "Komunikacja zastępcza",
  cause: "Przyczyna",
  mitigation: "Działania",
  near_landmark: "W pobliżu",
  hazard_to: "Zagraża",
  reported_to: "Powiadomiono",
  advice: "Zalecenie",
  safety: "Bezpieczeństwo",
  pollutant: "Zanieczyszczenie",
  days_out: "Dni awarii",
  blocks: "Blokuje",
  hours: "Godziny",
  schedule: "Harmonogram",
  offer: "Oferta",
  audience: "Dla kogo",
  bring: "Zabierz ze sobą",
  distance_km: "Dystans (km)",
  gust_kmh: "Porywy (km/h)",
};

// Enum value → Polish display, keyed by the detail field.
const VALUE_LABELS: Record<string, Record<string, string>> = {
  animal_species: { CAT: "Kot", DOG: "Pies", BIRD: "Ptak", OTHER: "Inne" },
  lost_or_found: { LOST: "Zaginione", FOUND: "Znalezione" },
  animal_size: { SMALL: "Mały", MEDIUM: "Średni", LARGE: "Duży" },
  animal_sex: { M: "Samiec", F: "Samica", UNKNOWN: "Nieznana" },
  utility: { POWER: "Prąd", WATER: "Woda", GAS: "Gaz", HEAT: "Ciepło", INTERNET: "Internet" },
  closure_type: { FULL: "Całkowite", PARTIAL: "Częściowe", LANE: "Pas ruchu" },
  business_type: {
    CAFE: "Kawiarnia",
    RESTAURANT: "Restauracja",
    MALL: "Centrum handlowe",
    AQUAPARK: "Aquapark",
    RETAIL: "Sklep",
  },
};

function humanizeKey(key: string): string {
  return DETAIL_LABELS[key] ?? key.replace(/_/g, " ");
}

function isUrl(value: string): boolean {
  return /^https?:\/\//i.test(value);
}

// A bare ISO-8601 datetime like "2026-09-04T23:30:00+02:00".
function isIsoDateTime(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value);
}

function formatValue(key: string, value: unknown): string {
  if (typeof value === "boolean") return value ? "Tak" : "Nie";
  if (Array.isArray(value)) return value.map((v) => String(v)).join(", ");
  const raw = String(value);
  if (key === "discount_pct") return `-${raw}%`;
  if (isIsoDateTime(raw)) return formatDateTime(raw) ?? raw;
  return VALUE_LABELS[key]?.[raw] ?? raw;
}

// Keys already surfaced elsewhere (chips / dedicated rows) — skip in the list.
const SKIP_DETAIL_KEYS = new Set(["near_landmark"]);

export function EventDetailFacts({ event }: { event: CityEvent }) {
  const detailEntries = Object.entries(event.details ?? {}).filter(
    ([k, v]) => !SKIP_DETAIL_KEYS.has(k) && v != null && v !== "",
  );

  const hasChips =
    event.category || event.severity || event.subtype || event.district;
  const hasFacts =
    hasChips ||
    detailEntries.length > 0 ||
    event.contact_phone ||
    event.confirmations > 0 ||
    event.verified;

  if (!hasFacts) return null;

  return (
    <div className="mt-4 space-y-4">
      {hasChips ? (
        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
          {event.subtype ? (
            <Chip label="Rodzaj" value={subtypeLabel(event.subtype) ?? event.subtype} />
          ) : null}
          {event.category ? (
            <Chip label="Kategoria" value={categoryLabel(event.category) ?? event.category} />
          ) : null}
          {event.severity ? (
            <Chip label="Priorytet" value={severityLabel(event.severity) ?? event.severity} />
          ) : null}
          {event.district ? <Chip label="Osiedle" value={event.district} /> : null}
          {event.verified ? <Chip label="Status" value="Zweryfikowane" /> : null}
        </div>
      ) : null}

      {detailEntries.length > 0 ? (
        <dl className="grid grid-cols-1 gap-x-6 gap-y-2 rounded-lg border p-3.5 text-sm sm:grid-cols-2">
          {detailEntries.map(([key, value]) => (
            <div key={key} className="flex items-start justify-between gap-3">
              <dt className="text-muted-foreground">{humanizeKey(key)}</dt>
              <dd className="text-right font-medium">
                {typeof value === "string" && isUrl(value) ? (
                  <a
                    href={value}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline underline-offset-2"
                  >
                    Otwórz
                  </a>
                ) : (
                  formatValue(key, value)
                )}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}

      {event.contact_phone || event.confirmations > 0 ? (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-sm">
          {event.contact_phone ? (
            <span className="text-muted-foreground">
              Kontakt:{" "}
              <a
                href={`tel:${event.contact_phone}`}
                className="font-medium text-foreground underline underline-offset-2"
              >
                {event.contact_phone}
              </a>
            </span>
          ) : null}
          {event.confirmations > 0 ? (
            <span className="text-muted-foreground">
              Potwierdzenia:{" "}
              <span className="font-medium text-foreground">{event.confirmations}</span>
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Chip({ label, value }: { label: string; value: string }) {
  return (
    <span className="rounded-md border px-2 py-1">
      {label}: <span className="text-foreground">{value}</span>
    </span>
  );
}
