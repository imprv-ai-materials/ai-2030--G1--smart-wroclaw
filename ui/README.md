# Smart Wrocław — UI

Frontend obywatelskiej aplikacji miasta Wrocławia. Next.js 16 (App Router) +
React 19 + TypeScript, Tailwind CSS v4 i shadcn/ui, TanStack Query v5.

## Funkcje

- **`/` — Strona główna:** hub z trzema modułami.
- **`/assistant` — Zapytaj o miasto:** czat z asystentem AI (utrzymanie miasta).
  Uruchamia asynchroniczny „run", odpytuje aktywny run + jego zdarzenia co ~1,2s
  i po zakończeniu odświeża wątek wiadomości.
- **`/report` — Zgłoś problem:** formularz zgłoszenia (walidacja `zod`) oraz lista
  „Moje zgłoszenia" ze statusami i opublikowaną odpowiedzią miasta.
- **`/specialist` — Panel specjalisty (HITL):** kolejka `PENDING_REVIEW`.
  Specjalista widzi treść od mieszkańca oraz propozycję AI (triage), może
  edytować kategorię/priorytet/wydział/odpowiedź i zatwierdzić lub odrzucić.

## Uruchomienie

```bash
pnpm install
cp .env.example .env.local   # ustaw NEXT_PUBLIC_API_URL jeśli inny niż domyślny
pnpm dev                     # http://localhost:3002
```

## Backend

Bazowy URL API pochodzi z `NEXT_PUBLIC_API_URL`
(domyślnie `http://localhost:8101/api/v1`).

Uwierzytelnianie deweloperskie (patrz `lib/api-client.ts`):

- każde żądanie wysyła nagłówek `X-Citizen-Id: 1`,
- żądania specjalisty (HITL) dodatkowo wysyłają `X-Specialist-Key: dev-specialist`.

Zamień te nagłówki na prawdziwe uwierzytelnianie przed wdrożeniem produkcyjnym.

## Struktura

```
app/                 # App Router: layout + 4 strony
components/ui/        # prymitywy shadcn/ui
components/           # site-header, status-badge, theme-provider
hooks/use-run-poll.ts# polling aktywnego run-a asystenta
lib/                 # api-client + typowane moduły API (assistant, reports)
```
