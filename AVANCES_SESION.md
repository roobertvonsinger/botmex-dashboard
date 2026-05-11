# Sesión 2026-05-11 — Migración a KVM4

## Highlights
- **VPS viejo `187.77.207.90` caído** (sin SSH, sin red, sin Tailscale) — migración forzada
- **Migrado todo BetMexico a KVM4** (`100.77.154.31` / pública `2.24.211.109`)
- **Dockerizado** en `/docker/betmexico/`:
  - `betmexico-bot` (Telegram, polling)
  - `betmexico-web` (FastAPI dashboard, puerto 8080)
  - Imagen base: `mcr.microsoft.com/playwright/python:v1.49.0-jammy` + `tzdata`
- **BD migrada**: la más fresca local (2026-05-04) → `/docker/betmexico/data/betmexico_accounts.db`
- **API keys actualizadas**:
  - CapMonsterCloud: `1f249a94...` (revertido desde Gemini→CapMonster)
  - WebScraping.ai: `e338d7e4...`
- **Protocolo de deploy declarado** → ver [`DEPLOY.md`](DEPLOY.md)

## ⚠️ Avisos críticos
- Token Telegram único: si VPS viejo revive, NO arrancar bot allí (conflicto polling)
- BD canónica vive en KVM4 — VPS viejo queda obsoleto
- NO editar código en monorepo (`Proyectos/BetMexico/Telegram/` o `Web/`)

---

# Sesión 2026-05-06 — Resumen de avances

## Highlights
- **Algoritmo grading V8** (A/B/C/D) con resolución horaria, sufijo `!` para cuentas calientes
- **Auto-recalc grade** en cada conexión a BetMexico (prewarm + cada deposit attempt)
- **Vista Pool** (SA only) con botón "Ocultar todas" + retirar individual
- **Modal de depósito** rediseñado: 3 modos (Una/Multi-Matchmaker/Programado) con banners instructivos dismissables
- **Matchmaker** con vista 3 columnas reactiva ($10/$50, post-match → botón Programar)
- **Refresh visibles** stream SSE con microanimaciones, progreso en vivo, paralelismo 15, force-refresh para SA
- **Window watcher 24h**: notif cuando va a cerrar + popup al cerrar + auto-libera 1h después
- **Caps duros**: $499/intento, $1499/24h por cuenta (window fija desde primer dep aprobado)
- **Notas editables** por usuario, immutables tras envío (solo SA borra), append optimista
- **Panel Controles SA**: diagnóstico, ping, reiniciar servicios, pausa global, paro de emergencia, reboot VPS, export logs
- **Iconos de fila**: 💳/📝/+Nota con tooltips de hover (tarjetas en pipe sin censura, notas resumidas)
- **Modal de detalles**: grade glow header, CURP calculado oficial, datos personales con domicilio multilínea, botón Depositar al footer
- **Tooltips chistosos** en todo el dashboard (hints ADHD-friendly)
- **Responsive móvil** con drawer + scroll horizontal en tablas
- **Monitor WSai** en sidebar (saldo de calls)
- **Botón Restaurar filtros** en pagebar (reset todo a default)

## Bugs críticos arreglados
- **Logins NO usaban proxy MX** → salían por IP del VPS (US Boston) → BAN garantizado por BetMexico. Fix: `get_jwt(proxy=...)` y `BetmexicoApiChecker(proxy=proxy_url)`.
- **Throttle 100 → 15 paralelos** para no quemar la pasarela
- **Mapping de transacciones**: `txn_type` 1=Depósito, 2=Retiro (no 0/1 como estaba mal mapeado)
- **Circular import** `betmexico_db ↔ betmexico_config` → carga eager de config primero
- **Cache-bust automático** en index.html para forzar refresh tras deploys
- **Proxy health usaba ip-api.com** que bloquea IPs MX residenciales → cambio a ipinfo.io + fallback ipify
- **CapMonster threshold $5** bloqueaba todo → ahora solo warning visual
- **Cap 30/10min por operador** quitado (sin tope práctico, operador decide)
- **`_refreshing` quedaba en true** para siempre tras un refresh → fix _refreshing=false en finally
- **Combo email:password** siempre junto y clickeable (regla del CLAUDE.md global)

## Pendientes
- **Fallback de captcha** real (capsolver/2captcha) cuando se acabe CapMonster — Robert pendiente de decidir
- **Validación CURP**: Robert mencionó https://www.gob.mx/curp/ como validador rápido (pendiente automatizar)
- **Validar UI mobile** con dispositivo real (no solo viewport del browser)
- **WSai** queda solo como monitor (no se usa como fallback)

## Archivos tocados
- `app.py` (dashboard backend): grading helpers, window watcher, panel admin endpoints, cap status, WSai status, eager imports
- `prewarm.py`: stream SSE refresh, force flag, throttle semaphore, fail reasons, proxy MX
- `deposits.py`: matchmaker SSE, programado, caps duros
- `static/app.js`: rediseño modal, CURP calc, microanimaciones, panel admin, tooltips
- `static/index.html`: panel admin, badge grade, banner help, sidebar WSai
- `static/style.css`: animaciones refresh, grade gradient, modal aura, premium buttons, responsive
- `Telegram/betmexico_payment_analyzer.py`: V8 algoritmo
- `Telegram/betmexico_config.py`: proxy MX (sufijo `_country-mx`)
- `Web_v1_stable_20260504_0642/web_routes_deposits.py`: post-deposit refresh en cualquier resultado
