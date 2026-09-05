"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { AuthShell } from "@/components/auth-shell";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { APIError } from "@/lib/api-client";
import { authApi } from "@/lib/auth-api";
import { cn } from "@/lib/utils";

function ResetInner() {
  const params = useSearchParams();
  const token = params.get("token");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);

  const submit = useMutation({
    mutationFn: () =>
      authApi.resetPassword({ token: token as string, new_password: password }),
    onSuccess: () => setDone(true),
    onError: (err) =>
      toast.error(
        err instanceof APIError ? err.message : "Nie udało się zresetować hasła.",
      ),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) {
      toast.error("Brak tokenu w adresie — użyj linku z wiadomości e-mail.");
      return;
    }
    if (password.length < 8) {
      toast.error("Hasło musi mieć co najmniej 8 znaków.");
      return;
    }
    if (password !== confirm) {
      toast.error("Hasła nie są takie same.");
      return;
    }
    submit.mutate();
  }

  if (done) {
    return (
      <AuthShell title="Hasło zmienione">
        <div className="flex flex-col items-center gap-4 text-center">
          <CheckCircle2 className="size-8" />
          <p className="text-sm text-muted-foreground">
            Twoje hasło zostało zaktualizowane. Możesz się teraz zalogować.
          </p>
          <Link
            href="/auth/login"
            className={cn(buttonVariants({ variant: "default" }), "w-full")}
          >
            Przejdź do logowania
          </Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Ustaw nowe hasło"
      description={
        token ? undefined : "Brak tokenu w adresie — użyj linku z wiadomości e-mail."
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-1.5">
          <Label htmlFor="password">Nowe hasło</Label>
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
          <Label htmlFor="confirm">Powtórz hasło</Label>
          <Input
            id="confirm"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="••••••••"
          />
        </div>
        <Button
          type="submit"
          className="w-full"
          disabled={submit.isPending || !token}
        >
          {submit.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Zapisywanie…
            </>
          ) : (
            "Zmień hasło"
          )}
        </Button>
      </form>
    </AuthShell>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetInner />
    </Suspense>
  );
}
