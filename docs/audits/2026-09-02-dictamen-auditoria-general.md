# Dictamen Técnico: Validación de Auditoría (Fases A y B) y Resolución de Drifts

**Fecha:** 2026-09-02  
**Repositorio:** `botmex-dashboard`  
**Estado:** Avance validado empíricamente — Drifts resueltos con evidencia dura. Fase C pendiente.

---

## 1. Resolución de Hallazgos "NO_VERIFICADO" (Drifts)

| Hallazgo | Severidad reportada | Realidad empírica comprobada en código / Git | Dictamen / Acción |
|---|---|---|---|
| **`support_*.py` y `support_dockerd.py` solo en `.pyc`** | P0 (`DEPLOYMENT_DRIFT`) | **Fuente 100% preservada** en rama `feat/support-agent` (commit `8cc125c`). Desarrollada el 2026-08-01 para el asistente SA y retenida sin merge a `main` porque el 9-router estuvo offline. En `app.py:753` aislada con `try/except`. | **Desclasificado de P0 a P3 (WIP Branch).** No es código fantasma ni pérdida de fuente. En `main` el router degrada en silencio. |
| **`docker-compose.yml` dice `python web/app.py` vs `app.py` en raíz** | P1 (`DEPLOYMENT_DRIFT`) | En VPS KVM4 (`DEPLOY.md` §1), el host monta `/docker/betmexico/code:/app`. El dashboard vive en `/docker/betmexico/code/web/`. En el contenedor (`/app`), la ruta es `/app/web/app.py`. Este repo local es la vista aplanada de `web/`. | **Validado como Arquitectura de Deploy (No Drift Real en Prod).** |
| **`betmexico_bot.py` (legacy) referenciado pero ausente en repo** | P1 (`CONFIG_DRIFT`) | El bot legacy vive en el monorepo (`Proyectos/BetMexico/Telegram/`), se despliega a `/docker/betmexico/code/betmexico_bot.py` y es de uso exclusivo de Robert. Este repo es exclusivamente Dashboard (`web/`) y mock bot. | **Validado por Diseño.** Conforme a directiva de Robert: no tocar ni intentar traerlo a este repo. |
| **`shared/betmexico_payment_analyzer.py` vs raíz** | P1 (`CONFIG_DRIFT`) | El de raíz es **V10 activo** (recuperación reciente, bonos de sesión limpia y grades A/B/C/D). El de `shared/` es copia congelada V9. `app.py:111` importa V10 de raíz. | **Confirmado como candidato de Fase C (Dead/Duplicated Code).** `shared/` es legacy congelado. |
| **`saneador_daemon.py` fuera de compose** | P2 (`DEPLOYMENT_DRIFT`) | Herramienta standalone de mantenimiento/auditoría manual de cuentas. Desacoplada del compose principal. | **Validado como Tool Independiente.** No requiere contenedor persistente. |

---

## 2. Validación de Fase A (Entrypoints) y Fase B (Flujos)

1. **Entrypoints Productivos:**
   - `betmexico-web`: Servidor FastAPI (`app.py`), puerto 8080 tras Traefik con TLS (`botmexico.com.mx`, `botmexico.net`). Mountea `/api/prewarm` y `/api/deposits`.
   - `betmexico-mock-bot`: Polling Telegram (@betmexbot) en `telegram_bot_mock/bot.py`.
   - 6 Background Loops en `_lifespan()`: Health (90s), Janitor locks, Window watcher, Release watchdog, JWT Keepalive (1h) y Account Refresh (20m) + Retiros pendientes (60s).
2. **Flujos Críticos Verificados:**
   - **Flujo 3 (`/bet` → Matchmaking → Depósitos):** Totalmente mapeado. Respeta las 9 invariantes canónicas (scoring continuo, ventana 1h, 3 strikes, 1:1, guard de saldo, certificación 3DS a A+).
   - **Flujo 4 & 5 (Auth & Retiros):** Sesiones cookies con rol SA/operador; retiros automáticos idempotentes en `withdrawals.py` con watchdog en `account_refresh.py`.
   - **Flujo 7 (Login Orchestrator):** `gentle_login()` con semáforo global de concurrencia 2 y pool de tokens JIT anti-fuga de captchas.

---

## 3. Pendientes Fase C (Contaminación y Hotspots)

1. **Concurrencia SQLite y Doble Singleton:** Auditar `app.py:3369-3370` (`BetmexicoDB(Path(db_path))` bypass de `app.db(write=True)`).
2. **Dependencias Circulares:** Analizar `app.py` ↔ `auto_deposit.py` ↔ `deposits.py` y `sys.modules.setdefault("app", ...)`.
3. **Código Muerto:** Confirmar referencias a `_legacy/` (2,075 líneas) y desfasaje de `shared/betmexico_payment_analyzer.py` (V9).
4. **Contaminación en Tests:** `tests/test_maintenance_mode.py` modificando `os.environ` en proceso vivo.
