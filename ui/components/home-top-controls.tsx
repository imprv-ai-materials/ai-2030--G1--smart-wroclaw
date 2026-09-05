"use client";

/**
 * Floating top-left control cluster for the chromeless home map: brand mark +
 * name, then account (Zaloguj / menu) and the light/dark toggle — the pieces the
 * fixed header carries on other pages, reused here as one rounded pill that
 * matches the chat entry and zoom controls.
 */

import Link from "next/link";

import { AuthArea, BrandLogo, ThemeToggle } from "@/components/site-header";

export function HomeTopControls() {
  return (
    <div className="pointer-events-auto flex shrink-0 items-center gap-1 rounded-full border bg-background/85 py-1 pr-1 pl-3 shadow-lg backdrop-blur">
      <Link href="/" className="flex items-center gap-2 pr-1 font-semibold">
        <BrandLogo />
        <span className="hidden text-sm sm:inline">Smart Wrocław</span>
      </Link>
      <span aria-hidden className="mx-0.5 hidden h-5 w-px bg-border sm:block" />
      <AuthArea />
      <ThemeToggle />
    </div>
  );
}
