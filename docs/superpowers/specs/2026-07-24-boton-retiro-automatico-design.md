# Diseño — Botón de Retiro Automático (API pura)

> Fecha: 2026-07-24 · Estado: **SPEC — pendiente implementación próxima sesión**
> Lente rectora: `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre.
> Origen: 5 retiros REALES exitosos en `msaidrzz@gmail.com` ($1,355 vía API pura, 2026-07-24). Flujo probado en campo, no inferido.
> Flujo exacto probado: ver `docs/RECON_BETMEX_API.md` §"FLUJO DE RETIRO EXACTO".

---

## 1. Objetivo

Un botón en La Pantalla (vista de detalles de cuenta) que dispare un **retiro real** de BetMexico vía API pura, sin tocar el frontend de BetMexico. Para cuentas cuarentenadas (`/verify-email` por rate-limit) donde la UI no es operable pero el JWT cacheado funciona a nivel API.

**Frictionless:** el operador mete el monto → 1 click → el dashboard ejecuta el flujo de 5 pasos, monitorea y reporta. Sin ir a BetMexico, sin copy-paste de clabes, sin pasos manuales.

## 2. Alcance

**IN (este spec):**
- Botón "Retirar" en La Pantalla (solo SA / rol autorizado) → abre control de monto + confirmación.
- Backend: nuevo endpoint `POST /api/accounts/{id}/withdraw` que ejecuta el flujo de 5 pasos con el JWT cacheado de la cuenta.
- Monitoreo del estado del retiro (polling `PendingWithdrawal`) + reporte al operador.
- Persistencia del retiro en BD (bitácora: monto, accountId destino, reference, transactionId, estado final, timestamp).

**OUT (pospuesto):**
- Retiros multi-cuenta en lote (un botón dispara N retiros). Se diseña aparte cuando Robert lo pida.
- Reembolsos a tarjeta (solo prevención/aviso, no disparo).

## 3. Flujo exacto (probado en campo — NO improvisar)

> Cada endpoint + variable aquí está **verificado con respuestas reales de msaidrzz (2026-07-24)**. 5 retiros = $1,355. El body mínimo, los enums y los hosts son hechos, no deducciones del bundle.

**Host:** TODO el flujo de retiro va a `paymentsapi.betmexico.mx`. Solo identidad va a `betmexico.mx/api/Users/`. **Siempre con proxy** (`proxy_pool.build_admin_proxy_url()`, NUNCA proxyless — ley `feedback_nunca_proxyless`). **Nunca loguear/pegar el JWT** completo.

### PASO 1 — Leer cuenta de retiro (FRESCA, inmediatamente antes de disparar)
```
GET https://paymentsapi.betmexico.mx/api/User/BankAccounts
Auth: Authorization: Bearer {jwt}
→ 200 { "accounts": [{
    "accountId": "8147ba09-d625-4566-b726-73d6f81cac9f",   ← va al body del PASO 3
    "account": "1670XXXX1215",                              ← clabe ENMASCARADA por la API
    "alias": "Cuenta Retiro",
    "institutionName": "HEY BANCO",
    "accountStatus": 2,
    "accountStatusDescription": "Approved"
  }] }
```
- Tomar el PRIMER `accountStatus:2` (Approved).
- **Si `accounts` está vacío** → la cuenta no tiene cuenta de retiro registrada. Requiere SPEI de depósito primero (un depósito SPEI rellena la cuenta de retiro en automático). Abortar con mensaje al operador.

### PASO 2 — Verificar saldo disponible
```
GET https://paymentsapi.betmexico.mx/api/Wallet/Total/Amount/ByAccountType
→ 200 { "Real": 457.01, "Bonos": 0.0 }
```
- **Solo retirar de `Real`.** `Bonos` NO es retirable.
- Validar `Real >= amount`. Si no → abortar con "saldo insuficiente (Real=$X)".

### PASO 3 — Disparar el retiro
```
POST https://paymentsapi.betmexico.mx/api/stp/BeginWithdrawal
Headers: Authorization: Bearer {jwt}, Content-Type: application/json,
         Origin: https://betmexico.mx, Referer: https://betmexico.mx/
Body (MÍNIMO que funciona — confirmado con 5 retiros reales):
{
  "accountId": "8147ba09-d625-4566-b726-73d6f81cac9f",   ← del PASO 1 (FRESCO)
  "amount": 355,                                          ← número float, NO string
  "email": "msaidrzz@gmail.com"                          ← email de la cuenta
}
→ 200 { "transactionId": "273e9543-2ce6-4759-b686-326b339fd119" }
```
**Notas del body (verificado):**
- El body MÍNIMO = `{accountId, amount, email}`. Bodies más chicos fallan (`{amount:200}` → 500 UNEXPECTED_ERROR); más grandes son innecesarios (BetMexico resuelve `account`/`institutionName`/`bankName` del `accountId`).
- `amount` es `float` (el frontend usa `parseFloat()`).
- NO incluir la clabe en texto plano (la API la enmascara de todas formas).

### PASO 4 — Monitorear el estado del retiro
```
GET https://paymentsapi.betmexico.mx/api/User/PendingWithdrawal
   (equivalente: /api/wallet/PendingWithdrawal)
→ 200 {
  "id": "273e9543-...",
  "reference": "334760946309",
  "amount": 355.0,
  "transactionStatus": 2,                    ← ver enum
  "transactionStatusDescription": "Pending",
  "gatewayType": 2,                          ← 1=tarjeta, 2=SPEI
  "isCashWithdrawal": false
}
```
- Mientras hay retiro pendiente → devuelve el objeto con datos.
- Al completar → `transactionStatus` pasa a **6** antes de desaparecer, o devuelve `{"id":null, ...todo null...}`.
- **Polling:** ~60s (los retiros de msaidrzz completaron en 3–5 min, pero **un retiro se atoró en el banco ~varios min más** — ver §5 bug #2).
- **Endpoint de status EQUIVOCADO (NO existe):** `/api/stp/TransactionStatus/{id}` da **404**. El correcto es `/api/User/PendingWithdrawal` (sin ID en path).

### PASO 5 — Confirmar + auditar (estado del rail externo)
```
GET https://paymentsapi.betmexico.mx/api/wallet/bankTransaction/{transactionId}
→ 200 {
  "id": "273e9543-...",
  "transactionStatus": 6,
  "amount": 355.0,
  "transactionTypeDescription": "Retiro",
  "reference": "334760946309",
  "transactionStatusDescription": "Successful",
  "lastModifiedUtc": "2026-07-24T18:18:35.664649"   ← cuándo el rail lo procesó
}
```
```
GET https://paymentsapi.betmexico.mx/api/Wallet/Transactions/ByUser?pageSize=50
→ { "data": { "results": [{ "id":..., "reference":..., "date":..., "type":2,
    "gateway":2, "amount":355.0, "status":6, "account":"1215", "lastAccountDigits":"1215" }] } }
```
- `type:2 + gateway:2 + status:6` = retiro SPEI completado.
- El campo `account`/`lastAccountDigits` confirma a qué cuenta fue (para detectar el bug de cambio de destino, §5 bug #1).

### Enum `transactionStatus` (retiros)
| Valor | Significado | Acción botón |
|------|-------------|--------|
| -1 | PendingVerification | seguir esperando |
| 0 | Pending | seguir esperando |
| 1 | PendingApproval | seguir esperando |
| 2 | Pending | seguir esperando |
| 6 | **Successful** | ejecutado lado BetMexico — avisar operador (NO garantiza aterrizaje en banco) |
| -4 | **Failed** | reintentar/escalar |

---

## 4. Endpoints de backend del dashboard (a crear)

| Endpoint | Método | Qué hace |
|---|---|---|
| `POST /api/accounts/{id}/withdraw` | POST | **Dispara el retiro.** Body `{amount}`. Ejecuta Pasos 1–3, devuelve `{transactionId, reference, accountId, accountDigits, amount}`. Valida JWT fresco del PASO 0. |
| `GET /api/accounts/{id}/withdraw/status/{txId}` | GET | Estado del retiro (Paso 4 + 5). Devuelve `{transactionStatus, description, lastModifiedUtc, accountDigits, gateway}`. |

**0. Validación de JWT (antes del PASO 1):** leer `accounts.jwt_token` + `jwt_expires_at`. Si expirado → abortar con "JWT expirado, requiere refresh" (no intentar retiro con JWT muerto). Reusar `load_jwt()` de `tools/bmx_call.py`.

**Seguridad/rol:** solo SA (o rol con permiso de retiro). Aplicar `_event_visible_to` / gate de rol existente. Loggear `account_touch` (SA ve toques ajenos).

---

## 5. ⚠️ Bugs críticos — guardarrails OBLIGATORIOS

### Bug #1 — El `accountId` NO garantiza el destino (cambio de cuenta por depósito)
**Causa raíz confirmada en campo:** un depósito SPEI **reescribe la cuenta de retiro** apuntando a la cuenta que recibió ese SPEI. BetMexico "retira al ÚLTIMO método de depósito usado".

**Prueba real de msaidrzz:**
- Retiro #1 → fue a **STP `0139`** (cuenta original).
- Robert mandó SPEI de $2 (a HEY BANCO) → ese depósito **reescribió** la cuenta de retiro → STP `0139` **desapareció** de `BankAccounts`, quedó solo HEY BANCO `1215`.
- Retiros #2–#5 → todos a HEY BANCO `1215`.

**Guardarrail en el botón:**
- Leer `BankAccounts` **FRESCO inmediatamente antes de cada disparo** (PASO 1), NUNCA cachear el `accountId`.
- Tomar el 1er `accountStatus:2 Approved`.
- **Si hay >1 cuenta aprobada** → NO adivinar. Alertar al operador: "hay N cuentas de retiro ({lista de institutionName+dígitos}), confirma cuál". (No se reprodujo en msaidrzz porque el SPEI de $2 dejó solo 1, pero es el caso de borde.)
- Tras el retiro, en el PASO 5, comparar `lastAccountDigits` devuelto con el `accountId` del PASO 1. Si difieren → alertar "el retiro fue a {dígitos}, no a la cuenta esperada {accountId}".

### Bug #2 — `status:6` (Successful) ≠ aterrizaje en el banco del usuario
**Causa confirmada en campo:** el retiro `dee3d6f8` ($300) marcó `status:6` en la API de BetMexico desde temprano (ejecutado del lado de ellos), pero el banco receptor lo tuvo **atorado varios minutos** antes de reflejarlo. Robert pensó que faltaba $300.

**Guardarrail en el botón:**
- El botón reporta **2 fases** claras, no 1:
  1. **"Retiro ejecutado"** (cuando `transactionStatus:6` en BetMexico) — el dinero salió de BetMexico.
  2. **"Retiro aterrizado"** — confirmación manual del operador de que vio el dinero en su banco.
- El botón NO afirma "dinero entregado" con solo `status:6`. El copy del UI: "BetMexico procesó el retiro ({ref}). Confirma en tu banco." (no "¡Listo, llegó!").
- Exponer `lastModifiedUtc` del PASO 5 para que el operador vea cuándo el rail lo procesó (un retiro reciente con `lastModifiedUtc` muy nuevo puede seguir en tránsito).

### Bug #3 — Reembolso a tarjeta entre retiros SPEI (caso de borde NO reproducido, pero real)
**Hipótesis de Robert (de la cuenta espinoza):** entre retiros SPEI, BetMexico a veces dispara un retiro como **reembolso a tarjeta** (rail `gateway:1`) "bien random", aunque el último depósito haya sido SPEI.

**NO se reprodujo en msaidrzz** (sus depósitos recientes $2 y $5 fueron SPEI, así que BetMexico no tenía tarjeta "reciente" a la que rebotar). Pero el historial de espinoza sí lo mostraba (entró $1,450 como 5×$280 + $50 con TARJETA el 22/07).

**Guardarrail en el botón:**
- En el PASO 5, verificar `gateway` del retiro disparado. Si el retiro sale con `gateway:1` (tarjeta) cuando esperábamos `gateway:2` (SPEI) → **alerta crítica**: "BetMexico mandó el retiro a TARJETA, no a SPEI. Revisar." (Esto es el bug de reembolso a tarjeta.)
- Considerar leer el historial de depósitos reciente de la cuenta antes de disparar: si el último depósito fue TARJETA, BetMexico podría redirigir el retiro a tarjeta. Avisar al operador de ese riesgo antes del disparo.

### Restricciones de concurrencia
- **2do retiro mientras el 1ro está `Pending` → 400 `THE_TRANSACTION_DOES_NOT_COMPLY_WITH_THE_ESTABLISHED_CONFIGURATION`.** El botón debe **bloquear** el botón mientras haya un retiro pendiente (polling PASO 4 = `id != null`), y reactivarse solo cuando `id:null` (completó/falló).
- No taladrar: el PASO 4 polling es a 60s, no menos (no alimentar rate-limit).

---

## 6. UI en La Pantalla (vista SA)

```
┌─ Detalles de cuenta: msaidrzz@gmail.com ──────────────────┐
│ ...cuenta de retiro: HEY BANCO ···1215 (Approved) [refrescar]│
│ ...saldo Real: $102.01 · Bonos: $0                          │
│                                                             │
│ [ Retirar ▾ ]  monto: [____]  →  [ Disparar ]               │
│                                                             │
│ Estado retiro: ⏳ Pending (ref 334760946309) · 2 min        │
│                ✓ BetMexico procesó · espera banco           │
└─────────────────────────────────────────────────────────────┘
```

- Botón "Retirar" solo para SA. Abre input de monto + "Disparar".
- Validar monto ≤ `Real` (PASO 2). Redondear a 2 decimales.
- Tras disparar: estado en vivo (polling PASO 4 → 5). Fases de §5 bug #2.
- Historial de retiros de la cuenta (de `Transactions/ByUser`, tipo 2) debajo, con `account` dígitos visibles (detectar bug #1).

## 7. Persistencia (BD)

Tabla nueva `account_withdrawals` (idempotente UNIQUE):
- `account_id`, `transaction_id` (UNIQUE), `reference`, `amount`, `account_digits` (destino), `institution_name`, `status_api` (enum BetMexico), `last_modified_utc`, `created_at`, `disparado_por` (operador).
- Cada retiro = 1 fila. Actualizar `status_api`/`last_modified_utc` conforme avanza el polling.
- Esto es la **bitácora trazable** (ley `feedback_dashboard_purpose`: ¿podrá Robert reconstruir qué pasó en 1 semana?).

## 8. Riesgos / no-go

- **NO cachear `accountId`** (bug #1). Fresh read cada disparo.
- **NO reportar "entregado" con `status:6`** (bug #2). 2 fases.
- **NO disparar con JWT expirado** (validar PASO 0).
- **NO proxyless** (ley). Loggear sin proxy = filtra IP real.
- **NO taladrar** BeginDeposit en cada refresh (rate-limit). El retiro no llama BeginDeposit.
- Archivos congelados `account_refresh.py`, `prewarm.py`, `deposits.py` **NO se tocan** (auditoría 2026-07-22, no míos). El flujo de retiro va en código nuevo.
- Bot Telegram (monorepo) **NO se toca** desde aquí (`feedback_no_monorepo`).

## 9. Verificación tras implementar

1. Smoke funcional: disparar retiro de $1 (no $100+) en cuenta de prueba para validar el flujo end-to-end sin riesgo grande.
2. Verificar los 2 bugs críticos NO ocurren: `lastAccountDigits` coincide con `accountId` (bug #1), `gateway:2` no `1` (bug #3).
3. Smoke HTTP real tras deploy (ley `feedback_verify_http_response_after_deploy`).
4. Confirmar la fila en `account_withdrawals` quedó con estado final + `last_modified_utc`.

## 10. Secuencia de implementación (próxima sesión)

1. Backend: `POST /api/accounts/{id}/withdraw` + `GET .../status/{txId}` en `app.py` (reusar helpers de `tools/bmx_call.py`: `load_jwt`, `get_proxy`, headers).
2. Tabla `account_withdrawals` (migración aditiva en `app.py`, idempotente).
3. UI en `pantalla.js`/`pantalla.css`: botón + input + estado en vivo (reusar tokens estilos del panel de clabes ya hecho).
4. Polling frontend (60s) sobre `/status/{txId}`.
5. Smoke $1 en cuenta de prueba → validar 2 fases + 3 guardarrails.
6. Deploy + smoke HTTP real.

> **Modelos por subagente** (ley `feedback_planes_orquestacion`): backend en Opus (dinero real, lógica crítica), UI en Sonnet (patrones ya establecidos), smoke/verify en Haiku (mecánico). Goals medibles: 1 retiro de $1 end-to-end con los 3 guardarrails verificados.
