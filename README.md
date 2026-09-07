<!-- Language: **English** · [Polski](#-smart-wrocław--polski) -->

# Smart Wrocław

[![PROGRAM AI 2030 — from hobbyist AI builder to professional](docs/assets/promo1.png)](https://app.imprv.ai/goal_package/5f9e6bc2-7b4b-47a1-90b4-d905796719c0)

> ### Part of **PROGRAM AI 2030**
> This project is part of **[PROGRAM AI 2030](https://app.imprv.ai/goal_package/5f9e6bc2-7b4b-47a1-90b4-d905796719c0)** — a set of hands-on courses in which we build one **fully functional app powered by 28 AI models**, each solving a real business problem. **Smart Wrocław** is one of the applications built along the way.
>
> In particular, this project belongs to the course **_"Od hobbystycznego budowniczego AI do profesjonalisty"_** (*"From hobbyist AI builder to professional"*) — the program's opening course.
>
> 👉 **Explore the program: [app.imprv.ai](https://app.imprv.ai/goal_package/5f9e6bc2-7b4b-47a1-90b4-d905796719c0)**

[![PROGRAM AI 2030 courses — AI that pays for itself](docs/assets/promo2.png)](https://app.imprv.ai/goal_package/5f9e6bc2-7b4b-47a1-90b4-d905796719c0)

A citizen app for the city of **Wrocław**.

## Run it (Dev Container — recommended)

A one-click, reproducible environment. Python 3.12, Poetry, Node 20, pnpm,
Postgres and the Inngest dev server all come up as a Compose stack — identically
on **macOS, Windows (WSL2) and Linux**. All you need is **Docker** and an editor
with Dev Containers support (VS Code + the *Dev Containers* extension, or the
`devcontainer` CLI). No local Python/Node/Postgres install.

### 1. Open in the container

1. Open this folder in VS Code.
2. **Reopen in Container** (Command Palette → *Dev Containers: Reopen in
   Container*). The first build takes a few minutes; `postCreate.sh` then installs
   the backend + frontend deps and applies the DB migrations, and prints
   **"Devcontainer ready"**.

### 2. Start the stack — three terminals

Open three terminals **inside the container** (VS Code → *Terminal*). In each one,
activate the project virtualenv first with **`penv`** (an alias for
`source .venv/bin/activate`), then run the pipeline:

```bash
# Terminal 1 — backend: REST API + Inngest worker (role=all) on :8101
penv
pypyr start_be

# Terminal 2 — load the demo city-events dataset (one-off; see note)
penv
pypyr seed_events

# Terminal 3 — Next.js UI on :3100
penv
pypyr start_ui
```

> `pypyr seed_events` appends the demo events to the database, so run it **once** —
> re-running it duplicates the rows. Skip it if you already have data.

`penv`, `pypyr` and the pipelines come preconfigured in the container — no extra
setup. Inside the container always use **`pypyr start_be`** (not `start_api` /
`start_worker` / `start_tilt`): those target the native host stack and break chat
turns when run in the container.

### 3. Open it

Open the forwarded ports (VS Code → **Ports** panel):

| Service      | URL                        |
|--------------|----------------------------|
| UI           | http://localhost:3100      |
| API + docs   | http://localhost:8101/docs |
| Inngest      | http://localhost:8288      |

Full details, gotchas and the native (non-container) workflow:
[`.devcontainer/README.md`](.devcontainer/README.md).

## Layout

```
smart_wroclaw/            ← project root: Poetry (pyproject.toml, poetry.lock, .venv)
├── api/      FastAPI · pypika · Inngest — backend service (see api/README.md)
│   └── api/ai/<agent>/   each AI agent: versions/ · datasets/ · eval/ (its own scored loop)
├── ui/       Next.js · React · Tailwind v4 · shadcn/ui · TanStack Query (see ui/README.md)
├── dev/      pypyr task pipelines that orchestrate the stack (native workflow)
├── .annotator/  lightweight in-repo dataset annotator (see .annotator/README.md)
├── docs/     architecture notes + diagrams
└── compose.yaml · Tiltfile · Dockerfile   ← infra / runtime
```

The architecture mirrors the sibling `imprv-ai-service` / `imprv-api` services:
bounded contexts, layered repositories/services, a pypika `DBClient`, an API/worker
split, and Inngest for background jobs.

---

<!-- Language: [English](#smart-wrocław) · **Polski** -->

# 🇵🇱 Smart Wrocław — Polski

[![PROGRAM AI 2030 — od hobbystycznego budowniczego AI do profesjonalisty](docs/assets/promo1.png)](https://app.imprv.ai/goal_package/5f9e6bc2-7b4b-47a1-90b4-d905796719c0)

> ### Część **PROGRAMU AI 2030**
> Ten projekt jest częścią **[PROGRAMU AI 2030](https://app.imprv.ai/goal_package/5f9e6bc2-7b4b-47a1-90b4-d905796719c0)** — zestawu praktycznych kursów, w których budujemy jedną **w pełni funkcjonalną aplikację napędzaną 28 modelami AI**, z których każdy rozwiązuje realny problem biznesowy. **Smart Wrocław** to jedna z aplikacji powstających po drodze.
>
> W szczególności ten projekt należy do kursu **_„Od hobbystycznego budowniczego AI do profesjonalisty”_** — otwierającego program.
>
> 👉 **Poznaj program: [app.imprv.ai](https://app.imprv.ai/goal_package/5f9e6bc2-7b4b-47a1-90b4-d905796719c0)**

[![Kursy PROGRAMU AI 2030 — AI, które zarabia na siebie](docs/assets/promo2.png)](https://app.imprv.ai/goal_package/5f9e6bc2-7b4b-47a1-90b4-d905796719c0)

Aplikacja dla mieszkańców miasta **Wrocław**.

## Uruchomienie (Dev Container — zalecane)

Jedno-klikowe, powtarzalne środowisko. Python 3.12, Poetry, Node 20, pnpm,
Postgres oraz serwer deweloperski Inngest wstają jako stack Compose — identycznie
na **macOS, Windows (WSL2) i Linux**. Wystarczy **Docker** oraz edytor
ze wsparciem Dev Containers (VS Code + rozszerzenie *Dev Containers*, lub
narzędzie CLI `devcontainer`). Bez lokalnej instalacji Pythona/Node/Postgres.

### 1. Otwórz w kontenerze

1. Otwórz ten folder w VS Code.
2. **Reopen in Container** (Command Palette → *Dev Containers: Reopen in
   Container*). Pierwsze budowanie trwa kilka minut; następnie `postCreate.sh`
   instaluje zależności backendu + frontendu, wykonuje migracje bazy danych
   i wypisuje **„Devcontainer ready”**.

### 2. Uruchom stack — trzy terminale

Otwórz trzy terminale **wewnątrz kontenera** (VS Code → *Terminal*). W każdym
najpierw aktywuj wirtualne środowisko projektu poleceniem **`penv`** (alias na
`source .venv/bin/activate`), a potem uruchom pipeline:

```bash
# Terminal 1 — backend: REST API + worker Inngest (role=all) na :8101
penv
pypyr start_be

# Terminal 2 — załaduj demonstracyjny zbiór wydarzeń miejskich (jednorazowo; patrz uwaga)
penv
pypyr seed_events

# Terminal 3 — UI Next.js na :3100
penv
pypyr start_ui
```

> `pypyr seed_events` dopisuje demonstracyjne wydarzenia do bazy, więc uruchom je
> **jednokrotnie** — ponowne uruchomienie zduplikuje wiersze. Pomiń, jeśli masz
> już dane.

`penv`, `pypyr` oraz pipeline'y są prekonfigurowane w kontenerze — bez dodatkowej
konfiguracji. Wewnątrz kontenera zawsze używaj **`pypyr start_be`** (nie `start_api` /
`start_worker` / `start_tilt`): tamte celują w natywny stack hosta i psują tury
czatu, gdy uruchomione w kontenerze.

### 3. Otwórz aplikację

Otwórz przekierowane porty (VS Code → panel **Ports**):

| Usługa       | URL                        |
|--------------|----------------------------|
| UI           | http://localhost:3100      |
| API + dokumentacja | http://localhost:8101/docs |
| Inngest      | http://localhost:8288      |

Pełne szczegóły, pułapki oraz natywny (bez kontenera) tryb pracy:
[`.devcontainer/README.md`](.devcontainer/README.md).

## Struktura

```
smart_wroclaw/            ← katalog główny: Poetry (pyproject.toml, poetry.lock, .venv)
├── api/      FastAPI · pypika · Inngest — usługa backendu (patrz api/README.md)
│   └── api/ai/<agent>/   każdy agent AI: versions/ · datasets/ · eval/ (własna, oceniana pętla)
├── ui/       Next.js · React · Tailwind v4 · shadcn/ui · TanStack Query (patrz ui/README.md)
├── dev/      pipeline'y zadań pypyr orkiestrujące stack (tryb natywny)
├── .annotator/  lekki, wbudowany w repo anotator zbiorów danych (patrz .annotator/README.md)
├── docs/     notatki architektoniczne + diagramy
└── compose.yaml · Tiltfile · Dockerfile   ← infrastruktura / runtime
```

Architektura odwzorowuje siostrzane usługi `imprv-ai-service` / `imprv-api`:
konteksty ograniczone (bounded contexts), warstwowe repozytoria/serwisy, `DBClient`
oparty o pypika, rozdział API/worker oraz Inngest do zadań w tle.
