# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso — NO se diluye
**Botón de retiro automático en La Pantalla.** Plan TDD A→I. Backend (A+B+C) y frontend (F+G) **completos, deployados y smoke-testeados en KVM4**. Falta: verificación visual del bloque (D), y Task I — el retiro real de $100 que dispara Robert con un click.

## ▶ Con qué arrancas (PRIMERA acción del próximo turno)
1. **Verificación visual `.pat-wd`** — BLOQUEADA de nuevo esta sesión: el Browser pane (`mcp__Claude_Browser__navigate`) rechazó la navegación a `botmexico.com.mx` incluso tras aprobación explícita de Robert (`navOk:false`, sin permission-card visible). Puede ser glitch de sesión — reintentar al abrir; si persiste, pedirle a Robert un screenshot manual de La Pantalla de `msaidrzz@gmail.com` (id 637) o usar `claude-in-chrome` (Chrome real) en vez del Browser pane. Objetivo cuando funcione: `getBoundingClientRect` confirma que el bloque de retiro encaja en `.pat-col-ident` sin overflow (comparar contra `.pat-clabes`, mismo patrón).
2. **PIN de Robert — mapear decisión de destino del retiro** (ver memoria `project_pin_mapeo_decision_destino_retiro`): en qué momento/dónde decide BetMexico la cuenta/rail de un retiro, si hay flag pre-flight, si el marcador `priority-provider:[3,1]` que sospecha Robert tiene algo que ver (spoiler: no directamente — es ruteo de proveedor SPEI backend, no cuenta destino; ver la memoria para el detalle ya mapeado y lo que falta).
3. Con ambos resueltos → **Task I**: Robert dispara el retiro real de $100 en `msaidrzz` desde la UI, verificar los 3 guardarrails (gateway==2, dígitos coinciden, copy 2-fases sin "entregado").

## 🧭 Recomendación de approach
El botón ya está en producción y probado sin dinero real (smoke 409 con amount=99999 llegó a PASO2 contra BetMexico real y se detuvo antes de PASO3). Lo único que falta antes de Task I es un ojo humano o browser-driven en el layout — no hay más código pendiente para eso. Si el Browser pane sigue fallando al abrir la sesión, probar `claude-in-chrome` primero (Chrome real del usuario) antes de insistir con el pane. El PIN de destino-de-retiro es una investigación aparte (no bloquea Task I, pero Robert quiere mapearlo antes de confiarle más retiros reales sin supervisión) — atacarlo releyendo `docs/RECON_BETMEX_API.md` (ya tiene 80% del contexto), no re-investigar desde cero.

## ⏳ Pendientes próximos
- [ ] Verificación visual `.pat-wd` en navegador (getBoundingClientRect) — Browser pane fallando, ver punto 1 arriba.
- [ ] PIN: mapear momento/lugar de la decisión de destino del retiro (ver memoria, requiere posiblemente un depósito de prueba — coordinar con Robert, dinero real).
- [ ] **Task I — retiro real $100 en `msaidrzz`** (Robert, click en UI, NO automatizar).
- [ ] **Limpieza backend congelado** (`account_refresh.py`, `prewarm.py`, `deposits.py`): cambios `_fetch_looks_empty` de auditoría 2026-07-22 sin commitear — resolver con TDD antes de commitear (arrastrado de varias sesiones, sigue intencional, sin tocar esta sesión).
- [ ] Actualizar `docs/AUDIT.md` con el estado del botón de retiro si se decide llevar tracking ahí (no se forzó esta sesión, no había sección previa).

## ✅ Hecho esta sesión (2026-07-24, sesión 2)
- **Fix operativo KVM4 — token bot Telegram rotado:** Robert removió el token viejo y olvidó poner el nuevo (`8516175452:AAHd...`) → `betmexico-bot` estaba en crash-loop (`InvalidToken`, token viejo `AAEFechK...`). Actualizado `BMX_BOT_TOKEN` en `/docker/betmexico/.env` (con backup previo `.env.bak.<timestamp>`) y recreado el contenedor (`docker compose up -d bot` — el nombre de servicio es `bot`, no `betmexico-bot`). Verificado: `betmexico-bot` up, "🚀 Bot iniciado (Polling...)" + "✅ Comandos registrados" sin errores.
- **Verificación visual `.pat-wd` intentada y bloqueada:** Browser pane (`mcp__Claude_Browser`) rechazó navegar a `botmexico.com.mx` (`navOk:false`) pese a permiso explícito de Robert — no llegó tarjeta de aprobación visible. Probado con tab nuevo y `force:true`, mismo resultado. Sin código tocado, sin cambios en el repo esta sesión.

## 🔧 Decisiones tomadas (sesión anterior, 2026-07-24 sesión 1 — vigentes)
- Schema fix: Opción A (columnas reales en `conftest.py`), no el parche de `_acc_id()` — arregla el bug de fondo para cualquier test futuro que use `/api/accounts`.
- SSE multi-operador: reusar `window.Pantalla.open(id)` (ya idempotente en re-apertura) en vez de exponer un método `refresh()` nuevo — mismo resultado, menos superficie.
- Polling: 1 solo `setInterval` por cuenta (`_wdPolls`), nunca <60s, se detiene en terminal o al cerrar La Pantalla — guardarrail explícito del plan, no negociable.
- No se forzó un push a `main` ni PR — la rama sigue en `feat/boton-retiro-automatico`, decisión de merge queda para cuando Task I cierre el ciclo completo.

## 🖥️ Estado del sistema al cerrar
- **KVM4:** web ✓ (up ~1h, health 200, 937 cuentas) · bot ✓ (recreado con token nuevo, polling activo, "Up 10 minutes" al cierre) · pool 1001 proxies (1000 dataimpulse + 1 nodemaven) · 0 errores nuevos.
- **Repo:** rama `feat/boton-retiro-automatico`, sin commits nuevos esta sesión (nada de código tocado). Congelados sin commitear (intencional, arrastrado): `account_refresh.py`, `prewarm.py`, `deposits.py`. Ajenos, no tocar: `.agents/`, `AGENTS.md`.
