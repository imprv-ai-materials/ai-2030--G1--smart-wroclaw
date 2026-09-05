"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, MailCheck } from "lucide-react";
import { toast } from "sonner";

import { AuthShell } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { APIError } from "@/lib/api-client";
import { authApi } from "@/lib/auth-api";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submittedEmail, setSubmittedEmail] = useState<string | null>(null);

  const register = useMutation({
    // Phone is intentionally NOT sent — business reporting comes later.
    mutationFn: () => authApi.register({ email: email.trim(), password }),
    onSuccess: () => {
      setSubmittedEmail(email.trim());
    },
    onError: (err) =>
      toast.error(
        err instanceof APIError ? err.message : "Nie udało się zarejestrować.",
      ),
  });

  const resend = useMutation({
    mutationFn: () => authApi.resendConfirmation(submittedEmail ?? email.trim()),
    onSuccess: () => toast.success("Wysłano ponownie wiadomość potwierdzającą."),
    onError: (err) =>
      toast.error(
        err instanceof APIError ? err.message : "Nie udało się wysłać wiadomości.",
      ),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password) {
      toast.error("Podaj e-mail i hasło.");
      return;
    }
    if (password.length < 8) {
      toast.error("Hasło musi mieć co najmniej 8 znaków.");
      return;
    }
    register.mutate();
  }

  if (submittedEmail) {
    return (
      <AuthShell
        title="Sprawdź skrzynkę"
        description="Konto zostało utworzone."
        footer={
          <p>
            <Link href="/auth/login" className="font-medium text-foreground hover:underline">
              Przejdź do logowania
            </Link>
          </p>
        }
      >
        <div className="flex flex-col items-center gap-4 text-center">
          <MailCheck className="size-8" />
          <p className="text-sm text-muted-foreground">
            Wysłaliśmy wiadomość na adres{" "}
            <span className="font-medium text-foreground">{submittedEmail}</span>.
            Kliknij link w wiadomości, aby potwierdzić adres e-mail i móc zgłaszać
            zdarzenia.
          </p>
          <Button
            variant="outline"
            className="w-full"
            onClick={() => resend.mutate()}
            disabled={resend.isPending}
          >
            {resend.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Wysyłanie…
              </>
            ) : (
              "Wyślij ponownie"
            )}
          </Button>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Zarejestruj się"
      description="Załóż konto mieszkańca."
      footer={
        <p>
          Masz już konto?{" "}
          <Link href="/auth/login" className="font-medium text-foreground hover:underline">
            Zaloguj się
          </Link>
        </p>
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
        <div className="space-y-1.5">
          <Label htmlFor="password">Hasło</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Minimum 8 znaków"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="phone">Telefon</Label>
          <Input id="phone" type="tel" disabled placeholder="+48 ___ ___ ___" />
          <p className="text-xs text-muted-foreground">
            jeżeli zgłaszasz jako firma (wkrótce)
          </p>
        </div>
        <Button type="submit" className="w-full" disabled={register.isPending}>
          {register.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Rejestracja…
            </>
          ) : (
            "Utwórz konto"
          )}
        </Button>
      </form>
    </AuthShell>
  );
}
