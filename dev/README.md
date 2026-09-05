# dev/ — pypyr task pipelines

These pipelines orchestrate the whole stack (backend `../api`, frontend `../ui`,
and the infra files at the project root — `../compose.yaml`, `../Tiltfile`,
`../Dockerfile`, `../migrations.Dockerfile`), so they live at the repo-module
root rather than inside any one service.

Run them from the project root `smart_wroclaw/` (where `pyproject.toml` and
`.venv` live). The `[tool.pypyr.shortcuts]` table there maps each short name to a
pipeline here (`pipeline_name = "dev/<name>"`).

| command                | what it does |
|------------------------|--------------|
| `pypyr install`        | `poetry install` + pre-commit hooks + `pnpm install` in `ui/` |
| `pypyr migrate`        | `alembic -c api/alembic.ini upgrade head` (needs Postgres up) |
| `pypyr start_tilt`     | `tilt up` — the whole stack in one command |
| `pypyr start_api`      | REST API on `:8101` (role=api) |
| `pypyr start_worker`   | Inngest worker on `:8103` (role=worker) |
| `pypyr start_ui`       | Next.js UI on `:3002` |
| `pypyr format`         | `black` + `isort` (write) |
| `pypyr check_format`   | `black --check` + `isort --check` |
| `pypyr lint`           | `flake8` over `api/api` |
| `pypyr test`           | `pytest` with coverage (`pypyr test tests=./tests/x.py` to scope) |
| `pypyr precommit`      | run all pre-commit hooks |

Shared variables (line length, dirs, the Inngest dev-server URL) live under
`[tool.pypyr.vars]` in `pyproject.toml` and are interpolated as `{name}`.

Typical first run:

```bash
cp api/.env.example api/.env
pypyr install
pypyr start_tilt          # or, in separate shells: start_api / start_worker / start_ui
```
