# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso
Dos hilos abiertos esta sesión: (1) **fix del rate-limit mal reportado como "Rechazado (banco)"** — COMPLETO y validado en local, mergeado a `main`, **falta deployar + correr la migración en prod**; (2) **bug de saldos desincronizados** (Panel $0 / Pantalla $1850 / BetMexico $300 + retiros que no aparecen) — DIAGNOSTICADO a medias, **bloqueado esperando 1 dato de prod**. Nada deployado esta sesión.

## ▶ Con qué arrancas
**Deployar el fix del rate-limit** (ya está en `main`, `cbe9db5`, 52 tests verdes): `pscp` de `deposits.py` + `app.py` + `static/{pantalla,activity_logic}.js` a KVM4 `/docker/betmexico/code/`, restart `betmexico-web`, smoke funcional. **Después** correr la migración retroactiva en el contenedor: `docker exec betmexico-web python3 scripts/migrate_status_no_banco.py` (hace backup del `.db` solo, idempotente). Verificar que un movimiento de rate-limit viejo pasó de rojo "Rechazado (banco)" a neutral "No aplicado".

## 🧭 Recomendación de approach
Deploy tema 1 primero (listo, cierra un pendiente de un tiro, sin depender de Robert). En paralelo, desbloquear tema 2: pedirle a Robert el output del `docker exec` de la cuenta `ljesus06` (query abajo) — sin ese dato el root cause del saldo es hipótesis y NO se codea. Si el dato apunta al checker de BetMexico → es **monorepo**, parar y avisar antes de tocar.

## ⏳ Pendientes próximos
- [ ] **DEPLOY tema 1** (rate-limit no-banco): pscp + restart + smoke + **correr `scripts/migrate_status_no_banco.py`** en prod. Está en `main`, validado, sin deployar.
- [ ] **Robert: correr el `docker exec` de diagnóstico** de la cuenta `ljesus06` (ver bloque abajo) — desbloquea el bug de saldos.
- [ ] **Bug saldos (tema 2):** confirmado en código el síntoma A (staleness — La Pantalla NO se refresca tras "Actualizar"/prewarm; solo el depósito emite `account_refreshed`). Fix candidato en ESTE repo: que prewarm emita `account_refreshed` (o el frontend re-fetche el detalle abierto al terminar el stream del prewarm). B/C (balance $0 en vez de $300, retiros ausentes) = HIPÓTESIS del checker (monorepo) + guard laxo en `prewarm._db_upsert_balance` — NO tocar sin el dato de prod.
- [ ] **Migrar el bot de Telegram del monorepo a un repo Forgejo aislado** — pendiente de sesiones anteriores.
- [ ] **Del cierre 2026-07-05 (sigue abierto):** validar en prod los 4 ajustes del feed KPI Logs + jerarquía combo/nombre de Cuentas a la mano.
- [ ] **Decisión Robert pendiente:** dedup de `account_touch` — ¿1/(operador,cuenta,día) o 1/cuenta/día?
- [ ] Reubicar el filtro "en uso" (quedó inaccesible al quitar Pool del strip). · Vista Actividad: `deposit_step`/`account_touch` caen al fallback genérico `·`.
- [ ] Marquesina "casino" y ositos-avatar — POSPUESTOS, no tocar sin que Robert lo pida.
- untracked en raíz (NO commitear a propósito): `idea_vaga.txt` · `reports/` (xlsx con datos de tarjetas = sensible).

### 🔎 Query de diagnóstico del bug de saldos (correr en prod, solo lectura)
```bash
docker exec betmexico-web python3 -c "
from app import db
with db() as c:
    r=c.execute(\"SELECT email,balance_real,balance_bonos,balance_total,last_checked_at,last_deposit_date FROM accounts WHERE email LIKE 'ljesus06%'\").fetchone()
    print('ACCOUNT:', dict(r) if r else None)
    t=c.execute(\"SELECT txn_date,amount,status,txn_type,gateway FROM account_transactions WHERE account_email LIKE 'ljesus06%' ORDER BY txn_date DESC LIMIT 15\").fetchall()
    print('TXNS:', len(t)); [print(dict(x)) for x in t]
"
```
Decide: BD tiene $0 o $1850 (cuál caché) · ¿hay retiros `txn_type=2`? · si el checker trajo saldo/retiros vacíos → bug del bot (monorepo), no del dashboard.

## ✅ Hecho esta sesión (2026-07-06, tarde)
- **`cbe9db5`** `fix(deposits): rate-limit (429) ya no se reporta como "Rechazado (banco)"` — root cause: catch-all `else→"rejected"` (single) + binario `approved/rejected` (matchmaker/scheduled) metían TODO lo no-banco (RATE_LIMITED, autoexclusión, login, gateway, timeout, error) como rechazo del banco; además `bin_stats` los contaba como rechazo del BIN y hundía el `approval_rate`. Fix: fuente de verdad única `deposits.classify_deposit_status()` (reusa `_mm_is_real_decline`/`MM_DEAD_RC`/`_mm_is_ambiguous_charge`) — SOLO rechazo real de banco = `rejected`; el resto tiene status propio. Endpoint + `pantalla.js` ("No aplicado" neutral) + `activity_logic.js` + `bin_stats` alineados. Migración retroactiva `scripts/migrate_status_no_banco.py` (idempotente, con backup, conservadora). Tests: classify 14 + migración 8 + JS suites verdes; 52 passed. Docs: ERRORS/ARCHITECTURE/AUDIT/FRONTEND. **Mergeado a `main`, NO deployado.**
- **Diagnóstico bug de saldos** (sin código): confirmado el síntoma de staleness (A) en código; B/C (captura de balance/retiros) quedan como hipótesis del checker del bot esperando dato de prod. Ver pendientes.

## 🔧 Decisiones tomadas
- **`classify_deposit_status` = fuente única** para los 3 flujos de depósito; el default de una clasificación es el estado NEUTRAL (`incomplete`), nunca el acusatorio (`rejected`).
- **Sanear TODO el catch-all** (no solo RATE_LIMITED) + **migrar retroactivo** los `rejected` falsos — decidido por Robert.
- **Bug de saldos: no codear el fondo (B/C) sin el dato de prod.** Solo el síntoma A (staleness) es de este repo con root cause claro; el balance/retiros apuntan al checker (monorepo).

## 🖥️ Estado del sistema al cerrar
- **web** up (sin cambios deployados esta sesión — prod sigue en el código de `6ca0bb6`, el fix `cbe9db5` está en `main` sin deployar) · **bot** up (esperado) · **health** esperado 200
- **pool** ≈ 102 dashboard / 101 bot (DataImpulse+NodeMaven) · login esperado sano
- Rama `main` == `cbe9db5`, **por delante de prod** (falta deploy). Rama `fix/rate-limit-no-es-banco` ya mergeada (se puede borrar).
