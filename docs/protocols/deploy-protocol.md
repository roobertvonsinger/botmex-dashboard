# Protocolo de Deploy

> **Stack actual (2026-09-08):** KVM4-Karen — `2.25.98.162` (pública) / `100.95.147.72` (Tailscale).
> Hostname real `karen`. KVM4-old (`100.77.154.31`) fue **retirado** — no usar.
> **SSH:** `ssh -i "C:/Users/rober/Dropbox/TESTING DEV/SSH KEYS/kvm4_hostinger" root@2.25.98.162`
> (alias `karen` / `kvm4` en `~/.ssh/config`). Usar `ssh`/`scp` **nativos** — NO `pscp`/`plink` (se cuelgan sin TTY).
> **Checkout de prod:** `/opt/kvm4/apps/betmexico/code` → bind-mount a `/app` de los 4 contenedores.
> **compose working_dir:** `/opt/kvm4/apps/betmexico` (`docker-compose.yml` ahí).
> **Contenedores:** `betmexico-web` (FastAPI, puerto interno 8080), `betmexico-bot` (bot legacy `@betmexbot`,
> corre `python betmexico_bot.py`), `betmexico-mock-bot` (bot mock del dashboard), `betmexico-balance-poller`.
> **Dominio público:** `https://botmexico.net` (`.com.mx` apunta a placeholder — ver memoria del proyecto).

---

## 🛑 Regla de oro: KVM4 se despliega SOLO vía git

**Prohibido** editar archivos en prod, hacer `rsync`/`scp`/`cp` de copias de trabajo sobre el checkout,
o desplegar sin `commit` + `push` previo a `origin/main`. Un deploy manual sin git deja el checkout
"frankenstein" (ver `docs/ERRORS.md`, entrada 2026-09-08) y el siguiente `git pull` explota.

Flujo canónico, sin excepciones:

```
1. Local:  cambio → tests verdes → commit → push origin main
2. Prod:   git fetch origin && git reset --hard origin/main   (o pull si es fast-forward limpio)
3. Prod:   docker restart <contenedor(es) afectados>
4. Verif:  health 200 + docker logs limpio + smoke funcional
```

### Comandos

```bash
KEY="C:/Users/rober/Dropbox/TESTING DEV/SSH KEYS/kvm4_hostinger"
HOST="root@2.25.98.162"
CODE="/opt/kvm4/apps/betmexico/code"

# 1. Local (desde repos/botmex-dashboard)
python tools/verify_bet_suite.py           # si el cambio toca auto-depósito/matchmaking → 13/13 obligatorio
git add <archivos> && git commit -m "..." && git push origin main

# 2. Traer el cambio a prod (git-only)
ssh -i "$KEY" "$HOST" "cd $CODE && git fetch origin -q && git log --oneline -1 origin/main && git reset --hard origin/main"

# 3. Restart del/los contenedor(es) afectados
#    - cambio en app.py/deposits.py/prewarm.py/static/* → betmexico-web
#    - cambio en betmexico_*.py (bot legacy)            → betmexico-bot   (dueño: monorepo, ver §C)
#    - cambio en telegram_bot_mock/*                    → betmexico-mock-bot
ssh -i "$KEY" "$HOST" "docker restart betmexico-web"

# 4. Verificación (ver deploy-checklist.md para el smoke completo)
ssh -i "$KEY" "$HOST" "docker exec betmexico-web curl -s -m 5 http://localhost:8080/api/health"   # → {"ok":true,...}
ssh -i "$KEY" "$HOST" "docker logs --tail 30 betmexico-web"                                        # sin Traceback/ImportError
```

Frontend (`static/*.html/.css/.js`) usa el mismo bind-mount → tras `git reset` basta refresh del
navegador (Ctrl+F5); el auto-reload por versión (`FRONTEND_ASSETS` en `app.py`) avisa a los operadores
ya conectados. No requiere restart, pero conviene igual para invalidar cachés de Python si tocaste `.py`.

---

## Tipos de cambio

### A) Frontend (`.html`, `.css`, `.js`)
`git reset --hard origin/main` en prod + refresh navegador. Sin restart.
Si agregaste un asset `.css`/`.js` NUEVO a `index.html` → sumarlo a `FRONTEND_ASSETS` en `app.py` o
queda ciego al auto-reload (ver `docs/ERRORS.md` 2026-07-06).

### B) Backend Python (`app.py`, `deposits.py`, `prewarm.py`, `auto_deposit.py`, etc.)
`git reset --hard origin/main` + `docker restart betmexico-web`.
Si el cambio toca **auto-depósito / matchmaking** → `python tools/verify_bet_suite.py` (13/13) ANTES del push.

### C) Módulos del bot legacy (`betmexico_bot.py`, `betmexico_check/amazon/notes/search/reports.py`)
**Dueño canónico:** monorepo `C:\Users\rober\Dropbox\TESTING DEV\Proyectos\BetMexico\Telegram\`.
Estos archivos están **gitignoreados** en este repo (co-ubicados en el checkout por el bind-mount
compartido, pero no son código del dashboard). El deploy del bot legacy se hace desde su propia
sesión/repo. Si un cambio del monorepo afecta módulos core que SÍ están tracked aquí
(`betmexico_db.py`, `betmexico_deposit.py`, `betmexico_login_service.py`, `betmexico_payment_analyzer.py`),
ese cambio debe entrar por este repo (commit + push + `git reset` en prod) — no por copia suelta.

### D) Migración de BD (nueva columna/tabla)
1. Migración aditiva en `_migrate()` (`app.py`) — `("col", "ALTER TABLE ... ADD COLUMN col TEXT")`.
2. Push + `git reset` + `docker restart betmexico-web`.
3. Verificar arranque sin error: `docker logs --tail 30 betmexico-web | grep -iE 'migrate|alter|error'`.
4. Confirmar columna:
   `ssh -i "$KEY" "$HOST" 'docker exec betmexico-web python -c "import sqlite3; c=sqlite3.connect(\"/data/betmexico_accounts.db\"); print([r[1] for r in c.execute(\"PRAGMA table_info(deposit_attempts)\")])"'`

### E) Dockerfile / requirements (rebuild)
```bash
ssh -i "$KEY" "$HOST" "cd /opt/kvm4/apps/betmexico && git -C code reset --hard origin/main && docker compose build betmexico-web && docker compose up -d --force-recreate betmexico-web"
```
Si el build se cuelga en "Configuring tzdata" → falta `ENV DEBIAN_FRONTEND=noninteractive` antes del `apt-get`.

### F) `.env` (keys, paths) — NO commitear
```bash
ssh -i "$KEY" "$HOST" "nano /opt/kvm4/apps/betmexico/.env"   # editar en prod directamente
ssh -i "$KEY" "$HOST" "docker restart betmexico-web"
```

### G) Traefik / dominio
Traefik corre aparte. Labels en `infra/docker-compose.yml` de betmexico → editar, push, `git reset`,
`docker compose up -d betmexico-web`. Verificar cert:
`echo | openssl s_client -servername <dominio> -connect <dominio>:443 2>/dev/null | openssl x509 -noout -subject -dates`

---

## Restore point antes de una operación de riesgo

Antes de un `git reset --hard` sobre un checkout divergido, o cualquier operación destructiva en prod:

```bash
TS=$(date +%Y%m%d_%H%M%S)
ssh -i "$KEY" "$HOST" "mkdir -p /root/restore-points && cd /opt/kvm4/apps/betmexico && \
  tar czf /root/restore-points/betmexico-code-PREOP-$TS.tar.gz --exclude=__pycache__ --exclude='*.pyc' code && \
  sha256sum /root/restore-points/betmexico-code-PREOP-$TS.tar.gz > /root/restore-points/betmexico-code-PREOP-$TS.tar.gz.sha256"
scp -i "$KEY" "$HOST:/root/restore-points/betmexico-code-PREOP-$TS.*" \
  "C:/Users/rober/Dropbox/TESTING DEV/repos/Boveda/BetMexico/restore-points/"
```

Restaurar = `tar xzf <tarball> -C /opt/kvm4/apps/betmexico` + `docker restart betmexico-web betmexico-bot`.

---

## Estándar de commit + push

```bash
cd "C:/Users/rober/Dropbox/TESTING DEV/repos/botmex-dashboard"
git add <archivos>
git commit -m "<tipo>(<scope>): <mensaje corto>

<detalle>

Smoke test:
- /api/health → 200
- <endpoint específico> → <código esperado>"
git push origin main
```

**Tipos:** `feat`, `fix`, `chore`, `docs`, `refactor`, `perf`, `test`.
**Scopes:** `backend`, `frontend`, `infra`, `deps`, `bitacora`, `bet`, etc.

---

## Después de cualquier deploy

Ver `deploy-checklist.md` para el smoke test funcional obligatorio (NO solo `/health`).
