"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, LogIn, MailWarning } from "lucide-react";
import { toast } from "sonner";
import { z } from "zod";

import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { APIError } from "@/lib/api-client";
import { authApi } from "@/lib/auth-api";
import { useAuth } from "@/lib/auth";
import {
  eventsApi,
  EVENT_TYPE_FORM_LABELS,
  EVENT_TYPE_OPTIONS,
  isEventType,
  type CreateEventInput,
  type EventType,
} from "@/lib/events-api";
import { cn } from "@/lib/utils";

// Wrocław center — prefilled so the user can just tweak the pin.
const DEFAULT_LAT = "51.1079";
const DEFAULT_LNG = "17.0385";

const optionalNumber = z
  .string()
  .trim()
  .transform((v) => (v === "" ? undefined : Number(v)))
  .refine((v) => v === undefined || !Number.isNaN(v), {
    message: "Podaj poprawną liczbę",
  });

const formSchema = z.object({
  title: z.string().trim().min(3, "Tytuł musi mieć co najmniej 3 znaki"),
  description: z.string().trim().min(10, "Opis musi mieć co najmniej 10 znaków"),
  location_text: z.string().trim().optional(),
  lat: optionalNumber,
  lng: optionalNumber,
});

function ReportForm({ defaultType }: { defaultType: EventType }) {
  const router = useRouter();
  const [type, setType] = useState<EventType>(defaultType);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [locationText, setLocationText] = useState("");
  const [lat, setLat] = useState(DEFAULT_LAT);
  const [lng, setLng] = useState(DEFAULT_LNG);

  const submit = useMutation({
    mutationFn: (body: CreateEventInput) => eventsApi.createEvent(body),
    onSuccess: (event) => {
      toast.success("Zdarzenie zgłoszone");
      router.push(`/events/${event.id}`);
    },
    onError: (err) =>
      toast.error(
        err instanceof APIError ? err.message : "Nie udało się wysłać zgłoszenia.",
      ),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const parsed = formSchema.safeParse({ title, description, location_text: locationText, lat, lng });
    if (!parsed.success) {
      toast.error(parsed.error.issues[0]?.message ?? "Sprawdź formularz");
      return;
    }
    submit.mutate({
      type,
      title: parsed.data.title,
      description: parsed.data.description,
      location_text: parsed.data.location_text || undefined,
      lat: parsed.data.lat,
      lng: parsed.data.lng,
    });
  }

  return (
    <Card className="mt-6">
      <CardContent>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-1.5">
            <Label htmlFor="type">Typ zdarzenia</Label>
            <Select
              id="type"
              value={type}
              onChange={(e) => setType(e.target.value as EventType)}
            >
              {EVENT_TYPE_OPTIONS.map((t) => (
                <option key={t} value={t}>
                  {EVENT_TYPE_FORM_LABELS[t]}
                </option>
              ))}
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="title">Tytuł</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="np. Uszkodzona nawierzchnia na ul. Legnickiej"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="description">Opis</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Opisz zdarzenie: co, gdzie i od kiedy występuje."
              className="min-h-28"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="location_text">Lokalizacja (opcjonalnie)</Label>
            <Input
              id="location_text"
              value={locationText}
              onChange={(e) => setLocationText(e.target.value)}
              placeholder="np. ul. Legnicka 45, Wrocław"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="lat">Szerokość (lat)</Label>
              <Input
                id="lat"
                inputMode="decimal"
                value={lat}
                onChange={(e) => setLat(e.target.value)}
                placeholder={DEFAULT_LAT}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="lng">Długość (lng)</Label>
              <Input
                id="lng"
                inputMode="decimal"
                value={lng}
                onChange={(e) => setLng(e.target.value)}
                placeholder={DEFAULT_LNG}
              />
            </div>
          </div>

          <Button type="submit" className="w-full" disabled={submit.isPending}>
            {submit.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Wysyłanie…
              </>
            ) : (
              "Wyślij zgłoszenie"
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function ReportGate() {
  const params = useSearchParams();
  const { token, user, isLoading } = useAuth();

  const defaultType: EventType = useMemo(() => {
    const t = params.get("type");
    return isEventType(t) ? t : "ISSUE";
  }, [params]);

  const resend = useMutation({
    mutationFn: () => authApi.resendConfirmation(user?.email ?? ""),
    onSuccess: () => toast.success("Wysłano ponownie wiadomość potwierdzającą."),
    onError: (err) =>
      toast.error(
        err instanceof APIError ? err.message : "Nie udało się wysłać wiadomości.",
      ),
  });

  if (isLoading) {
    return (
      <div className="mt-6 space-y-3">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-28 w-full" />
      </div>
    );
  }

  // Not logged in.
  if (!token) {
    return (
      <Card className="mt-6">
        <CardContent className="flex flex-col items-center gap-4 py-8 text-center">
          <LogIn className="size-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Aby zgłosić zdarzenie, musisz się zalogować.
          </p>
          <Link
            href="/auth/login"
            className={cn(buttonVariants({ variant: "default" }), "w-full max-w-xs")}
          >
            Zaloguj się
          </Link>
        </CardContent>
      </Card>
    );
  }

  // Logged in but e-mail not confirmed.
  if (user && !user.email_confirmed) {
    return (
      <Card className="mt-6">
        <CardContent className="flex flex-col items-center gap-4 py-8 text-center">
          <MailWarning className="size-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Aby zgłosić zdarzenie, potwierdź swój adres e-mail. Sprawdź skrzynkę i
            kliknij link potwierdzający.
          </p>
          <Button
            variant="outline"
            className="w-full max-w-xs"
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
        </CardContent>
      </Card>
    );
  }

  return <ReportForm defaultType={defaultType} />;
}

export default function ReportPage() {
  return (
    <div className="mx-auto w-full max-w-md px-4 py-6 md:max-w-2xl md:py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Zgłoś zdarzenie</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Opisz zdarzenie w przestrzeni miejskiej. Po wysłaniu pojawi się na liście
        aktywnych zdarzeń.
      </p>

      <Suspense
        fallback={
          <div className="mt-6">
            <Skeleton className="h-64 w-full" />
          </div>
        }
      >
        <ReportGate />
      </Suspense>
    </div>
  );
}
