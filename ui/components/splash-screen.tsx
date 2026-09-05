"use client";

/**
 * Full-screen splash shown once per browser session. Pure black background with
 * the white wordmark; fades out after ~1.6s or on click. Whether it should show
 * is derived from the `sw_splash_seen` sessionStorage key via
 * `useSyncExternalStore`, so it renders nothing during SSR/hydration (no
 * mismatch) and unmounts cleanly once dismissed.
 */

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

import { cn } from "@/lib/utils";

const SESSION_KEY = "sw_splash_seen";
const FADE_MS = 500;

const listeners = new Set<() => void>();

function subscribe(callback: () => void): () => void {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

function getSnapshot(): boolean {
  try {
    return sessionStorage.getItem(SESSION_KEY) !== "1";
  } catch {
    return false;
  }
}

function getServerSnapshot(): boolean {
  return false;
}

function markSeen(): void {
  try {
    sessionStorage.setItem(SESSION_KEY, "1");
  } catch {
    /* sessionStorage unavailable */
  }
  for (const listener of listeners) listener();
}

export function SplashScreen() {
  const shouldShow = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot,
  );
  const [hiding, setHiding] = useState(false);

  const dismiss = useCallback(() => {
    setHiding(true);
    // After the fade, persist the flag — that flips the store and unmounts.
    window.setTimeout(markSeen, FADE_MS);
  }, []);

  useEffect(() => {
    if (!shouldShow) return;
    const timer = window.setTimeout(dismiss, 1600);
    return () => window.clearTimeout(timer);
  }, [shouldShow, dismiss]);

  if (!shouldShow) return null;

  return (
    <div
      onClick={dismiss}
      className={cn(
        "fixed inset-0 z-[100] flex cursor-pointer flex-col items-center justify-center bg-black text-white transition-opacity ease-out",
        hiding ? "opacity-0" : "opacity-100",
      )}
      style={{ transitionDuration: `${FADE_MS}ms` }}
      role="presentation"
    >
      <span className="text-3xl font-semibold tracking-tight md:text-4xl">
        Smart Wrocław
      </span>
      <span className="mt-3 text-sm text-white/60">Miasto, które słucha</span>
    </div>
  );
}
