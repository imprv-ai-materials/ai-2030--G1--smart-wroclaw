"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CalendarClock, Home, MapPin, Share2 } from "lucide-react";
import { toast } from "sonner";

import { CityMap } from "@/components/city-map";
import { EventStatusBadge, EventTypeBadge } from "@/components/event-badges";
import { EventDetailFacts } from "@/components/event-details-facts";
import { EventProlong } from "@/components/event-prolong";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";
import { eventsApi, SOURCE_LABELS } from "@/lib/events-api";
import { cn, formatDateTime } from "@/lib/utils";

export default function EventDetailPage() {
  const { user } = useAuth();
  const params = useParams<{ id: string }>();
  const id = Number(params.id);

  const event = useQuery({
    queryKey: ["events", id],
    queryFn: () => eventsApi.getEvent(id),
    enabled: Number.isFinite(id),
  });

  function copyLink() {
    navigator.clipboard
      .writeText(window.location.href)
      .then(() => toast.success("Skopiowano link"))
      .catch(() => toast.error("Nie udało się skopiować linku"));
  }

  return (
    <div className="mx-auto w-full max-w-md px-4 py-6 md:max-w-2xl md:py-10">
      <div className="flex items-center justify-between gap-2">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Wróć do strony głównej
        </Link>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={copyLink}
          aria-label="Kopiuj link do zdarzenia"
          title="Kopiuj link"
        >
          <Share2 className="size-4" />
        </Button>
      </div>

      {event.isLoading ? (
        <div className="mt-6 space-y-4">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-40 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
        </div>
      ) : event.isError || !event.data ? (
        <div className="mt-10 rounded-xl border border-dashed p-8 text-center">
          <p className="text-sm text-muted-foreground">
            Nie znaleziono zdarzenia lub wystąpił błąd.
          </p>
          <Link
            href="/"
            className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium hover:underline"
          >
            <Home className="size-4" />
            Strona główna
          </Link>
        </div>
      ) : (
        <article className="mt-6">
          <div className="flex flex-wrap items-center gap-2">
            <EventTypeBadge type={event.data.type} />
            <EventStatusBadge status={event.data.status} />
          </div>

          <h1 className="mt-3 text-2xl font-semibold tracking-tight">
            {event.data.title}
          </h1>

          <p className="mt-3 whitespace-pre-wrap text-muted-foreground">
            {event.data.description}
          </p>

          <EventDetailFacts event={event.data} />

          <EventProlong event={event.data} className="mt-6" />

          {/* Location + map */}
          <Card className="mt-6 gap-4 py-5">
            <CardContent className="space-y-4">
              {event.data.location_text || event.data.address ? (
                <p className="flex items-start gap-2 text-sm">
                  <MapPin className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                  <span>
                    {event.data.location_text}
                    {event.data.location_text && event.data.address ? " · " : ""}
                    {event.data.address}
                  </span>
                </p>
              ) : null}
              <CityMap
                events={[event.data]}
                interactive={false}
                showLegend={false}
                myReporterId={user?.id}
              />
            </CardContent>
          </Card>

          {/* Metadata */}
          <dl className="mt-6 space-y-3 text-sm">
            <MetaRow
              icon={<CalendarClock className="size-4" />}
              label="Początek"
              value={formatDateTime(event.data.starts_at)}
            />
            <MetaRow
              icon={<CalendarClock className="size-4" />}
              label="Koniec"
              value={formatDateTime(event.data.ends_at)}
            />
            <Separator />
            <MetaRow
              label="Źródło"
              value={
                event.data.source
                  ? SOURCE_LABELS[event.data.source] ?? event.data.source
                  : null
              }
            />
            <MetaRow label="Zgłoszono" value={formatDateTime(event.data.created_at)} />
          </dl>
        </article>
      )}
    </div>
  );
}

function MetaRow({
  icon,
  label,
  value,
}: {
  icon?: React.ReactNode;
  label: string;
  value: string | null;
}) {
  if (!value) return null;
  return (
    <div className={cn("flex items-center justify-between gap-4")}>
      <dt className="flex items-center gap-1.5 text-muted-foreground">
        {icon}
        {label}
      </dt>
      <dd className="text-right font-medium">{value}</dd>
    </div>
  );
}
