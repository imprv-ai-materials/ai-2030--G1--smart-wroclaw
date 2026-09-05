"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import { useTheme } from "next-themes";
import {
  KeyRound,
  LogOut,
  MessagesSquare,
  MoonIcon,
  SunIcon,
  UserRound,
} from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

export function SiteHeader() {
  // The home screen is a full-bleed map with its own floating controls, so the
  // fixed header is hidden there; every other (scrollable) page keeps it.
  const pathname = usePathname();
  if (pathname === "/") return null;

  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-md items-center gap-4 px-4 md:max-w-2xl">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <BrandLogo />
          <span>Smart Wrocław</span>
        </Link>

        <div className="ml-auto flex items-center gap-1">
          <AuthArea />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

// Theme-aware brand mark. Swaps the PNG source on the resolved theme; before
// hydration we render the light variant to match the server-rendered markup.
export function BrandLogo() {
  const { resolvedTheme } = useTheme();
  const hydrated = useHydrated();

  const src =
    hydrated && resolvedTheme === "dark"
      ? "/logo__dark_theme.png"
      : "/logo__light_theme.png";

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt="Smart Wrocław"
      width={28}
      height={28}
      className="size-7 select-none"
      draggable={false}
    />
  );
}

export function AuthArea() {
  const { token, user, isLoading } = useAuth();

  if (isLoading) {
    return <div className="size-9 animate-pulse rounded-lg bg-muted" />;
  }

  if (!token) {
    return (
      <Link
        href="/auth/login"
        className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
      >
        Zaloguj
      </Link>
    );
  }

  return <AccountMenu email={user?.email ?? "Konto"} />;
}

function AccountMenu({ email }: { email: string }) {
  const router = useRouter();
  const { logout } = useAuth();
  const [open, setOpen] = useState(false);

  function handleLogout() {
    logout();
    setOpen(false);
    router.push("/");
  }

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="sm"
        className="max-w-[10rem]"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <UserRound className="size-4" />
        <span className="hidden truncate sm:inline">{email}</span>
      </Button>

      {open ? (
        <>
          {/* Click-away backdrop. */}
          <button
            aria-hidden
            tabIndex={-1}
            className="fixed inset-0 z-40 cursor-default"
            onClick={() => setOpen(false)}
          />
          <div
            role="menu"
            className="absolute right-0 z-50 mt-1 w-52 overflow-hidden rounded-lg border bg-popover p-1 text-popover-foreground shadow-sm"
          >
            <p className="truncate px-2 py-1.5 text-xs text-muted-foreground sm:hidden">
              {email}
            </p>
            <Link
              href="/profile"
              role="menuitem"
              className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted"
              onClick={() => setOpen(false)}
            >
              <MessagesSquare className="size-4" />
              Moje rozmowy
            </Link>
            <Link
              href="/auth/change-password"
              role="menuitem"
              className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted"
              onClick={() => setOpen(false)}
            >
              <KeyRound className="size-4" />
              Zmień hasło
            </Link>
            <button
              role="menuitem"
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
              onClick={handleLogout}
            >
              <LogOut className="size-4" />
              Wyloguj
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}

// Hydration-safe "mounted" flag (avoids a setState-in-effect) so the theme icon
// is only resolved on the client, where `resolvedTheme` is known.
const noopSubscribe = () => () => {};
function useHydrated() {
  return useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
}

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const hydrated = useHydrated();

  const isDark = resolvedTheme === "dark";
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label="Przełącz motyw"
      onClick={() => setTheme(isDark ? "light" : "dark")}
    >
      {hydrated && isDark ? (
        <SunIcon className="size-4" />
      ) : (
        <MoonIcon className="size-4" />
      )}
    </Button>
  );
}
