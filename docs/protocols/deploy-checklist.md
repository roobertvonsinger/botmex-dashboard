# Deploy Checklist (BLOCKING)

> Si un item falla y no se resuelve, NO declarar el deploy completo.
> NO confiar solo en `/api/health` — hacer smoke test funcional.

## Antes del deploy

- [ ] Cambio aplicado SOLO en repo canónico `repos/botmex-dashboard/` (NO en monorepo viejo `Proyectos/BetMexico/Web/`)
- [ ] `git status` muestra solo los archivos que pretendo cambiar
- [ ] Si el cambio toca imports: `grep` confirma que no rompe `app.py` (busca `from X` para X recién agregado/quitado)
- [ ] Si toca schema BD: migración aditiva agregada en `_migrate()` (`ALTER TABLE ... ADD COLUMN`)
- [ ] Si toca Dockerfile / requirements: planificar rebuild (no es hot-mount)
- [ ] Si toca `.env`: actualizar `infra/.env.example` con la variable nueva (sin secretos)

## Durante el deploy

- [ ] pscp de los archivos correctos al destino correcto:
  - Backend Python → `/docker/betmexico/code/web/`
  - Frontend static → `/docker/betmexico/code/web/static/`
  - Bot modules → `/docker/betmexico/code/`
- [ ] Restart correspondiente:
  - Web only: `docker compose restart web`
  - Ambos: `docker compose restart`
  - Rebuild: `docker compose build && docker compose up -d --force-recreate`
- [ ] Logs SIN tracebacks (esperar 6-10s antes de chequear, hay shutdown ordenado):
  ```bash
  docker logs --tail 30 betmexico-web
  ```

## Después del deploy — smoke test FUNCIONAL

- [ ] **Health básico**: `curl -sf http://localhost:8080/api/health` → JSON con `ok:true` + count de cuentas
- [ ] **Health full** (si cambió algo de infra): `curl http://localhost:8080/api/health/full` (vía cookie) → todos los checks OK
- [ ] **Endpoint específico del cambio**: probar el endpoint que cambió. Si era un router → POST debe dar 401 o 200 (NO 503)
  - Matchmaker: `curl -X POST http://localhost:8080/api/deposits/multi/stream` → esperado 401
  - Scheduled: `curl -X POST http://localhost:8080/api/deposits/scheduled/create` → esperado 401
- [ ] **Persistencia BD** (si el cambio escribe a BD): query manual para confirmar que escribió:
  ```bash
  docker exec betmexico-web python -c "import sqlite3; c=sqlite3.connect('/data/betmexico_accounts.db'); print(c.execute('SELECT COUNT(*) FROM <tabla>').fetchone())"
  ```
- [ ] **Navegador**: Ctrl+F5 en `https://botmexico.com.mx` y probar el flujo end-to-end
- [ ] **HTTPS válido** (si se tocó Traefik): cert vigente, sin warning
  ```bash
  echo | openssl s_client -servername botmexico.com.mx -connect botmexico.com.mx:443 2>/dev/null | openssl x509 -noout -dates
  ```

## Después del smoke test exitoso

- [ ] `git commit` con mensaje descriptivo (ver formato en `deploy-protocol.md`)
- [ ] `git push origin main`
- [ ] Actualizar `docs/` si aplica (la skill `botmex-bitacora` lo recordará):
  - `ENDPOINTS.md` si cambió endpoint
  - `FRONTEND.md` si cambió UI o handler
  - `SSE_EVENTS.md` si cambió un broadcast kind
  - `AUDIT.md` si cambió comportamiento esperado/actual
  - `ERRORS.md` si descubriste un error nuevo durante el deploy

## Si algo falla

Ver `support.md` para troubleshooting estructurado por síntoma.

## Errores comunes que invalidan el deploy

- ❌ `[deps] bot init failed` en logs → router no se montó → endpoints darán 503
- ❌ `ModuleNotFoundError` en startup → falta dependencia o archivo
- ❌ `sqlite3.OperationalError: no such column` → migración faltante
- ❌ `Container Restarting` después de 30s → crash loop, ver logs

## Rollback rápido

```bash
# Volver al commit anterior
cd "C:\Users\rober\Dropbox\TESTING DEV\repos\botmex-dashboard"
git log --oneline -5
git checkout <hash_anterior> -- <archivo>

# Re-subir y restart
pscp ...
docker compose restart web
```

O para rollback total al último commit:
```bash
git reset --hard HEAD~1
# Subir TODO de nuevo desde el commit anterior
```

**Cuidado**: rollback de migración BD requiere `ALTER TABLE ... DROP COLUMN` (SQLite limitado, posible que requiera recreate de la tabla). Pensar 2 veces antes de revertir migraciones.
