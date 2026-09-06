"use client";

/**
 * Immersive home screen: the map is the whole canvas. Quick actions float in a
 * pill at the top; active events sit in a scrollable strip along the bottom.
 * Clicking an action opens the right-side panel in CHAT mode; clicking an event
 * card (or a map pin) opens it in DETAILS mode. Strictly black & white.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  CalendarClock,
  ChevronLeft,
  ExternalLink,
  MapPin,
  MessagesSquare,
  Plus,
  Share2,
  X,
} from "lucide-react";

import { AgentChat } from "@/components/agent-chat";
import { CityMap } from "@/components/city-map";
import { EventStatusBadge, EventTypeBadge } from "@/components/event-badges";
import { EventCard } from "@/components/event-card";
import { EventDetailFacts } from "@/components/event-details-facts";
import { EventProlong } from "@/components/event-prolong";
import { HomeTopControls } from "@/components/home-top-controls";
import { Button, buttonVariants } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";
import {
  eventsApi,
  SOURCE_LABELS,
  type CityEvent,
} from "@/lib/events-api";
import { cn, formatDateTime } from "@/lib/utils";

export default function HomePage() {
  const { user } = useAuth();

  // The map always shows the live active feed — a chat search never filters it;
  // search results are shown inside the chat instead.
  const events = useQuery({
    queryKey: ["events", { status: "ACTIVE" }],
    queryFn: () => eventsApi.listEvents({ status: "ACTIVE" }),
  });

  const list = useMemo(() => events.data?.events ?? [], [events.data]);
  const byId = useMemo(() => new Map(list.map((e) => [e.id, e])), [list]);

  // The chat stays mounted while open; an event's details layer on top of it
  // (from a card in the strip OR in the chat), so closing the details returns to
  // the same conversation.
  const [chatOpen, setChatOpen] = useState(false);
  const [detailsEvent, setDetailsEvent] = useState<CityEvent | null>(null);
  // Bumped to remount `AgentChat` with a clean slate when starting anew.
  const [chatKey, setChatKey] = useState(0);

  const openChat = useCallback(() => {
    // Always show the chat: dismiss any open details so the entry button doesn't
    // just re-show the details with a back arrow.
    setDetailsEvent(null);
    setChatOpen(true);
  }, []);

  const startNewConversation = useCallback(() => {
    // Drop the resumed conversation from the URL and remount the chat fresh, so
    // the next turn starts a brand-new conversation server-side.
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.delete("chat");
      window.history.replaceState(null, "", url);
    }
    setDetailsEvent(null);
    setChatOpen(true);
    setChatKey((k) => k + 1);
  }, []);
  const openDetails = useCallback((event: CityEvent) => setDetailsEvent(event), []);
  const openDetailsById = useCallback(
    (id: number) => {
      const event = byId.get(id);
      if (event) setDetailsEvent(event);
    },
    [byId],
  );
  const closeDetails = useCallback(() => setDetailsEvent(null), []);
  const closePanel = useCallback(() => {
    setChatOpen(false);
    setDetailsEvent(null);
  }, []);

  // Arriving with `?chat=<id>` (e.g. from the profile) opens the chat panel.
  useEffect(() => {
    if (
      typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).has("chat")
    ) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot deep-link sync
      setChatOpen(true);
    }
  }, []);

  const panelOpen = chatOpen || detailsEvent != null;
  const selectedId = detailsEvent?.id ?? null;

  // The selected event drives the map's focus (fly-to) when it has coordinates.
  const focus =
    detailsEvent && detailsEvent.lat != null && detailsEvent.lng != null
      ? { id: detailsEvent.id, lng: detailsEvent.lng, lat: detailsEvent.lat }
      : null;

  return (
    <div className="relative h-svh w-full overflow-hidden">
      {/* Map = the whole canvas */}
      <CityMap
        events={list}
        className="absolute inset-0"
        canvasClassName="h-full rounded-none border-0"
        showLegend={false}
        showEmptyHint={false}
        onEventClick={openDetailsById}
        focus={focus}
        myReporterId={user?.id}
      />

      {/* Floating top controls: brand + account fab on the left, the chat entry
          trigger sitting right next to it. */}
      <div className="pointer-events-none absolute inset-x-0 top-4 z-20 flex items-start gap-2 px-4">
        <HomeTopControls />
        <button
          type="button"
          onClick={openChat}
          className="pointer-events-auto flex min-w-0 flex-1 items-center gap-2.5 rounded-full border bg-background/85 px-4 py-2.5 text-left shadow-lg backdrop-blur transition-colors hover:bg-background md:max-w-md"
        >
          <MessagesSquare className="size-4 shrink-0" />
          <span className="flex-1 truncate text-sm text-muted-foreground">
            Zgłoś awarię, zdarzenie lub zapytaj o miasto…
          </span>
          <span className="rounded-full bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground">
            Napisz
          </span>
        </button>
      </div>

      {/* Bottom events strip */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-background/90 via-background/55 to-transparent pt-8 pb-3">
        <div className="pointer-events-auto w-full">
          <div className="mb-0.5 flex items-center gap-2 px-4">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Aktywne zdarzenia
            </h2>
            <span className="rounded-full border bg-background/80 px-1.5 text-[11px] font-medium tabular-nums text-muted-foreground">
              {list.length}
            </span>
          </div>

          <div className="no-scrollbar flex snap-x snap-mandatory gap-2.5 overflow-x-auto scroll-px-4 px-4 pt-1.5 pb-1">
            {events.isLoading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <Skeleton
                  key={i}
                  className="h-[4.5rem] w-72 shrink-0 snap-start rounded-lg"
                />
              ))
            ) : events.isError ? (
              <p className="rounded-lg border border-dashed bg-background/80 px-3 py-2.5 text-sm text-muted-foreground">
                Nie udało się wczytać zdarzeń.
              </p>
            ) : list.length === 0 ? (
              <p className="rounded-lg border border-dashed bg-background/80 px-3 py-2.5 text-sm text-muted-foreground">
                Brak aktywnych zdarzeń.
              </p>
            ) : (
              list.map((event) => (
                <EventCard
                  key={event.id}
                  event={event}
                  selected={event.id === selectedId}
                  onClick={() => openDetails(event)}
                  className="w-72 shrink-0 snap-start"
                />
              ))
            )}
          </div>
        </div>
      </div>

      {/* Right panel: the chat, with an event's details layered on top when one
          is selected — the chat stays mounted underneath so you can go back. */}
      {panelOpen ? (
        <RightPanel
          title={detailsEvent ? "Szczegóły zdarzenia" : "Asystent miasta"}
          onClose={closePanel}
          onBack={detailsEvent && chatOpen ? closeDetails : undefined}
          onNew={chatOpen && !detailsEvent ? startNewConversation : undefined}
        >
          {chatOpen ? (
            <div className={cn("h-full", detailsEvent && "hidden")}>
              <AgentChat key={chatKey} onOpenEvent={openDetails} />
            </div>
          ) : null}
          {detailsEvent ? <EventDetails event={detailsEvent} /> : null}
        </RightPanel>
      ) : null}
    </div>
  );
}

function RightPanel({
  title,
  onClose,
  onBack,
  onNew,
  children,
}: {
  title: string;
  onClose: () => void;
  onBack?: () => void;
  onNew?: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="pointer-events-none absolute inset-0 z-30">
      {/* Dim + click-away (mobile only; on desktop the map/strip stay clickable
          so you can pick another event without closing the panel). */}
      <button
        aria-label="Zamknij panel"
        onClick={onClose}
        className="pointer-events-auto absolute inset-0 cursor-default bg-foreground/10 md:hidden"
      />
      <aside
        className={cn(
          "pointer-events-auto absolute inset-x-0 bottom-0 top-16 flex flex-col overflow-hidden rounded-t-2xl border bg-background shadow-2xl",
          "animate-in fade-in slide-in-from-bottom-6 duration-200",
          "md:inset-y-0 md:right-0 md:left-auto md:top-0 md:w-[420px] md:rounded-none md:border-y-0",
        )}
      >
        <header className="flex items-center gap-2 border-b px-4 py-3">
          {onBack ? (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onBack}
              aria-label="Wróć do czatu"
            >
              <ChevronLeft className="size-4" />
            </Button>
          ) : null}
          <h2 className="min-w-0 flex-1 truncate text-sm font-semibold">
            {title}
          </h2>
          {onNew ? (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onNew}
              aria-label="Nowa rozmowa"
              title="Nowa rozmowa"
            >
              <Plus className="size-4" />
            </Button>
          ) : null}
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            aria-label="Zamknij"
          >
            <X className="size-4" />
          </Button>
        </header>
        <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
      </aside>
    </div>
  );
}

function EventDetails({ event }: { event: CityEvent }) {
  const { user } = useAuth();
  const hasCoords = event.lat != null && event.lng != null;
  return (
    <div className="flex h-full flex-col overflow-y-auto p-4">
      <div className="flex items-center gap-2">
        <EventTypeBadge type={event.type} />
        <EventStatusBadge status={event.status} />
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          className="ml-auto shrink-0"
          aria-label="Kopiuj link do zdarzenia"
          title="Kopiuj link"
          onClick={() => {
            const url = `${window.location.origin}/events/${event.id}`;
            navigator.clipboard
              .writeText(url)
              .then(() => toast.success("Skopiowano link"))
              .catch(() => toast.error("Nie udało się skopiować linku"));
          }}
        >
          <Share2 className="size-4" />
        </Button>
      </div>

      <h3 className="mt-3 text-lg font-semibold tracking-tight">
        {event.title}
      </h3>

      {event.description ? (
        <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">
          {event.description}
        </p>
      ) : null}

      <EventDetailFacts event={event} />

      <EventProlong event={event} className="mt-4" />

      {event.location_text || event.address ? (
        <p className="mt-3 flex items-start gap-2 text-sm">
          <MapPin className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
          <span>
            {event.location_text}
            {event.location_text && event.address ? " · " : ""}
            {event.address}
          </span>
        </p>
      ) : null}

      {hasCoords ? (
        <div className="mt-3">
          <CityMap
            events={[event]}
            interactive={false}
            showLegend={false}
            canvasClassName="h-44"
            myReporterId={user?.id}
          />
        </div>
      ) : null}

      <dl className="mt-4 space-y-2.5 text-sm">
        <MetaRow
          icon={<CalendarClock className="size-4" />}
          label="Początek"
          value={formatDateTime(event.starts_at)}
        />
        <MetaRow
          icon={<CalendarClock className="size-4" />}
          label="Koniec"
          value={formatDateTime(event.ends_at)}
        />
        <Separator />
        <MetaRow
          label="Źródło"
          value={
            event.source
              ? SOURCE_LABELS[event.source] ?? event.source
              : null
          }
        />
        <MetaRow label="Zgłoszono" value={formatDateTime(event.created_at)} />
      </dl>

      <Link
        href={`/events/${event.id}`}
        className={cn(
          buttonVariants({ variant: "outline", size: "sm" }),
          "mt-5 w-full gap-2",
        )}
      >
        <ExternalLink className="size-4" />
        Otwórz pełną stronę
      </Link>
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
    <div className="flex items-center justify-between gap-4">
      <dt className="flex items-center gap-1.5 text-muted-foreground">
        {icon}
        {label}
      </dt>
      <dd className="text-right font-medium">{value}</dd>
    </div>
  );
}
