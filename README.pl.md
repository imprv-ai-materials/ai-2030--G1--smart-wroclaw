<div align="center">

### 🌐 Język / Language

<kbd>🇬🇧 &nbsp;<a href="README.md"><b>English</b></a>&nbsp;</kbd> &nbsp;&nbsp; <kbd>🇵🇱 &nbsp;<b>Polski</b> ✓&nbsp;</kbd>

_Wersją źródłową jest [angielski README](README.md) — tłumaczenie może być nieco opóźnione._

</div>

---

# Smart Wrocław

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
