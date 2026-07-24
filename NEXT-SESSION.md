# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso — NO se diluye
**Implementar el BOTÓN DE RETIRO AUTOMÁTICO en La Pantalla.** Plan TDD completo listo para ejecutar: `~/.claude/plans/vale-armamos-un-smartplan-abundant-emerson.md` (9 tasks A→I, modelos por subagente asignados, guardarrails bug#1/#2/#3 con tests). Spec fuente: `docs/superpowers/specs/2026-07-24-boton-retiro-automatico-design.md`. Flujo probado en campo (5 retiros reales, msaidrzz, $1,355) en `docs/RECON_BETMEX_API.md` §"FLUJO DE RETIRO EXACTO".

**Logrado y CERRADO:** los 5 retiros de msaidrzz llegaron COMPLETOS ($1,355). El "faltante de $300" era un retiro atorado en el banco (retardo de procesamiento), no bug. Quedan ~$102 en la cuenta para el smoke del botón. Lección clave: `status:6` en API BetMexico = ejecutado del lado de ellos, NO garantiza aterrizaje en banco.

## ▶ Con qué arrancas (PRIMERA acción del próximo turno)
**`/Smartexe` sobre el plan.** Primer paso: copiar el plan de `~/.claude/plans/vale-armamos-un-smartplan-abundant-emerson.md` a `docs/superpowers/plans/2026-07-24-boton-retiro-automatico.md` + crear rama `feat/boton-retiro-automatico` desde `feat/auditoria-tdah-2026-07-20`. Luego Task A (migración tabla `account_withdrawals`) → Task B (módulo `withdrawals.py` TDD) → ... → Task I (retiro real $100).

## 🧭 Recomendación de approach
**Backend primero (Tasks A→E), todo TDD con `httpx.MockTransport`**, luego frontend (F→G), luego smoke HTTP sin dinero (H, amount=99999→409), y **el retiro real $100 lo dispara Robert con click en la UI** (Task I, NO subagente a ciegas — dinero real). Decisiones técnicas ya tomadas en el plan: módulo `withdrawals.py` aislado (no en app.py de 3306L); PASO0 reusa `clabe_fetch._load_jwt_for_account` (NO `tools/bmx_call.py`, es CLI-only); `begin_withdrawal` **single-shot** (no `call_with_proxy_failover` — un retry duplica el retiro; los GET sí fallover). Smoke corregido: **$100 no $1** (BetMexico mínimo $100).

## ⏳ Pendientes próximos
- [ ] **Ejecutar el plan via `/Smartexe`** (9 tasks A→I, ver `~/.claude/plans/vale-armamos-un-smartplan-abundant-emerson.md`).
- [ ] **Smoke real $100 msaidrzz** (Task I) — 1 sola oportunidad real, lo dispara Robert con click. Verificar 3 guardarrails: gateway==2 (bug#3), lastAccountDigits coincide (bug#1), 2-fases no "entregado" (bug#2).
- [ ] **Limpieza backend congelado** (`account_refresh.py`, `prewarm.py`, `deposits.py`): cambios `_fetch_looks_empty` de auditoría 2026-07-22 — resolver `float("N/A")` ValueError y falso positivo `balance_only` con TDD. **NO commitear hasta resolver.** Siguen modified sin commitear (intencional).
- [ ] **Deploy tras implementar** (Task H): pscp + restart + smoke HTTP + `StartedAt > mtime`.

## ✅ Hecho esta sesión (2026-07-24, tarde)
- **Plan TDD del botón de retiro** completo (9 tasks, modelos por subagente Opus/Sonnet/Haiku, vigilancia anti-cuelgue). Fuera del repo en `~/.claude/plans/`.
- Anclajes verificados con 3 Explore en paralelo: backend `app.py`, `clabe_fetch.py`+`proxy_pool.py`+RECON, frontend `pantalla.js/css`.
- 1 Plan agent validó arquitectura + produjo tests TDD concretos (28 tests módulo + 20 endpoints).
- **Commits de la sesión pasada, estabilizados esta sesión:**
  - `bf185ac` — `feat(clabes): panel SPEI NVIO/STP persistido en BD + endpoints` (tabla `account_deposit_clabes`, `clabe_fetch.py`, GET/POST `/clabes`, UI).
  - `bbb14d8` — `feat(recon): spec botón retiro automático + herramientas CDP/bmx_call` (spec, `tools/bmx_call.py`, `tools/cdp_*`).

## 🔧 Decisiones tomadas
- **`withdrawals.py` módulo aislado** (raíz, async, importable) — NO en `app.py` inline. Motivo: `app.py` ya tiene 3306L; el patrón del repo es que llamadas a BetMexico vivan en módulos dedicados (`clabe_fetch.py`, `autoexclusion.py`, `deposits.py`); módulo aislado = TDD con MockTransport sin levantar FastAPI.
- **PASO0 reusa `clabe_fetch._load_jwt_for_account(db, id)`** (clabe_fetch.py:37) — ya valida expiración. NO reimplementar, NO usar `tools/bmx_call.py` (CLI-only, no importable; su `load_jwt` busca por email LIKE). Corrige el spec §4 que decía "reusar load_jwt de bmx_call.py".
- **`begin_withdrawal` single-shot** (NO `call_with_proxy_failover`): un retry por proxy-fail podría duplicar el retiro (a diferencia de `BeginDeposit` que es idempotente). Los GET (PASO1/2/4/5) sí fallover. Trade-off documentado en el plan.
- **Smoke $100 no $1:** BetMexico no permite retiros <$100. 1 sola oportunidad real en msaidrzz (~$102). Disparado por Robert (click), no subagente.
- **Plan vive fuera del repo** (`~/.claude/plans/`) — se copia a `docs/superpowers/plans/` como 1er paso de `/Smartexe`.
- **CDP > chrome-devtools-mcp** para captura (sesión pasada).
- **Capturas con JWTs (`tools/*.jsonl|log`) NO commitean** (.gitignore línea 49-50).

## 🖥️ Estado del sistema al cerrar
- **KVM4:** web ✓ Up 46h · bot ✓ Up 3d (vivo, no Exited) · health ✓ 200 (937 cuentas) · pool = 1001 proxies (1000 dataimpulse + 1 nodemaven) · cero errores 406/504/Traceback en 12h (solo polls KPIs).
- **Repo:** rama `feat/auditoria-tdah-2026-07-20`, 2 commits nuevos (`bf185ac` clabes + `bbb14d8` recon/spec/tools). **NO pusheados a Forgejo** todavía (la rama ya estaba pusheada hasta `30d4b57`; estos 2 commits son locales — push pendiente, decisión de Robert/estabilidad).
- **Congelados sin commitear (intencional):** `account_refresh.py`, `prewarm.py`, `deposits.py` (auditoría 07-22). `.agents/`, `AGENTS.md` ajenos, no tocar.
- **CDP/Chrome local:** Chrome 150 con `--remote-debugging-port=9222`, sesión espinoza logueada viva (JWT válido hasta 2026-07-31) — para calleo de verificación posterior (bug#3 reembolso a tarjeta), NO bloquea la implementación del botón.
