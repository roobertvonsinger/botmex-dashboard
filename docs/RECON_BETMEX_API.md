# RECON — API de BetMexico (mapeo del frontend)

> Reverse engineering autorizado (testing propio). Generado 2026-07-22, actualizado 2026-07-24.
> Fuente: bundle SPA Vue `bmx-prod-v26.7.47` (build más nuevo que el v26.5.25 documentado en `docs/ERRORS.md`).

## ⚠️ Separación QUIRÚRGICA: Depósitos vs Retiros (no confundir)

**Dos families de endpoints distintos. NUNCA mezclar.** Confundirlos ya costó sesiones.

### DEPÓSITOS (el usuario envía dinero A BetMexico)
| Endpoint | Qué hace |
|---|---|
| `POST /api/wallet/deposit/BeginDepositWithCard` | Tarjeta (lo que USA el bot). body `{amount, theme:1}` → processorpay |
| `POST /api/stp/BeginDeposit` | SPEI MX. **SIN body** → `{reference, userId, accounts:[{account, blocked, order, integration}]}`. Devuelve las CLABES de depósito (NVIO order 1 + STP order 3). |
| `POST /api/BankTransfer/BeginDeposit` | SPEI canónico con body `{...e}` |
| `POST /api/DigitalWallet/BeginDeposit` | Wallet digital |
| `GET /api/stp/...` status | Estado del depósito |

> **Las clabes que devuelve `BeginDeposit` son las CUENTAS DONDE EL USUARIO DEPOSITA** (NVIO/STP). Son internas de BetMexico. NO son la cuenta de retiro del usuario.

### RETIROS (BetMexico envía dinero AL usuario)
| Endpoint | Qué hace |
|---|---|
| `POST /api/stp/BeginWithdrawal` | Retiro SPEI MX (body `e`). Rail principal. |
| `POST /api/card/beginwithdrawal` | Retiro a TARJETA (body `e`) |
| `POST /api/bankTransfer/beginWithdrawal` | Retiro bank transfer (body `e`) |
| `POST /api/pix/BeginWithdrawal` | Retiro Pix (Brasil) |
| `POST /api/DigitalWallet/BeginWithdrawal` | Retiro wallet digital |
| `GET /api/User/PendingWithdrawal` / `/api/wallet/PendingWithdrawal` | Retiro pendiente actual → `{reference, transactionStatus}` |
| `GET /api/user/LastWithdrawalDetail` | Detalle último retiro |
| `POST /api/Card/CardTransactionStatus` | Estado transacción tarjeta |

> **La cuenta de retiro** del usuario se lee con `GET /api/User/BankAccounts` (MX) y va en el body `e` del `BeginWithdrawal` (`accountId`, `account`=clabe del usuario, `institutionName`, `bankName`). **BetMexico retira al ÚLTIMO método de depósito usado** (si depositó con tarjeta → retira a tarjeta; un depósito SPEI rellena la cuenta de retiro en automático).

### Regla de oro
`BeginDeposit` = entra dinero a BetMexico + devuelve clabes internas. `BeginWithdrawal` = sale dinero de BetMexico + usa la clabe/cuenta del USUARIO. **Mismo verbo `Begin`, familias opuestas.** El `priority-provider: [3,1]` del `payments-maintenance.json` se refiere a **proveedores SPEI backend** (orden de intento), NO a cuentas internas de depósito ni a métodos de retiro — es backend, no está en el JS (no-determinado).

## Método
betmexico.mx es **SPA Vue** (rolldown/Vite). WebFetch NO sirve (renderiza con JS). Flujo verificado:
1. `curl` crudo del HTML → sacar `<script src>` del bundle principal (`/assets/index-*.js`)
2. `grep` de refs a otros chunks (`*.js`) en el bundle principal
3. Descargar chunks de **negocio** (filtrar por nombre: deposit/wallet/spei/session/auth/user)
4. `grep` de strings `/api/...` en los chunks → los endpoints viven como strings literales

```bash
curl -sL -A "Mozilla/5.0 Chrome/136.0" https://betmexico.mx/login -o login.html
# en el HTML: <script type="module" crossorigin src="/assets/index-CpvDmhjM.js"></script>
curl -sL https://betmexico.mx/assets/index-CpvDmhjM.js -o index.js
grep -oE '[a-zA-Z0-9_-]+-[A-Za-z0-9_-]{6,}\.js' index.js | sort -u \
  | grep -iE 'deposit|wallet|spei|payment|session|auth|verify|user|kyc' | ...
# en cada chunk: grep -ohE '/api/[A-Za-z0-9/_-]+'
```

## ★ Gate /verify-email — RESUELTO (API, no solo web)

Hay **2 flujos** de verificación por correo, extraídos de `useAuth-DgRnafzv.js` + `EmailPinView`:

### A) Link (VerifyEmailLink / `VerificationViaEmailView`)
```
POST /api/EmailVerification/SendVerificationEmail   body: {userId, email}   # manda link al correo
POST /api/EmailVerification/VerifyEmail              body: {token}            # valida, devuelve JWT fresco
```
Tras validar `VerifyEmail`, el backend devuelve `{userId, username, fullName, email, token, refreshToken}` → **emite JWT fresco, la cuenta sale de la cuarentena vía API pura**.

### B) PIN (VerifyEmailPin / `EmailPinView`) — el que pega a cuentas rate-limitadas
```
POST /api/Users/Send/PIN/                # envía PIN al correo
POST /api/Users/SendReattempt/PIN/       # reenvío
POST /api/Users/Validate/PIN/            # valida el PIN
GET  /api/Users/Validate/HasFullValidation  # KYC
```
- Error `USER_VALIDATION_EXPIRED_PIN` → "El código ingresado ha caducado"
- Contador `pin-retry-attempts:<username>` en localStorage
- Constante `406` en el chunk = HTTP 406 = PIN inválido/expirado (mismo status que FAILURE_IN_CAPTCHA)

**Implicación msaidrzz:** la cuarentena por rate-limit la manda al flujo de PIN. El navegador no deja salir porque hay que ingresar el PIN. **Vía API**: `/api/Users/Send/PIN/` manda el código al correo, `/api/Users/Validate/PIN/` lo valida → JWT fresco. Accionable sin navegador si hay acceso al correo.

## ★ Retiros vía API (withdrawal)

Mapeado del bundle `bmx-prod-v26.7.47` (chunk `useAuth-C0Juh89W.js`). Existen **5 vías** de `BeginWithdrawal` (una por rail de pago), más endpoints de estado. Todas son `POST` y reciben un **body `e`** construido en la vista de retiro; el store `useWithdrawalOptionsStore` revela los campos del body.

### Vías BeginWithdrawal (POST, body `e`)
| Endpoint | Rail | Notas |
|---|---|---|
| `POST /api/stp/BeginWithdrawal` | SPEI MX | **Análogo al `stp/BeginDeposit`**. Rail principal MX. |
| `POST /api/card/beginwithdrawal` | Tarjeta | Retiro a tarjeta |
| `POST /api/bankTransfer/beginWithdrawal` | Bank transfer canónico | |
| `POST /api/pix/BeginWithdrawal` | Pix (Brasil) | |
| `POST /api/DigitalWallet/BeginWithdrawal` | Wallet digital | |

### Body `e` (del store `useWithdrawalOptionsStore`)
Campos que el frontend ensambla antes del POST (objeto `formWithdrawal` + `selectedAccount`):
- `accountId`, `account` (la clabe), `institutionName`, `bankName` — vienen de la cuenta bancaria elegida (`getDefaultBankAccount()`).
- `methodType` (enum: `0=None,1=Cpf,2=Cnpj,3=Phone,4=Email,5=RandomKey` — estos son para Pix/Brasil; MX usa la clabe del `account`).
- `methodValue`, `transactionId`, `actionTypeRequest` (`0=None,1=AddAccount,2=DeleteAccount,3=UpdateAccount`).
- `amount` — implícito del formulario de la vista (no está como campo del store, se captura en UI).

### Estado / consulta de retiros
| Endpoint | Método | Uso |
|---|---|---|
| `GET /api/User/PendingWithdrawal` | GET | Retiro pendiente actual. Flag `Ie` elige este vs `/api/wallet/PendingWithdrawal`. **Retorna `{reference, transactionStatus, ...}`**. |
| `GET /api/wallet/PendingWithdrawal` | GET | Variante (según tenant/flag `Ie`). |
| `GET /api/user/LastWithdrawalDetail` | GET | Detalle del último retiro. |
| `GET /api/WalletTransactionExternal/TransactionStatus?${queryString}` | GET | Estado de transacción externa (recibe query string). |
| `POST /api/Card/CardTransactionStatus` | POST | Estado de transacción tarjeta. |
| `POST /api/Yape/YapeTransactionStatus` | POST body `{transactionId}` | Estado Yape (Perú). |

### Enum `transactionStatus` (de `LoginBlockedWithdrawal`)
`PendingVerification:-1, PendingApproval:1, Pending:2`. La vista `LoginBlockedWithdrawal` (cuenta bloqueada autoexcluida) llama a `PendingWithdrawal` (alias `S`/`mu`) — NO inicia retiro, solo consulta el pendiente y ofrece "Retirar mi dinero" si hay saldo real.

### Flujos colaterales del retiro
- Logout forzado por bloqueo: `POST /api/Session/close/` con `method:"logout_blocked_withdrawal"`.
- `request-withdrawal`, `/withdrawalWindow` = rutas SPA (no endpoints).
- `withdrawal-reminder-last-shown` en localStorage controla el recordatorio modal.

## ★ payments-maintenance.json (flags.betmexico.mx)

`GET https://flags.betmexico.mx/payments/payments-maintenance.json` — JSON plano (sin auth), `Cache-Control: max-age=60`, CloudFront. Es el panel de feature-flags de pagos. Estructura (3 bloques):

### `automaticWithdrawal`
```json
"automaticWithdrawal": { "spei": true }
```
**Retiros SPEI automáticos habilitados.** `true` = el sistema procesa retiros SPEI sin revisión manual (lo suelta al banco/stp directo). Si fuera `false`, los retiros SPEI quedarían en `Pending` esperando aprobación manual de un operador BetMexico.

### `inMaintenance` (matriz por rail × fase)
Cada rail de SPEI tiene 3 fases: `-payments` (depósitos), `-withdraws` (retiros), `-changestatus` (cambio de estado). Valor `true` = EN MANTENIMIENTO (ese rail/fase caído).
```json
"inMaintenance": {
  "card": false,                          // tarjeta ok
  "spei": false,                          // spei genérico ok
  "conekta": false,
  "cash-conekta-deposits": false,
  "cash-conekta-withdrawals": false,
  "spei-sqs-payments": false,             // rail SQS (cola)
  "spei-sqs-withdraws": false,
  "spei-sqs-changestatus": false,
  "spei-stp-payments": false,             // rail STP (banco STP) — el principal
  "spei-stp-withdraws": false,
  "spei-stp-changestatus": false,
  "spei-bitso-payments": false,           // rail Bitso
  "spei-bitso-withdraws": false,
  "spei-bitso-changestatus": false,
  "spei-afirme-payments": true,           // ⚠ rail Afirme CAÍDO
  "spei-afirme-withdraws": true,          // ⚠ retiros Afirme caídos
  "spei-afirme-changestatus": true        // ⚠ change-status Afirme caído
}
```
**Hallazgo:** BetMexico tiene **3 proveedores SPEI backend** (STP, Bitso, Afirme) + 1 cola (SQS). STP y Bitso OK; **Afirme en mantenimiento total** (depósitos+retiros+changestatus). El `priority-provider: [3,1]` (ver abajo) define cuál se intenta primero.

### `spei.priority-provider`
```json
"spei": { "priority-provider": [3, 1] }
```
**Orden de preferencia de proveedores SPEI.** `[3, 1]` = intentar primero el proveedor con `order` 3, luego el `order` 1.
- Recordar: en `stp/BeginDeposit`, cada clabe trae `order` (NVIO=1, STP=3). El `order` identifica al proveedor/integración.
- `[3, 1]` → prefiere el proveedor 3 (STP, según el orden del BeginDeposit) y cae al 1 (NVIO) si el 3 falla o está en mantenimiento.
- Por eso Afirme puede estar caído sin afectar: el `priority-provider` enruta a STP primero, que está sano.

### `paymentsApiRefactor`
```json
"paymentsApiRefactor": {
  "paymentsApiDepositNotificationUrl": "https://paymentsapi.betmexico.mx/api/Stp/DepositNotification",
  "paymentsApiRejectedDepositNotificationUrl": "https://paymentsapi.betmexico.mx/api/Stp/NotifyDepositRejected",
  "isPaymentsApiEnabled": true
}
```
Webhooks internos de BetMexico: el banco (STP) notifica depósitos a `/api/Stp/DepositNotification` y rechazos a `/api/Stp/NotifyDepositRejected`. `isPaymentsApiEnabled:true` = refactor de payments activo (no legacy). No accionables para nosotros (son callbacks server-to-server del banco), pero confirman que el flujo SPEI es STP→paymentsapi.

## ★ BankAccounts — esquema completo

### Lectura (GET)
```js
// función su() en useAuth — elige por tenant/país:
x (Pix/Brasil) → GET /api/wallet/BankAccounts/PixBankAccounts
S (Alt)        → GET /api/wallet/BankAccounts/
default (MX)   → GET /api/User/BankAccounts          ← MX
```
- Flag `Ie` (tenant) decide entre `/api/User/...` y `/api/wallet/...` para `PendingWithdrawal` también.

### Response shape (de `useBankAccounts`)
```json
{
  "accounts": [
    {
      "accountId": <id>,
      "account": "<la clabe de 18 dígitos>",
      "institutionName": "<banco>",
      "accountStatus": 2,          // enum: 0=CREATED, 1=PENDING, 2=APPROVED
      ...otros campos del banco
    }
  ],
  "<bankDataProvider campos>"
}
```
- `useBankAccounts` expone: `countAccounts`, `isBankAccountApproved` (`accounts[0].accountStatus === APPROVED`), `getDefaultBankAccount` (`accounts[0]`).
- **Para retirar, la cuenta bancaria debe estar `APPROVED` (status 2).** Si está `PENDING`/`CREATED`, el retiro no procede.
- `getDefaultBankAccount()` = siempre `accounts[0]` (BetMexico opera con la primera clabe aprobada como destino de retiro).

### Mutación (POST/PUT/PATCH)
| Endpoint | Método | Uso |
|---|---|---|
| `POST /api/wallet/BankAccounts` | POST body `{...e}` | Alta de cuenta bancaria (MX/Alt) |
| `PUT /api/wallet/BankAccounts` | PUT body `e` | Edición |
| `PATCH /api/wallet/BankAccounts/${id}` | PATCH body `t` | Editar por id |
| `POST /api/wallet/BankAccounts/PixBankAccounts` | POST | Alta Pix |
| `PUT /api/wallet/BankAccounts/PixBankAccounts` | PUT | Edición Pix |
| `PATCH /api/wallet/BankAccounts/PixBankAccounts/${id}` | PATCH | Editar Pix por id |

> **Nota operacional:** las clabes que ya capturamos de `stp/BeginDeposit` (`accounts[].account` con `integration` NVIO/STP) **son las mismas** que devuelve `GET /api/User/BankAccounts` — son las cuentas bancarias registradas/aprobadas del usuario. `BeginDeposit` las muestra para que el usuario deposite; `BankAccounts` es el CRUD de las mismas. El `accountId` de aquí es el que va en el body de `BeginWithdrawal`.

## ★ Clabes SPEI — 3 endpoints de depósito bancario
```
POST /api/stp/BeginDeposit           (sin body)        → {reference, userId, accounts:[{account, blocked, order, integration}]}  # NVIO(order 1) + STP(order 3)
POST /api/BankTransfer/BeginDeposit  body:{...}        # canónico, manda datos de depósito
POST /api/DigitalWallet/BeginDeposit                   # otro flujo
GET  /api/DigitalWallet/AvailableWallets/
```

### Clabes (cuentas bancarias del usuario) — la función `su()` elige por tenant/país
```
MX   → GET /api/User/BankAccounts
Alt  → GET /api/wallet/BankAccounts/
Pix  → GET /api/wallet/BankAccounts/PixBankAccounts   (Brasil)
Mutación → POST/PUT/PATCH /api/wallet/BankAccounts
```

## Mapa completo de endpoints (dedupe del frontend)

### Pagos / depósitos
| Endpoint | Uso |
|---|---|
| `POST /api/wallet/deposit/BeginDepositWithCard` | Tarjeta (lo que USA el bot). body `{amount, theme:1}` → processorpay |
| `GET /api/wallet/bankTransaction/{id}` | Estado transacción tarjeta |
| `POST /api/stp/BeginDeposit` | SPEI (sin body) |
| `POST /api/BankTransfer/BeginDeposit` | SPEI canónico (con body) |
| `POST /api/DigitalWallet/BeginDeposit` / `BeginWithdrawal` | Digital wallet |
| `GET /api/user/LastDepositDetail` / `LastWithdrawalDetail` | Último depósito/retiro |
| `GET /api/Wallet/Total/Amount/ByAccountType` | Balance (lo que USA el bot) |
| `GET /api/Wallet/Transactions/ByUser` | Movimientos |
| `GET /api/User/BankAccounts` / `/api/wallet/BankAccounts/` | Clabes |
| `GET /api/card/beginDeposit` · `GET /api/Card/CardTransactionStatus` | Tarjeta |
| `/api/wallet/OxxoPay/IsValidDepositWithOxxoPay` · `/api/wallet/oxxopay/BeginDepositWithOxxoPay` | Oxxo |
| `/api/pix/*` · `/api/yape/*` · `/api/pagoefectivo/beginDeposit` · `/api/tupay/beginDeposit` | Otros países |

### Sesión / usuario
| Endpoint | Uso |
|---|---|
| `POST /api/Session/login/` | Login. body `{username, password, extendedSession, tokenCaptcha:{token, captchaVersion:"v2"}}` |
| `GET /api/Session/check` | Valida sesión |
| `POST /api/Session/RefreshToken/` | Refresca JWT |
| `POST /api/Session/close/` | Logout |
| `POST /api/Session/ssoLogin` / `/api/Users/ssoRegister` | SSO |
| `GET /api/Users/UserInfo` / `GET /api/Users/` | Perfil |
| `GET /api/Users/Validate/HasFullValidation` | KYC (lo USA el bot) |
| `GET /api/Users/Validate/HasFirstDeposit` / `AccountValidation` / `PIN/` | Validaciones |
| `/api/Users/Send/PIN/` · `/api/Users/SendReattempt/PIN/` | PIN por correo |
| `/api/Users/Update/PasswordByVendor/*` | Cambio pass vendor |
| `/api/Users/ReleaseUser` · `/api/Users/ReactiveAccountDesenrola` | Reactivar cuenta |
| `/api/Users/DeleteUser` | Borrar |
| `GET /api/UserDocument/GetStatusFiles` (lo USA el bot) · `/api/UserDocument/AddressRequired` | Documentos KYC |

### Antifraude / verificación
| Endpoint | Uso |
|---|---|
| `/api/UserVerification/GetVendorWindow` | Ventana de verificación |
| `/api/UserVerification/IsInVendorProcessVerification` | ¿En proceso? |
| `/api/UserVerification/ValidateLinkVerification` | Validar link |
| `/api/MaintenanceMessage/GetActiveMessage` | Mensaje de mantenimiento |
| `/api/ResponsibleGame/Break` · `/Exclusion` | Autoexclusión |
| `/api/Geography/{Cities,States,Regions,Nations}` | Geo |

## Infra (subdominios)
- `betmexico.mx` — frontend SPA + API sesión/usuario
- `paymentsapi.betmexico.mx` — backend de pagos (wallet/deposit/stp). **El bot apunta aquí** para wallet/deposit/transactions
- `processorpay.com/sanval/api/IframeGames/makePayment` — pasarela de tarjeta
- `casino-cdn`, `sportsbook`, `feedgate`, `betby`, `flags.betmexico.mx`

## SpeiMaintenance = SOLO banner UI
`useSpeiMaintenance-DrFwYNkl.js` expone flags `isStpDepositMaintenance`/`isBitsoDepositMaintenance`/`isSpeiDepositMaintenance` (vía `fetchPaymentsFlagsIfNeeded`). Solo muestra banner "una cuenta SPEI en mantenimiento". No es lógica de clabes.

## Pendientes (requieren login fresco desde VPS)
1. **Login fresco de diagnóstico msaidrzz** — ver si `/api/Session/login` devuelve el gate de PIN/verify-email o login normal. Toca el semáforo → decisión de Robert.
2. **Clabes reales msaidrzz** — `GET /api/User/BankAccounts` con su JWT fresco.
3. **Probar liberación de cuarentena** — `/api/Users/Validate/PIN/` con el código leído del correo.

## ★★ OBJETIVO OPERATIVO ACTIVO (2026-07-24) — retiro en cuenta cuarentenada

**El objetivo que NO se debe diluir:** Lograr un retiro en la cuenta que está con la pantalla en `/verify-email` (cuarentena rate-limit) y que **tiene dinero real** (depositamos desde el dashboard).

- **Cuenta sana de referencia (para mapear el flujo con datos reales):** `espinoza.arellano.alberto.205@gmail.com:ALBERTOcr7` (id BD 1497, userId `28f2d949-9617-4523-b289-5f55aaaa2911`, balance $1,300, KYC ok).
- **Cuenta cuarentenada con dinero:** `msaidrzz@gmail.com:Mm2025srz21` (id 637, balance $1,450.01 REAL, atorada en `/verify-email`).
- **Estado de la sesión viva (espinoza):** JWT en `localStorage["bet4:token"]`, válido hasta 2026-07-31, status `Active`. Claims .NET: `emailaddress`=email, `name`=username, `sid`=userId. **Sesión logueada viva en Chrome con CDP** (puerto 9222). Tab confirmado en `/casino/slots`.
- **Dato de calleo confirmado:** las llamadas API reales van a `paymentsapi.betmexico.mx` (wallet/user/BankAccounts/withdrawal) y a `betmexico.mx/api/` (Session/Users/Giveaway). `betmexico.mx/api/Users/UserInfo` NO existe ahí (sirve SPA fallback HTML) — usar `paymentsapi`.

### Calleo pendiente (siguiente sesión, con capturador CDP escuchando)
Con la sesión espinoza viva y el capturador `tools/cdp_capture.py` corriendo (CDP puerto 9222), navegar el tab a:
1. `/withdrawal` → captura `GET /api/User/BankAccounts` (o `paymentsapi`) → schema real de las clabes/cuentas de retiro de espinoza + `accountStatus` (debe ser APPROVED=2).
2. `GET /api/User/PendingWithdrawal` / `paymentsapi.betmexico.mx/api/wallet/PendingWithdrawal` → si hay retiro pendiente.
3. `GET /api/user/LastWithdrawalDetail` → historial de retiros (espinoza tiene los casos de bug de prioridad tarjeta-vs-cuenta).
4. Si Robert dispara un retiro real → capturar el body `e` de `POST /api/stp/BeginWithdrawal` o `/api/card/beginwithdrawal` + la respuesta `{reference, transactionStatus}`.
5. **Medir el cambio de prioridad:** tras enviar un SPEI a la cuenta (BeginDeposit), ver si el siguiente retiro cambia a cuenta bancaria instantáneo o hay delay (bug de BetMexico: a veces sale a tarjeta, a veces 2-3 a cuenta y de repente uno a tarjeta).

### Método de captura — CANONICAL = CDP (NO requiere MCP ni reiniciar sesión)
`tools/cdp_capture.py` (o `~/.agents/skills/rgate-investigate/scripts/cdp_capture.py`, versión robusta) se conecta a `ws://localhost:9222`, habilita `Network.enable`, captura todas las requests `/api/` + betmexico con **bodies, postData, timestamps ISO** a `tools/captured.jsonl`. Chrome arrancado con `--remote-debugging-port=9222 --user-data-dir=<perfil>`. Robert navega/loguea, el script atrapa el tráfico en vivo (mismo origen → sin CORS, el JWT viaja en el header del interceptor axios). Ver skill `rgate-investigate` (método CDP canonical, HAR como fallback).

Ver `memory/reference_betmex_api_endpoints_frontend.md`, `memory/project_verify_email_cuarentena_betmexico.md`, `memory/project_clabes_spei_begin_deposit.md`.
