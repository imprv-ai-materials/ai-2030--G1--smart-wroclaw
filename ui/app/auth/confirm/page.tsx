"use client";

import Link from "next/link";
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { AuthShell } from "@/components/auth-shell";
import { buttonVariants } from "@/components/ui/button";
import { APIError } from "@/lib/api-client";
import { authApi } from "@/lib/auth-api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type State =
  | { kind: "loading" }
  | { kind: "success"; message: string }
  | { kind: "error"; message: string };

function ConfirmInner() {
  const params = useSearchParams();
  const token = params.get("token");
  const { refresh } = useAuth();
  const [state, setState] = useState<State>(() =>
    token
      ? { kind: "loading" }
      : { kind: "error", message: "Brak tokenu potwierdzającego w adresie." },
  );
  const ran = useRef(false);

  useEffect(() => {
    if (!token || ran.current) return;
    ran.current = true;

    authApi
      .confirmEmail(token)
      .then((res) => {
        setState({
          kind: "success",
          message: res.message || "Adres e-mail został potwierdzony.",
        });
        void refresh();
      })
      .catch((err) => {
        setState({
          kind: "error",
          message:
            err instanceof APIError
              ? err.message
              : "Nie udało się potwierdzić adresu e-mail.",
        });
      });
  }, [token, refresh]);

  return (
    <AuthShell title="Potwierdzenie e-mail">
      <div className="flex flex-col items-center gap-4 py-2 text-center">
        {state.kind === "loading" ? (
          <>
            <Loader2 className="size-8 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Potwierdzanie adresu e-mail…
            </p>
          </>
        ) : state.kind === "success" ? (
          <>
            <CheckCircle2 className="size-8" />
            <p className="text-sm">{state.message}</p>
            <Link
              href="/"
              className={cn(buttonVariants({ variant: "default" }), "w-full")}
            >
              Przejdź do aplikacji
            </Link>
          </>
        ) : (
          <>
            <XCircle className="size-8" />
            <p className="text-sm text-muted-foreground">{state.message}</p>
            <Link
              href="/"
              className={cn(buttonVariants({ variant: "outline" }), "w-full")}
            >
              Strona główna
            </Link>
          </>
        )}
      </div>
    </AuthShell>
  );
}

export default function ConfirmPage() {
  return (
    <Suspense fallback={null}>
      <ConfirmInner />
    </Suspense>
  );
}
