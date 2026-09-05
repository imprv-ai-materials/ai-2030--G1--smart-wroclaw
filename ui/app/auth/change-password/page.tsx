"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { AuthShell } from "@/components/auth-shell";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { APIError } from "@/lib/api-client";
import { authApi } from "@/lib/auth-api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

export default function ChangePasswordPage() {
  const router = useRouter();
  const { token, isLoading } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");

  const submit = useMutation({
    mutationFn: () =>
      authApi.changePassword({ current_password: current, new_password: next }),
    onSuccess: () => {
      toast.success("Hasło zostało zmienione.");
      router.push("/");
    },
    onError: (err) =>
      toast.error(
        err instanceof APIError ? err.message : "Nie udało się zmienić hasła.",
      ),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!current || !next) {
      toast.error("Wypełnij wszystkie pola.");
      return;
    }
    if (next.length < 8) {
      toast.error("Nowe hasło musi mieć co najmniej 8 znaków.");
      return;
    }
    if (next !== confirm) {
      toast.error("Nowe hasła nie są takie same.");
      return;
    }
    submit.mutate();
  }

  if (isLoading) {
    return (
      <AuthShell title="Zmień hasło">
        <div className="flex justify-center py-4">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      </AuthShell>
    );
  }

  if (!token) {
    return (
      <AuthShell
        title="Zmień hasło"
        description="Aby zmienić hasło, musisz być zalogowany."
      >
        <Link
          href="/auth/login"
          className={cn(buttonVariants({ variant: "default" }), "w-full")}
        >
          Zaloguj się
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Zmień hasło">
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-1.5">
          <Label htmlFor="current">Obecne hasło</Label>
          <Input
            id="current"
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="next">Nowe hasło</Label>
          <Input
            id="next"
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            placeholder="Minimum 8 znaków"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="confirm">Powtórz nowe hasło</Label>
          <Input
            id="confirm"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </div>
        <Button type="submit" className="w-full" disabled={submit.isPending}>
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
