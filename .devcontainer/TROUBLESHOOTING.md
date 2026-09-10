# Dev Container — rozwiązywanie problemów (Windows / WSL2)

Krótkie, konkretne instrukcje dla najczęstszych błędów przy uruchamianiu
projektu w Dev Containers. Pełne wyjaśnienie przyczyn: [README.md](README.md),
sekcja *Windows hosts: „An error occurred setting up the container"*.

## Naprawa: „stat /run/guest-services/distro-services/<dystrybucja>.sock: no such file or directory"

Objaw: obraz buduje się poprawnie, a potem `docker compose … up` natychmiast
przerywa pracę z komunikatem:

```
✘ service "app" Error response from daemon: accessing specified distro mount service:
  stat /run/guest-services/distro-services/ubuntu-24-04-new.sock: no such file or directory
```

Przyczyna: VS Code montuje gniazdo Wayland z WSLg (bo w WSL ustawione jest
`WAYLAND_DISPLAY`), a Docker Desktop nie ma usługi mount service dla tej
dystrybucji — integracja WSL jest dla niej wyłączona albo dystrybucja o tej
nazwie już nie istnieje (została przemianowana / utworzona na nowo).

### 1. Wyłącz montowanie Wayland w VS Code (to jest właściwa naprawa)

1. Otwórz VS Code na Windowsie (z menu Start — **nie** przez `code .` z terminala WSL/Ubuntu).
2. `Ctrl+Shift+P` → wpisz **Preferences: Open User Settings (JSON)** → Enter.
3. Dodaj wewnątrz nawiasów `{ }` linię (pamiętaj o przecinku po poprzedniej linii):

   ```jsonc
   "dev.containers.mountWaylandSocket": false
   ```

4. `Ctrl+S` (zapisz).
5. `Ctrl+Shift+P` → **Developer: Reload Window**.

> Ustawienie ma scope `application`, więc działa **tylko** w User Settings —
> nie da się go zapisać w repo (`.vscode/settings.json` ani `devcontainer.json`).
> Każdy programista na Windowsie dodaje je raz, na swojej maszynie.

### 2. Posprzątaj dystrybucje WSL

6. Otwórz **PowerShell** i sprawdź, jakie dystrybucje masz naprawdę:

   ```powershell
   wsl -l -v
   ```

   Zapamiętaj dokładną nazwę z listy (np. `Ubuntu-24.04`). Jeśli nie ma na niej
   nazwy z komunikatu błędu — to jest „duch" po zmianie nazwy dystrybucji i stąd błąd.

7. **Docker Desktop → Settings (⚙) → Resources → WSL integration**:
   - odznacz wszystko, czego nie ma na liście z punktu 6,
   - zaznacz swoją prawdziwą dystrybucję,
   - kliknij **Apply & restart**.

8. W PowerShell:

   ```powershell
   wsl --shutdown
   ```

9. Zamknij Docker Desktop **przez ikonę w zasobniku (tray) → Quit Docker Desktop**,
   uruchom go ponownie i poczekaj, aż na dole będzie **Engine running** (zielona kropka).

### 3. Uruchom projekt

10. W VS Code otwórz folder projektu.
11. `Ctrl+Shift+P` → **Dev Containers: Rebuild and Reopen in Container**.
12. Czekaj (pierwszy build to kilka minut), aż w terminalu pojawi się **„Devcontainer ready"**.

### Jeśli nadal nie działa

- `Ctrl+Shift+P` → **Dev Containers: Show Container Log** i przeszlij pierwszą
  czerwoną linię **powyżej** `Error: Command failed: docker compose … up -d`.
- Mocniejszy wariant kroku 1 — w tym samym pliku User Settings (JSON) dodaj też:

  ```jsonc
  "dev.containers.forwardWSLServices": false
  ```

  (wyłącza całe przekazywanie usług z WSL: SSH agent, GPG, X, Wayland).
- Jeśli w Docker Desktop nadal widnieje nieistniejąca dystrybucja i nie da się
  jej odznaczyć — usuń jej wpis z listy integracji WSL w
  `%APPDATA%\Docker\settings-store.json` przy **zamkniętym** Docker Desktop.

## Naprawa: kontener startuje, ale `app` od razu się wyłącza (końce linii CRLF)

Objaw: w logu widać `/usr/bin/env: 'bash\r': No such file or directory` albo
`exec /usr/local/bin/devcontainer-entrypoint.sh: no such file or directory`.

Przyczyna: Git for Windows domyślnie ma `core.autocrlf=true` i przy klonowaniu
zamienił końce linii w `entrypoint.sh` na CRLF. Nowe klony są zabezpieczone
przez `.gitattributes`, ale istniejący klon trzeba naprawić ręcznie.

1. Sprawdź w PowerShell, w katalogu repo:

   ```powershell
   if ((Get-Content -Raw .devcontainer\entrypoint.sh) -match "`r`n") { "CRLF - to jest to" } else { "LF - szukaj gdzie indziej" }
   ```

2. **Najpierw zacommituj lub zestashuj swoje zmiany** — `git reset --hard` je usuwa. Potem:

   ```powershell
   git config core.autocrlf false
   git rm --cached -r .
   git reset --hard
   ```

3. `Ctrl+Shift+P` → **Dev Containers: Rebuild and Reopen in Container**
   (koniecznie *Rebuild*, nie tylko *Reopen* — zepsuty entrypoint jest
   zapieczony w cache'owanym obrazie).
