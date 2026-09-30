---
name: scaffolding-project-from-reference
description: Use when the developer wants a new project, project skeleton or project harness created from an existing project or repository they point to, so that it has the same technology stack, architecture, config and local dev setup before other skills implement features in it.
---

# Scaffolding a Project from a Reference

## Overview

The developer points to a reference project. You build a new project with the same stack and the same shape (entrypoints, composition root, config, adapters, bounded contexts, local dev setup) and no business logic. Implementation skills fill that shape later, so it must match the reference.

Read the reference on every run. This skill holds no templates.

## Steps

A step marked **Ask** ends your turn with its question. A step marked **Gate** ends your turn with its proposal: wait for the developer's yes, and write nothing it covers before that.

1. **Name. Ask.** Ask for the new project's name. The project goes next to the reference unless the developer names another place.
2. **Analysis.** Read the reference and report:
   - the stack of each app: language, package manager, framework, main and dev libraries
   - the layers and why they are split: entrypoints, composition root, config, adapters, bounded contexts and their inner layers, shared code, and which of them import which
   - which UI files belong to each API bounded context
   - config and `.env`: the settings class, the env prefix, every file that reads `.env`
   - local dev: compose services, Tiltfile resources, task runner, Dockerfiles, migrations, ports, compose project name
   - the env vars the task runner sets for a process that the Tiltfile's resource for the same process does not set, and the value the code falls back to without each
   - the steps of the install and dev tasks that write outside the app's folder, for example `pre-commit install` in a project inside a parent git repo, which writes that repo's `.git/hooks`
   - each Dockerfile: the files it `COPY`s before it installs the root package, the files `pyproject.toml` names (`readme`, `packages`), whether its build context has a `.dockerignore`, and the host folders `compose.yaml` mounts into any service that sit inside that context (a `volumes:` entry that starts with `./`, such as a database's data folder)
   - the Python env: a real `.venv` folder, or a `.venv` symlink to a pyenv virtualenv, and whether `poetry` resolves on `PATH` without it
   - the display name: the project's name as titles and comment headers write it
   - every file sorted as **generic** (no business logic: adapters, tooling, config, UI kit components) or **domain**
3. **Bounded contexts. Ask.** Ask for the new project's bounded contexts, a name and a one-line purpose each.
4. **API proposal. Gate.** Show:
   - the whole api tree, each file marked `[copy]` (a generic file from the reference), `[new]` (you write it) or `[tool]` (a command makes it)
   - the identifier map, old → new: package name, kebab name, env var prefix, display name. Every `[copy]` file of every app gets the whole map.
   - a `[new]` `.dockerignore` listing those host folders and `.venv`, when a build context contains one of them and has no `.dockerignore`
   - the `pyproject.toml` fields you remove after `poetry init` because the Dockerfiles do not copy their files before installing the root package (Poetry 2's `poetry init` writes `readme = "README.md"`)
   - the commands: env creation, `poetry init`, `poetry add` of the reference's main and dev libraries with the reference's version constraints and extras
   - each bounded context with the reference's inner layers
5. **Scaffold the API.** Run the proposal. Append the reference's `[tool.*]` sections other than `[tool.poetry*]` to the new `pyproject.toml` with a command (`sed -n` or `awk`), remove the fields step 4 listed with `sed`, then run the identifier map on every copied file.
6. **compose.yaml and Tiltfile proposal. Gate.** List the reference's services and let the developer pick. Show both files in full, with each Tilt resource setting the env vars step 2 found missing (see **Run beside the reference**).
7. **UI proposal. Gate.** Show the generator command the reference was built with (for Next.js: `pnpm create next-app@<reference major>` with flags that match the reference's layout), the `pnpm add` commands with the reference's ranges, one `pnpm pkg set` that sets every library of those `pnpm add` commands back to the reference's range (`pnpm add` saves `^<resolved version>` instead; write each as `'dependencies["<name>"]=<range>'` or `devDependencies`), `pnpm install`, and the tree with the same marks, including each bounded context's UI files.
8. **Scaffold the UI.** Run the step 7 commands in order: the generator, `pnpm add`, `pnpm pkg set`, `pnpm install`. Then copy the reference's generic files over the generated ones and run the identifier map on them.
9. **`.env`.** For every app whose reference counterpart reads a `.env`: when the new `.env` is absent, run `[ -e .env ] || cp .env.example .env`. When it exists, leave it as it is and list the keys it lacks compared with `.env.example`.
10. **Start and check.**
    1. Run the reference's install, test, lint and build commands, without the steps step 2 found writing outside the app's folder.
    2. Save `docker ps -a --format '{{.Names}} {{.CreatedAt}}'`.
    3. Start the stack the way the reference does, with the new env on `PATH` (for Tilt: `env VIRTUAL_ENV=<env> PATH=<env>/bin:$PATH tilt up --port <free port>`).
    4. Call every service's health endpoint and load the UI home page.
    5. Run the `docker ps` command again: a container that existed before must show the same creation time, and a new one must carry the new project's name.
    6. Stop the stack: end the `tilt up` process, which runs the local resources, then run `tilt down`.
    7. Run `docker build` on every Dockerfile of every app. After a run, the mounted host folders hold files inside the build context.
    8. Search the copied files for the reference's domain words: its context names and the terms its domain files use.
    9. When a check fails, run the same check on the reference. The same failure there makes it a reference problem, and step 11 still proposes its fix.
11. **Report and fix. Gate.** Show the tree, how to start it (with the env on `PATH`), and every problem: failed checks, skipped steps, domain words left in copied files. Give every problem a proposed minimal fix, a reference problem too. After the yes, apply the approved fixes with commands and rerun the check that found each problem.

## Rules

**Copy means `cp`.** Copy a `[copy]` file with `cp` or `rsync`, then run the identifier map from step 4 on it with `sed`: package name, kebab name, env var prefix, display name. Never retype it. Change it further only through a gate: the `compose.yaml` and `Tiltfile` changes of step 6, and the fixes approved in step 11, applied with a command. Code that a `[new]` file takes verbatim from the reference follows the same rule.

**A bounded context gets the reference's layers, empty, in the API and in the UI.** In the API, create each layer as an empty module. Wire the context the way the reference wires its contexts (router mounted in the entrypoint, worker function list, a section in the composition root), with no routes, tables, models or functions. In the UI, create the files the reference keeps per context (step 2 lists them) as the smallest files that build: an empty module, or a page that renders only the context's name. Link them the way the reference links its contexts, for example as a navigation entry.

**Run beside the reference.** Give the new project its own compose project name in both places that set it: `name:` in `compose.yaml` and `docker_compose("./compose.yaml", project_name="<kebab name>")` in the `Tiltfile`. Tilt ignores `name:` and names the project after the folder, so a new `api/Tiltfile` without `project_name` takes over the reference's `api` containers. Also give it free host ports (check with `ss -ltn`), its own Tilt port and its own Python env. Set in each Tilt resource the env vars step 2 found missing, pointing at the new project's ports: without them the code falls back to a default, and a default port can belong to another project.

**Change nothing outside the new project.** Run no command that writes files outside the new project's folders and its Python env. When a reference task does, skip that step, run the rest, and list the skipped step in the report.

**Python commands run in the new project's env.** Make the env the way the reference's is made. Install into it the Poetry version that the reference's copied files pin (`POETRY_VERSION` in its Dockerfiles), not the version its env happens to have, so the copied images can read the new lock. Then run `env VIRTUAL_ENV=<env> PATH=<env>/bin:$PATH poetry ...`.

## Common Mistakes

| Mistake | Fix |
|---|---|
| One proposal for the whole project | Three gates: api, compose and Tilt, ui |
| Copying `pyproject.toml`, `poetry.lock`, `package.json` or `pnpm-lock.yaml` | `poetry init` and `poetry add`, the generator and `pnpm add` |
| Rewriting a generic file to drop the reference's domain words | `cp`, `sed` on identifiers, then propose the rest at step 11 |
| An empty `contexts_boundaries/` | Ask for contexts in step 3 and create their layers |
| Contexts only in the API | Create the reference's per-context UI files too |
| `name:` in `compose.yaml` but no `project_name` in the `Tiltfile` | Set both |
| A Tilt resource without an env var the task runner sets | Set it in the `Tiltfile` in step 6 |
| Running the reference's install task whole | Skip its steps that write outside the new project, report them |
| Lock written by a newer Poetry than the copied Dockerfiles pin (image build fails) | Install the pinned Poetry in the env before `poetry init` |
| Building only the images Tilt builds | `docker build` every Dockerfile after the stack ran |
| Keeping the ranges `pnpm add` saved | Restore the reference's ranges with `pnpm pkg set` |
| `tilt down` while `tilt up` still runs | End `tilt up` first |
| Leaving a failed check as it is, or fixing it unasked | Propose its fix at the step 11 gate |
