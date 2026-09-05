"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ComponentProps } from "react";

/**
 * Thin wrapper around `next-themes`' provider so the root layout can host it
 * directly in the server-rendered tree — this keeps the inline theme-detection
 * `<script>` in the SSR HTML where React 19 expects it.
 */
export function ThemeProvider(props: ComponentProps<typeof NextThemesProvider>) {
  return <NextThemesProvider {...props} />;
}
