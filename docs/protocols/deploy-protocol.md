# Protocolo de Deploy

> Stack actual: KVM4 (`100.77.154.31`) / `2.24.211.109`. SSH password: `Kashau2022##`.
> Carpeta: `/docker/betmexico/`. Servicios: `betmexico-bot` + `betmexico-web` (puerto 8080).
> Dominio público: `https://botmexico.com.mx`.

## Tipos de cambio + flujo

### A) Cambio frontend (`.html`, `.css`, `.js`)

Hot-mount via volumen `./code:/app`. NO requiere restart.

```bash
# Local: editar archivos en static/
pscp -batch -pw "Kashau2022##" static/app.js static/index.html static/style.css \
  root@100.77.154.31:/docker/betmexico/code/web/static/

# Refresh duro del navegador (Ctrl+F5). Si index.html usa cache-bust automático,
# refresh normal basta.
```

### B) Cambio backend Python (`app.py`, `deposits.py`, `prewarm.py`, etc.)

Hot-mount + restart del container web.

```bash
# Local
pscp -batch -pw "Kashau2022##" app.py deposits.py prewarm.py \
  root@100.77.154.31:/docker/betmexico/code/web/

# Restart
plink -batch -pw "Kashau2022##" root@100.77.154.31 \
  "cd /docker/betmexico && docker compose restart web"

# Verificar
plink -batch -pw "Kashau2022##" root@100.77.154.31 \
  "docker logs --tail 30 betmexico-web"
```

### C) Cambio en módulos del bot (`betmexico_*.py`)

Esos archivos viven en `/docker/betmexico/code/` (compartidos con bot Telegram).
**Origen canónico actual**: `Proyectos/BetMexico/Telegram/` en monorepo.
(Cuando se migre a su propio repo, ajustar.)

```bash
pscp -batch -pw "Kashau2022##" "C:\Users\rober\Dropbox\TESTING DEV\Proyectos\BetMexico\Telegram\betmexico_db.py" \
  root@100.77.154.31:/docker/betmexico/code/

# Si cambio afecta a AMBOS containers, restart de ambos:
plink -batch -pw "Kashau2022##" root@100.77.154.31 \
  "cd /docker/betmexico && docker compose restart"
```

### D) Cambio que requiere migración de BD (nueva columna, tabla, etc.)

1. Agregar migración aditiva al `_migrate()` en `app.py:95`:
   ```python
   ("nueva_col", "ALTER TABLE deposit_attempts ADD COLUMN nueva_col TEXT"),
   ```
2. Push backend (paso B)
3. Verificar que arrancó SIN error de migración:
   ```bash
   plink -batch -pw "Kashau2022##" root@100.77.154.31 \
     "docker logs --tail 30 betmexico-web | grep -iE 'migrate|alter|error'"
   ```
4. Confirmar columna en BD:
   ```bash
   plink -batch -pw "Kashau2022##" root@100.77.154.31 \
     'docker exec betmexico-web python -c "import sqlite3; c=sqlite3.connect(\"/data/betmexico_accounts.db\"); print([r[1] for r in c.execute(\"PRAGMA table_info(deposit_attempts)\")])"'
   ```

### E) Cambio en Dockerfile o requirements

Requiere rebuild.

```bash
# Subir Dockerfile editado (idealmente via tmp file para evitar issues de escape)
pscp -batch -pw "Kashau2022##" infra/Dockerfile root@100.77.154.31:/docker/betmexico/Dockerfile

# Build foreground (NO background — puede pelear con buildkit)
plink -batch -pw "Kashau2022##" root@100.77.154.31 \
  "cd /docker/betmexico && docker build -t betmexico:latest . > /tmp/build.log 2>&1 ; tail -8 /tmp/build.log"

# Recreate containers
plink -batch -pw "Kashau2022##" root@100.77.154.31 \
  "cd /docker/betmexico && docker compose up -d --force-recreate"
```

**Cuidado**: si el build se cuelga en "Configuring tzdata", verificar que el Dockerfile tenga `ENV DEBIAN_FRONTEND=noninteractive` antes del `apt-get install`.

### F) Cambio en `.env` (keys, paths)

```bash
# Editar .env en KVM4 directamente (NO commitear .env)
plink -batch -pw "Kashau2022##" root@100.77.154.31 \
  "sed -i 's/OLD_KEY/NEW_KEY/g' /docker/betmexico/.env"

# Restart para que tome los nuevos values
plink -batch -pw "Kashau2022##" root@100.77.154.31 \
  "cd /docker/betmexico && docker compose restart"
```

### G) Cambio en config Traefik / dominio

Traefik corre en `/docker/traefik/` (NO en `/docker/betmexico/`). Labels Traefik están en `docker-compose.yml` de betmexico.

```bash
# Para agregar otro dominio:
# 1. Editar infra/docker-compose.yml — extender Host(`...`) en label
# 2. Subir compose
pscp -batch -pw "Kashau2022##" infra/docker-compose.yml root@100.77.154.31:/docker/betmexico/

# 3. Apply
plink -batch -pw "Kashau2022##" root@100.77.154.31 \
  "cd /docker/betmexico && docker compose up -d"

# 4. Verificar cert
echo | openssl s_client -servername <nuevo-dominio> -connect <nuevo-dominio>:443 2>/dev/null | openssl x509 -noout -subject -issuer -dates
```

## Estándar de commit + push

Después de cualquier deploy exitoso:

```bash
cd "C:\Users\rober\Dropbox\TESTING DEV\repos\botmex-dashboard"
git add <archivos>
git commit -m "<tipo>(<scope>): <mensaje corto>

<detalle opcional>

Smoke test:
- /api/health → 200
- <endpoint específico> → <código esperado>"

git push origin main
```

**Tipos**: `feat`, `fix`, `chore`, `docs`, `refactor`, `perf`, `test`.
**Scopes**: `backend`, `frontend`, `infra`, `deps`, `bitacora`, etc.

## Hot-mount cheat sheet

| Cambio | Requiere | Comando final |
|---|---|---|
| static/*.js, *.html, *.css | pscp + refresh navegador | — |
| *.py (backend) | pscp + restart web | `docker compose restart web` |
| betmexico_*.py (bot modules) | pscp + restart de ambos | `docker compose restart` |
| Dockerfile, requirements | rebuild + recreate | `docker compose build && docker compose up -d --force-recreate` |
| .env | edit + restart | `docker compose restart` |
| docker-compose.yml | pscp + `up -d` | `docker compose up -d` |

## Después de cualquier deploy

Ver `deploy-checklist.md` para el smoke test obligatorio.
