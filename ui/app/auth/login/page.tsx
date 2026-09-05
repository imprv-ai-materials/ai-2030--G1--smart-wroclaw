"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { AuthShell } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { APIError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";
import { authApi } from "@/lib/auth-api";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const submit = useMutation({
    mutationFn: () => authApi.login({ email: email.trim(), password }),
    onSuccess: (res) => {
      login(res.access_token);
      toast.success("Zalogowano");
      if (!res.email_confirmed) {
        toast.message("Potwierdź adres e-mail, aby zgłaszać zdarzenia.");
      }
      router.push("/");
    },
    onError: (err) =>
      toast.error(
        err instanceof APIError ? err.message : "Nie udało się zalogować.",
      ),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password) {
      toast.error("Podaj e-mail i hasło.");
      return;
    }
    submit.mutate();
  }

  return (
    <AuthShell
      title="Zaloguj się"
      description="Wpisz swój adres e-mail i hasło."
      footer={
        <>
          <p>
            Nie masz konta?{" "}
            <Link href="/auth/register" className="font-medium text-foreground hover:underline">
              Zarejestruj się
            </Link>
          </p>
          <p className="mt-1">
            <Link
              href="/auth/forgot-password"
              className="text-muted-foreground hover:underline"
            >
              Nie pamiętasz hasła?
            </Link>
          </p>
        </>
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
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
          />
        </div>
        <Button type="submit" className="w-full" disabled={submit.isPending}>
          {submit.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Logowanie…
            </>
          ) : (
            "Zaloguj się"
          )}
        </Button>
      </form>
    </AuthShell>
  );
}
