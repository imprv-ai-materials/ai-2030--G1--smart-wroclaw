#!/usr/bin/env bash
# Entrypoint of the `app` service. Runs as root BEFORE VS Code attaches as the
# `vscode` user, then execs the compose command (`sleep infinity`).
#
# Job: make the container's `vscode` user match the OWNER of the bind-mounted
# workspace. VS Code does this automatically (`updateRemoteUserUID`) for image /
# Dockerfile devcontainers, but NOT for docker-compose ones like this — so on a
# Linux host whose uid isn't 1000 the workspace is read-only for `vscode`:
# postCreate dies with "[Errno 13] Permission denied: PosixPath('…/.venv')"
# (poetry can't rmdir the .venv mount point without write access to its parent)
# and every file save in the editor fails with EACCES.
#
# No-op on macOS / Windows: Docker Desktop reports the mount as root-owned but
# lets any uid write to it, so the writability probe below passes.
set -euo pipefail

WORKSPACE="${WORKSPACE:-/workspaces/smart_wroclaw}"
DEV_USER="${DEV_USER:-vscode}"

log() { echo "[entrypoint] $*" >&2; }

align_uid() {
  [ -d "$WORKSPACE" ] || { log "no workspace at $WORKSPACE, skipping uid alignment"; return; }

  local host_uid host_gid cur_uid cur_gid
  host_uid="$(stat -c %u "$WORKSPACE")"
  host_gid="$(stat -c %g "$WORKSPACE")"
  cur_uid="$(id -u "$DEV_USER")"
  cur_gid="$(id -g "$DEV_USER")"

  # Already writable as the dev user (same uid, or Docker Desktop's relaxed mount)?
  if su -s /bin/sh "$DEV_USER" -c "test -w '$WORKSPACE'"; then
    return
  fi

  if [ "$host_uid" = "0" ]; then
    # Rootless Docker / Podman without --userns=keep-id: the host user shows up as
    # root in here, and we can't turn `vscode` into root. Flag it and carry on.
    log "WARNING: $WORKSPACE is root-owned and not writable by $DEV_USER."
    log "         Rootless Docker/Podman? Set \"remoteUser\": \"root\" in devcontainer.json,"
    log "         or run podman with --userns=keep-id."
    return
  fi

  log "workspace owned by $host_uid:$host_gid, $DEV_USER is $cur_uid:$cur_gid — remapping $DEV_USER"

  # Check for a uid clash BEFORE changing anything, so a refusal leaves the user intact.
  if [ "$host_uid" != "$cur_uid" ] && getent passwd "$host_uid" >/dev/null; then
    log "ERROR: uid $host_uid already taken by $(getent passwd "$host_uid" | cut -d: -f1); cannot remap"
    return
  fi
  if [ "$host_gid" != "$cur_gid" ]; then
    if getent group "$host_gid" >/dev/null; then
      usermod -g "$host_gid" "$DEV_USER"           # gid already exists → make it primary
    else
      groupmod -g "$host_gid" "$(id -gn "$DEV_USER")"
    fi
  fi
  if [ "$host_uid" != "$cur_uid" ]; then
    usermod -u "$host_uid" "$DEV_USER"
  fi
  # Files created at image-build time under the home dir still carry the old ids.
  chown -R "$host_uid:$host_gid" "/home/$DEV_USER"
  log "done: $DEV_USER is now $(id -u "$DEV_USER"):$(id -g "$DEV_USER")"
}

if [ "$(id -u)" = "0" ]; then
  align_uid
else
  log "not running as root, skipping uid alignment"
fi

exec "$@"
