"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, MailCheck } from "lucide-react";

import { AuthShell } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authApi } from "@/lib/auth-api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);

  const submit = useMutation({
    mutationFn: () => authApi.requestPasswordReset(email.trim()),
    // Always show the same neutral message — regardless of success/failure —
    // so we don't reveal whether an account exists.
    onSettled: () => setDone(true),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    submit.mutate();
  }

  if (done) {
    return (
      <AuthShell
        title="Sprawdź skrzynkę"
        footer={
          <Link href="/auth/login" className="font-medium text-foreground hover:underline">
            Wróć do logowania
          </Link>
        }
      >
        <div className="flex flex-col items-center gap-4 text-center">
          <MailCheck className="size-8" />
          <p className="text-sm text-muted-foreground">
            Jeśli konto istnieje, wysłaliśmy link do zresetowania hasła.
          </p>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Nie pamiętasz hasła?"
      description="Podaj adres e-mail, a wyślemy link do zresetowania hasła."
      footer={
        <Link href="/auth/login" className="text-muted-foreground hover:underline">
          Wróć do logowania
        </Link>
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-1.5">
          <Label htmlFor="email">E-mail</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="jan.kowalski@example.com"
          />
        </div>
        <Button type="submit" className="w-full" disabled={submit.isPending}>
          {submit.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Wysyłanie…
            </>
          ) : (
            "Wyślij link"
          )}
        </Button>
      </form>
    </AuthShell>
  );
}
