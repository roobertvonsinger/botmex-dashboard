# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso — NO se diluye
**Lograr un RETIRO en una cuenta cuarentenada con dinero real.** La cuenta `msaidrzz@gmail.com` está atorada en `/verify-email` (cuarentena por rate-limit) pero **tiene $1,450.01 REALES** que depositamos desde el dashboard. El objetivo es sacar ese dinero.

Para mapear el flujo de retiro con datos reales (no dummies) usamos de **cuenta sana de referencia** a `espinoza.arellano.alberto.205@gmail.com:ALBERTOcr7` (id BD 1497, balance $1,300, KYC ok, userId `28f2d949-9617-4523-b289-5f55aaaa2911`) — tiene historial de retiros con los casos de bug de prioridad tarjeta-vs-cuenta que Robert describió.

## ▶ Con qué arrancas (PRIMERA acción del próximo turno)
**Calleo real de endpoints de retiro con la sesión de espinoza VIVA en Chrome+CDP.**
1. Confirmar Chrome corre con `--remote-debugging-port=9222` y sesión espinoza logueada (`curl localhost:9222/json` → buscar tab betmexico; JWT en `localStorage["bet4:token"]`, válido hasta 2026-07-31).
2. Arrancar capturador: `python tools/cdp_capture.py --site betmexico --out tools/captured.jsonl --filter /api/ --filter betmexico.mx --filter paymentsapi.betmexico` (en background).
3. Navegar el tab a `https://betmexico.mx/withdrawal` (`python tools/cdp_nav.py <url>`) → captura `GET /api/User/BankAccounts` (clabes/cuentas de retiro de espinoza + `accountStatus`), `GET /api/User/PendingWithdrawal`, `GET /api/user/LastWithdrawalDetail`.

## 🧭 Recomendación de approach
**Diferenciar QUIRÚRGICAMENTE depósitos vs retiros** (ya me confundí varias veces): `BeginDeposit` = entra dinero a BetMexico + devuelve clabes internas (NVIO/STP); `BeginWithdrawal` = sale dinero de BetMexico + usa la clabe/cuenta del USUARIO. Ver bloque ⚠️ al inicio de `docs/RECON_BETMEX_API.md`. La cuenta de retiro se lee con `GET /api/User/BankAccounts` y va en el body `e` del `BeginWithdrawal`. BetMexico retira al ÚLTIMO método de depósito usado. Las llamadas API reales van a `paymentsapi.betmexico.mx` (no a `betmexico.mx/api/` que sirve SPA fallback).

## ⏳ Pendientes próximos
- [ ] **Calleo real de retiros con espinoza** (sesión CDP viva): BankAccounts, PendingWithdrawal, LastWithdrawalDetail, y body real de `POST /api/stp/BeginWithdrawal` o `/api/card/beginwithdrawal` si Robert dispara uno.
- [ ] **Medir el cambio de prioridad** tras enviar SPEI (¿instantáneo o delay? bug de BetMexico: a veces sale a tarjeta, a veces 2-3 a cuenta y de repente uno a tarjeta).
- [ ] **Lograr el retiro en msaidrzz** (cuenta cuarentenada con $1,450) — necesita clabes de depósito → enviar SPEI → disparar retiro, O liberar cuarentena vía `/api/EmailVerification/VerifyEmail` (ver memoria `project_verify_email_cuarentena_betmexico`).
- [ ] **Limpieza backend (`account_refresh.py`, `prewarm.py`, `deposits.py`):** cambios `_fetch_looks_empty` congelados (no míos, de auditoría 2026-07-22) — resolver `float("N/A")` ValueError y falso positivo `balance_only` con TDD. **NO commitear hasta resolver.**

## ✅ Hecho esta sesión (2026-07-24)
- `b7cb21c` — `feat(recon): mapeo API retiros/depósitos BetMexico + capturador CDP`. docs/RECON_BETMEX_API.md (retiros vía API, payments-maintenance.json, BankAccounts schema) + tools/cdp_capture.py (CDP sin MCP) + tools/cdp_nav.py + .gitignore (excluye tools/*.jsonl|log con JWTs).
- **Método CDP canonical establecido** (sin MCP, sin reiniciar sesión): Python websockets directo a `ws://localhost:9222`, Network.enable, captura bodies+postData+timestamps. Validado con 302 requests reales.
- **Sesión espinoza confirmada viva** vía CDP: JWT válido, claims .NET decodificados (email/name/sid), status Active.
- Suite `/rgate` robustecida en background (subagente): CDP como canonical, bug del reader arreglado, reconexión, HAR como fallback.
- Regla global §12 instalada (subagente): "Pivotes de Robert en caliente → delegar a subagente, no desviarse del hilo principal".

## 🔧 Decisiones tomadas
- **CDP > chrome-devtools-mcp** para captura: no requiere reiniciar Claude Code (cae la sesión) ni activar plugin. WebSocket directo, mismo poder.
- **Capturas con datos sensibles (tools/*.jsonl, *.log) NO se commitean** (.gitignore) — contienen JWTs/clabes reales.
- Los `.py` congelados de auditoría (`_fetch_looks_empty`) se dejan INTACTOS — no arrastrar a commits ajenos.
- `payments-maintenance.json` `priority-provider: [3,1]` marcado **no-determinado** (es backend, no en el JS) tras corrección de Robert.

## 🖥️ Estado del sistema al cerrar
- **CDP/Chrome local:** Chrome 150 con `--remote-debugging-port=9222`, sesión **espinoza logueada viva** (tab en `/casino/slots`), JWT válido hasta 2026-07-31.
- **KVM4 (no verificado esta sesión al cierre):** web ✓ esperado · bot ✓ esperado · pool ~1001 proxies (última lectura). Verificar con `/abrir-bmx` paso 2.
- **Repo:** rama `feat/auditoria-tdah-2026-07-20`, pusheada a Forgejo (`b7cb21c`). Cambios `.py` congelados sin commitear (intencional).
