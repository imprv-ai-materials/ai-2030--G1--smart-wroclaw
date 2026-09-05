
# compose.yaml lives beside this Tiltfile (the project root); the API config/.env
# lives in api/, so hand compose that env file for ${CONFIG__POSTGRES__*} interpolation.
docker_compose("./compose.yaml", env_file="api/.env")

docker_build(
    "smart-wroclaw-migrations",
    # Build context = the repo-module root (the project root, beside this
    # Tiltfile) so the api/ package is inside the context. `only` paths are
    # relative to it.
    context=".",
    dockerfile="migrations.Dockerfile",
    only=[
        "./api/api",
        "./pyproject.toml",
        "./poetry.lock",
        "./api/alembic.ini",
    ],
)
