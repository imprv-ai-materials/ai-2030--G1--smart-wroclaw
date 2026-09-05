import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format an ISO timestamp for Polish readers, or `null` if absent/invalid. */
export function formatDateTime(value?: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("pl-PL", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export type ExpiryInfo = {
  /** The event has an expiry window at all (citizen-filed events do). */
  hasExpiry: boolean;
  /** Its window has already lapsed — it's off the public map. */
  expired: boolean;
  /** Short Polish label, e.g. "Wygasa za 3 godz." / "Wygasło". */
  label: string | null;
};

/**
 * Describe an event's 24h visibility window relative to now. Drives the
 * countdown + "Wygasło" state shown next to the author's prolong button.
 */
export function eventExpiry(expiresAt?: string | null): ExpiryInfo {
  if (!expiresAt) return { hasExpiry: false, expired: false, label: null };
  const end = new Date(expiresAt);
  if (Number.isNaN(end.getTime())) {
    return { hasExpiry: false, expired: false, label: null };
  }
  const ms = end.getTime() - Date.now();
  if (ms <= 0) return { hasExpiry: true, expired: true, label: "Wygasło" };

  const minutes = Math.round(ms / 60_000);
  if (minutes < 60) {
    return { hasExpiry: true, expired: false, label: `Wygasa za ${minutes} min` };
  }
  const hours = Math.round(minutes / 60);
  if (hours < 48) {
    return { hasExpiry: true, expired: false, label: `Wygasa za ${hours} godz.` };
  }
  const days = Math.round(hours / 24);
  return { hasExpiry: true, expired: false, label: `Wygasa za ${days} dni` };
}
