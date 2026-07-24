# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso — NO se diluye
**Botón de retiro automático en La Pantalla.** Plan TDD A→I. Backend (A+B+C) y frontend (F+G) **completos, deployados y smoke-testeados en KVM4**. Falta: verificación visual del bloque (D), y Task I — el retiro real de $100 que dispara Robert con un click.

## ▶ Con qué arrancas (PRIMERA acción del próximo turno)
1. **Verificación visual `.pat-wd`** (Task F-run, pendiente por extensión Chrome no conectada la sesión pasada): abrir `https://botmexico.com.mx`, loguear como SA, abrir La Pantalla de `msaidrzz@gmail.com` (id 637), confirmar con `getBoundingClientRect` que el bloque de retiro encaja en `.pat-col-ident` sin overflow (comparar contra `.pat-clabes`, mismo patrón).
2. **PIN de Robert — mapear decisión de destino del retiro** (ver memoria `project_pin_mapeo_decision_destino_retiro`): en qué momento/dónde decide BetMexico la cuenta/rail de un retiro, si hay flag pre-flight, si el marcador `priority-provider:[3,1]` que sospecha Robert tiene algo que ver (spoiler: no directamente — es ruteo de proveedor SPEI backend, no cuenta destino; ver la memoria para el detalle ya mapeado y lo que falta).
3. Con ambos resueltos → **Task I**: Robert dispara el retiro real de $100 en `msaidrzz` desde la UI, verificar los 3 guardarrails (gateway==2, dígitos coinciden, copy 2-fases sin "entregado").

## 🧭 Recomendación de approach
El botón ya está en producción y probado sin dinero real (smoke 409 con amount=99999 llegó a PASO2 contra BetMexico real y se detuvo antes de PASO3). Lo único que falta antes de Task I es un ojo humano o browser-driven en el layout — no hay más código pendiente para eso. El PIN de destino-de-retiro es una investigación aparte (no bloquea Task I, pero Robert quiere mapearlo antes de confiarle más retiros reales sin supervisión) — atacarlo releyendo `docs/RECON_BETMEX_API.md` (ya tiene 80% del contexto), no re-investigar desde cero.

## ⏳ Pendientes próximos
- [ ] Verificación visual `.pat-wd` en navegador (getBoundingClientRect).
- [ ] PIN: mapear momento/lugar de la decisión de destino del retiro (ver memoria, requiere posiblemente un depósito de prueba — coordinar con Robert, dinero real).
- [ ] **Task I — retiro real $100 en `msaidrzz`** (Robert, click en UI, NO automatizar).
- [ ] **Limpieza backend congelado** (`account_refresh.py`, `prewarm.py`, `deposits.py`): cambios `_fetch_looks_empty` de auditoría 2026-07-22 sin commitear — resolver con TDD antes de commitear (arrastrado de varias sesiones, sigue intencional).
- [ ] Actualizar `docs/AUDIT.md` con el estado del botón de retiro si se decide llevar tracking ahí (no se forzó esta sesión, no había sección previa).

## ✅ Hecho esta sesión (2026-07-24)
- **Fix bug de schema `conftest.py`** (Opción A): agregadas columnas `fullname/curp/phone` al `CREATE TABLE accounts` sintético → `test_withdrawals_endpoints.py` 20/20 verde. Commit `3a11788`.
- **Task F+G (frontend):** botón de retiro SA-only en La Pantalla (`renderPantallaWithdraw`), estado 2-fases (bug#2), alertas bug#1/#3, polling fijo 60s con resume al reabrir, SSE multi-operador (`kind:'withdrawal'`). Commit `de77328`.
- **Deploy a KVM4:** `app.py`, `withdrawals.py`, `clabe_fetch.py` (ver bug abajo), `static/{app,pantalla}.js`, `pantalla.css`. Restart limpio, health 200, `StartedAt > mtime` confirmado.
- **Bug de campo encontrado y arreglado:** `clabe_fetch.py` (commit `bf185ac`, feature de clabes SPEI) **nunca se había deployado a KVM4** — la feature estuvo muerta en prod desde que se creó. Detectado porque `withdrawals.py` lo importa al top del archivo (crash-loop al boot). Fix: deploy del módulo faltante. Documentado en `docs/ERRORS.md`.
- **Smoke H3/H4 post-deploy (sin dinero real):** `POST /withdraw {amount:99999}` en `msaidrzz` (id 637) → 409 `InsufficientBalance` real (PASO1+PASO2 contra BetMexico, sin llegar a PASO3, 0 filas nuevas en `account_withdrawals`). `GET /withdraw/status/tx-inexistente` → 404.
- **Docs actualizados:** `ENDPOINTS.md` (retiros: de "EN CURSO" a "deployado y verificado" + `last_withdrawal`), `FRONTEND.md` (sección `.pat-wd`), `SSE_EVENTS.md` (`kind:'withdrawal'`), `ERRORS.md` (bug clabe_fetch.py).
- **Push:** rama `feat/boton-retiro-automatico` a Forgejo (3 commits nuevos esta sesión: `3a11788`, `de77328`, más este de cierre).
- **Memoria nueva:** PIN de Robert sobre mapeo de decisión de destino del retiro (`project_pin_mapeo_decision_destino_retiro`).

## 🔧 Decisiones tomadas
- Schema fix: Opción A (columnas reales en `conftest.py`), no el parche de `_acc_id()` — arregla el bug de fondo para cualquier test futuro que use `/api/accounts`.
- SSE multi-operador: reusar `window.Pantalla.open(id)` (ya idempotente en re-apertura) en vez de exponer un método `refresh()` nuevo — mismo resultado, menos superficie.
- Polling: 1 solo `setInterval` por cuenta (`_wdPolls`), nunca <60s, se detiene en terminal o al cerrar La Pantalla — guardarrail explícito del plan, no negociable.
- No se forzó un push a `main` ni PR — la rama sigue en `feat/boton-retiro-automatico`, decisión de merge queda para cuando Task I cierre el ciclo completo.

## 🖥️ Estado del sistema al cerrar
- **KVM4:** web ✓ (restart limpio post-deploy, health 200, 937 cuentas) · bot ✓ (sin tocar) · pool 1001 proxies (1000 dataimpulse + 1 nodemaven) · 0 errores nuevos tras el deploy.
- **Repo:** rama `feat/boton-retiro-automatico`, pusheada a Forgejo. Congelados sin commitear (intencional, arrastrado): `account_refresh.py`, `prewarm.py`, `deposits.py`. Ajenos, no tocar: `.agents/`, `AGENTS.md`.
