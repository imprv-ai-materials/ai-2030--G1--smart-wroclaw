# Dev Container — run Smart Wrocław on any OS

A one-click, reproducible dev environment. Everything the stack needs — Python
3.12, Poetry, Node 20, pnpm, Postgres and the Inngest dev server — is provisioned
in containers, so it behaves the same on **macOS, Windows (WSL2) and Linux**. No
local Python/Node/Postgres install required; only Docker + an
editor with Dev Containers support (VS Code + the *Dev Containers* extension, or
the `devcontainer` CLI).

## Start it

1. Open the `smart_wroclaw/` folder in VS Code.
2. **Reopen in Container** (Command Palette → *Dev Containers: Reopen in
   Container*). First build takes a few minutes.
3. `postCreate.sh` runs automatically: it installs backend + frontend deps and
   applies the DB migrations. When it prints **"Devcontainer ready"**, start the
   app from two terminals:

   ```bash
   poetry run uvicorn api.main:app --app-dir api --host 0.0.0.0 --reload --port 8101   # REST + worker
   pnpm --dir ui dev                                                     # UI
   ```

Open the forwarded ports (VS Code → **Ports** panel):

| Service         | URL                          | Notes                                   |
|-----------------|------------------------------|-----------------------------------------|
| UI (Next.js)    | http://localhost:3100        |                                         |
| API + docs      | http://localhost:8101/docs   | REST + Inngest function host (role=all) |
| Inngest         | http://localhost:8288        | dev dashboard                           |
| Postgres        | localhost:5432 (forwarded)   | `smart_wroclaw` / `smart_wroclaw`       |

## "Can we fire up the compose from the devcontainer?" — yes, it *is* the compose

The devcontainer is defined **as a Compose stack** (`.devcontainer/compose.yaml`).
When you Reopen in Container, VS Code runs `docker compose up` on it for you, so
bringing the stack up is not a separate step — opening the container fires up the
compose. The services:

```
┌─ app ──────────────┐   the devcontainer you work in (source bind-mounted).
│  uvicorn :8101      │   run uvicorn (role=all → REST + worker) and pnpm here.
│  next  :3100        │
└─────────┬───────────┘
          │  db:5432          inngest:8288
   ┌──────▼─────┐      ┌──────────▼───────┐
   │ postgres:18│      │ inngest dev srv  │
   └────────────┘      │ -u app:8101/...  │
                       └──────────────────┘
```

Everything talks over the Compose network by **service name** (`db`, `inngest`),
so there's no `host.docker.internal` and no host-port juggling — that's what
makes it portable. Host access is via `forwardPorts`, so it never clashes with a
native `docker compose` / Tilt run.

### How this differs from the native (non-container) workflow

| | Native host (`compose.yaml` + Tilt) | Devcontainer (`.devcontainer/compose.yaml`) |
|---|---|---|
| Postgres / Inngest | containers, **published on localhost** | containers, **network-internal** |
| api / worker / ui | run **on your machine** (Poetry/pnpm) | run **inside the `app` container** |
| Orchestrator | **Tilt** (`pypyr start_tilt`) | Compose (auto, via the devcontainer) |
| DB address | `localhost:5439` (from `api/.env`) | `db:5432` (compose env override) |

> **Inside the container use `pypyr start_be` + `pypyr start_ui` (or the plain
> `uvicorn` / `pnpm` commands above) — not `start_tilt` / `start_api` /
> `start_worker`.** Those three hardcode host-oriented URLs (`127.0.0.1:8488`,
> Docker socket for Tilt) for the native workflow. `start_be` / `start_ui`
> inherit the container env vars (DB host, Inngest URL, role), so they work in
> both setups.

## Annotating eval datasets

Dataset labelling uses the lightweight in-repo annotator at
[`/.annotator`](../.annotator/README.md) — no extra service. Point it at an
agent's dataset + template, e.g.:

```bash
python .annotator/annotate.py \
  api/api/ai/main_agent/datasets/annotate.template.js \
  api/api/ai/main_agent/datasets/queries.jsonl
# → http://127.0.0.1:7900
```

## Notes & gotchas

- **`.venv` and `ui/node_modules` are named volumes**, not the bind-mounted host
  folders — a macOS/Windows virtualenv or native module won't run under Linux, so
  the container keeps its own. If you ever change dependencies, re-run
  `poetry install` / `pnpm --dir ui install` (or rebuild the container).
- **`ui/.next` is a named volume too**, so it is a *mount point* inside the
  container: `rm -rf ui/.next` empties it but then fails with `Device or resource
  busy`. Clear the cache with `find ui/.next -mindepth 1 -delete` instead (this is
  what `pypyr start_ui` does).
- **git:** this container mounts only `smart_wroclaw/`, but the repo's `.git`
  lives at the monorepo root above it, so run `git` from the host (or open the
  monorepo root as the workspace if you prefer git inside the container).
- **OpenAI key:** left blank in the generated `api/.env`, so the assistant and
  triage agents use their offline fallbacks and the whole stack is exercisable
  with no key and no cost. Add `CONFIG__OPENAI__API_KEY=…` to `api/.env` to use a
  real model.
- **Linux hosts with uid ≠ 1000:** VS Code's automatic uid remap
  (`updateRemoteUserUID`) does not apply to compose-based devcontainers, so
  `entrypoint.sh` does it instead: on start it remaps the `vscode` user to the
  owner of the bind-mounted workspace when that user can't write to it. Without
  this, `postCreate.sh` dies with `[Errno 13] Permission denied: PosixPath('…/.venv')`
  (poetry can't recreate the venv mount point) and file saves fail with EACCES.
  On macOS / Windows the mount is writable by any uid, so it's a no-op.
- **Rootless Docker / Podman:** the host user appears as root inside the
  container and `vscode` can't be remapped onto it. Set `"remoteUser": "root"`
  in `devcontainer.json`, or run podman with `--userns=keep-id`.
- **Rebuild** after changing anything under `.devcontainer/`: *Dev Containers:
  Rebuild Container*.

## Windows hosts: "An error occurred setting up the container"

VS Code shows that one-line dialog for *any* failure. The real error is in
**Terminal → Dev Containers**, on the first red line *above*
`Error: Command failed: docker compose … up -d app db inngest` — or, in full, in
the log that *Dev Containers: Show Container Log* opens
(`%APPDATA%\Code\logs\<timestamp>\window1\exthost\ms-vscode-remote.remote-containers\`).

Two distinct things cause it. They fail at different stages, so the log tells
you which one you have.

### 1. WSLg Wayland socket + Docker Desktop WSL integration (confirmed in the wild)

**Symptom** — the image *builds fine*, then `compose up` dies instantly while
creating the containers:

```
[+] up 1/3
 ✘ service "app" Error response from daemon: accessing specified distro mount service:
   stat /run/guest-services/distro-services/<distro>.sock: no such file or directory
```

**Cause** — when `WAYLAND_DISPLAY` is set in WSL, the Dev Containers extension
mounts WSLg's Wayland socket into the container so Linux GUI apps can draw on the
Windows desktop. It does that through a UNC path, which you can see in the
compose override it generates:

```yaml
volumes:
  - vscode:/vscode
  - \\wsl.localhost\Ubuntu-24.04\mnt\wslg\runtime-dir\wayland-0:/tmp/vscode-wayland-<uuid>.sock
```

Only the Docker Desktop daemon can resolve `\\wsl.localhost\<distro>\…`, and only
for distros where **WSL integration is turned on**. If that distro is off in
Docker Desktop's list (a freshly created or renamed distro defaults to off), the
daemon can't reach its mount service and refuses to create the container. Note
this bites even when the clone lives on `C:\` and you never open a WSL shell —
the extension probes the default distro regardless.
See [vscode-remote-release#11402](https://github.com/microsoft/vscode-remote-release/issues/11402),
[#9293](https://github.com/microsoft/vscode-remote-release/issues/9293),
[#8172](https://github.com/microsoft/vscode-remote-release/issues/8172).

**Fix A — enable the integration** (do this if you use WSL at all):
*Docker Desktop → Settings → Resources → WSL integration* → enable the distro
named in the error, **Apply & restart**, then *Dev Containers: Reopen in
Container*.

**Fix B — stop the mount being generated** (do this if you don't need Linux GUI
apps in the container; it is the more reliable of the two). In **host** VS Code,
*Preferences: Open User Settings (JSON)*, add:

```jsonc
"dev.containers.mountWaylandSocket": false
```

then reload the window and reopen in the container. Nothing here needs WSLg, so
Fix B costs you nothing. Verified against extension `ms-vscode-remote.remote-
containers` 0.469.0: *"Controls whether a Wayland socket, if one exists, should
be mounted into the Dev Container"*, default `true`, **scope `application`**.
`dev.containers.forwardWSLServices: false` is the bigger hammer — it turns off
SSH agent / GPG agent / X / Wayland forwarding from WSL all at once.

That `application` scope is why this fix cannot be committed to the repo: an
application-scoped setting is only honoured in *user* settings, so neither
`.vscode/settings.json` nor `customizations.vscode.settings` in
`devcontainer.json` can set it (and the latter applies inside the container
anyway — far too late to change the compose command). Each Windows developer has
to add it once, per machine.

### 2. CRLF line endings

**Symptom** — the stack comes up, then the `app` container exits immediately, or
`postCreateCommand` fails:

```
/usr/bin/env: 'bash\r': No such file or directory
exec /usr/local/bin/devcontainer-entrypoint.sh: no such file or directory
```

**Cause** — Git for Windows checks out with `core.autocrlf=true` by default,
rewriting `entrypoint.sh` to CRLF. That file is the `app` service's ENTRYPOINT,
so Linux looks for an interpreter literally named `bash\r`.

The repo now pins LF via `.gitattributes`, and the image + `postCreateCommand`
strip CR defensively — but an *existing* Windows clone still has CRLF on disk.
Check before touching anything:

```powershell
if ((Get-Content -Raw .devcontainer\entrypoint.sh) -match "`r`n") { "CRLF - this is it" } else { "LF - look elsewhere" }
```

Fix it once, on the host — **commit or stash first, `reset --hard` discards
uncommitted work**:

```powershell
git config core.autocrlf false
git rm --cached -r .
git reset --hard
```

then *Dev Containers: **Rebuild** Container* — not just "Reopen", since a broken
entrypoint is baked into the cached image.

### Unrelated but worth knowing

The bind mount is much faster if the clone lives inside the WSL filesystem
(`\\wsl.localhost\Ubuntu\home\<you>\…`) and you open it with the WSL extension
before reopening in the container. If you go that route you need Fix A above
anyway, since Docker Desktop must have integration enabled for that distro.
