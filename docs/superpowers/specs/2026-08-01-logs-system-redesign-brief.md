# Brief para Open Design — Rediseño del sistema de logs de BoTMexico

> Documento autocontenido. Pégalo completo en Open Design — no necesitas el repo abierto para que tenga sentido.

---

## 1. Qué es esto y quién lo usa

BoTMexico es un dashboard de operación (no cara al público) para gestionar cuentas, depósitos y retiros contra BetMexico. Lo opera **Robert**, dueño del sistema, **diagnosticado con TDAH** — necesita leer estado y decidir rápido, sin parsear párrafos ni escanear texto plano homogéneo.

**Función de los logs aquí:** no es un debug console de desarrollador. Es la herramienta con la que Robert **reconstruye qué pasó** (una cuenta, una misión, una semana) y **decide la siguiente acción**. Si un log no ayuda a decidir o reconstruir, sobra.

**Regla dura del proyecto (no negociable, aplica al rediseño):** nunca enmascarar información sensible. Tarjetas, combos email:password, deben quedar copiables en un click, sin ofuscar ni truncar el dato operativo.

---

## 2. Problema actual (por qué se pide el rediseño)

Cita textual de Robert sobre el estado actual: *"no quiero logs genéricos, quiero logs que me sirvan a mí"*. Se pidió: **jerarquía visual, categorización, y filtros por categoría** — ninguno de los tres existe hoy de forma completa.

### 2.1 Hallazgo de arquitectura — DOS sistemas de logs paralelos, no unificados

**Sistema A — parser de líneas de log crudas** (texto de Python `logger.info/warning/error`, se re-parsea en el frontend con regex). Reconoce solo **6 categorías** vía heurística de texto:

| Categoría | Trigger (regex, aproximado) |
|---|---|
| `deposit_ok` | status `approved`/`live` |
| `deposit_fail` | "submit rejected", "dead account", "bank_rejected", "rechazad[oa]" |
| `withdraw_ok` | logger de withdrawals + "disparado" |
| `withdraw_fail` | logger de withdrawals + nivel ERROR o "insuficiente" |
| `login_fail` | "rate-limit", "rate_limited", "login_failed", "login_denied", "429" |
| `system_error` | nivel ERROR/CRITICAL genérico |
| `refresh` | (catch-all de refresh de cuentas) |

Además existe una línea estructurada especial `[CARD_TOUCH]` (formato `key=value | key=value`) que trae: `operator`, `combo` (email:password), `account`, `pipe` (tarjeta), `amount`, `status`, `reason` — se renderiza distinto (con "chips" clicables por dato).

**Sistema B — feed de actividad estructurado** (`GET /api/activity`, eventos ya tipados en JSON, no texto). Trae **33 valores de `kind` distintos**, SIN mapeo a las 6 categorías del Sistema A:

```
account_refreshed, account_touch, auto_mission, bulk, capmonster_low,
curp_validated, deposit, deposit_step, emergency_stop, global_pause,
global_resume, lock, maintenance_toggle, note, pool_move,
prewarm_errors, proxy_down, release_available, release_available_again,
scheduled, scheduled_aborted, scheduled_cancelled, scheduled_phase,
scheduled_retry, scheduled_started, telegram_bot_bet, telegram_bot_cancel,
telegram_bot_pause, telegram_bot_resume, unlock, unlock_auto,
vps_reboot, withdrawal, withdrawal_status
```

Cada `kind` trae campos propios (no hay un shape único). Ejemplos reales tal cual los emite el backend:

```jsonc
// kind: "deposit"
{ "kind": "deposit", "ts": "...", "who": "RobertVS", "who_color": "#...", "who_id": 1341812706,
  "target": "email:password", "amount": 150.0, "status": "threeds", "reason": "3DS_REQUIRED — ...",
  "duration_ms": 2771 }

// kind: "lock"
{ "kind": "lock", "ts": "...", "who": "RobertVS", "who_color": "#...", "who_id": ...,
  "target": "email:password", "id": 1497, "locked_until": null, "auto": true }

// kind: "scheduled_aborted"  (justo el caso que motivó este brief — depósito programado que se corta)
{ "kind": "scheduled_aborted", "sched_id": "...", "email": "...", "code": "3DS_REQUIRED",
  "reason": "cuenta premium A+ (3DS)", "iter": 6, "total": 9, "ts": "..." }

// kind: "auto_mission"
{ "kind": "auto_mission", "mission_id": "...", "status": "matching" | "match" | "scheduling" | "completed" | "failed" | "cancelled",
  "ts": "...", "who": "...", "accounts": 7 }

// kind: "withdrawal"
{ "kind": "withdrawal", "ts": "...", "target": "email", "id": 1497, "amount": 500.0, "transactionId": "..." }

// kind: "capmonster_low" / "proxy_down" / "vps_reboot"  (alertas de infra, no de operación)
{ "kind": "capmonster_low", "severity": "danger", "msg": "CapMonster bajo: $3.20", "ts": "..." }

// kind: "telegram_bot_bet"
{ "kind": "telegram_bot_bet", "ts": "...", "mission_id": "...", "card_count": 3 }

// kind: "note"
{ "kind": "note", "ts": "...", "who": "...", "target": "email:password", "text": "..." }
```

**Por qué esto importa para el rediseño:** cualquier sistema de categorías/colores/filtros tiene que decidir sobre ESTOS 33 `kind` (más los 6 del sistema A, más `[CARD_TOUCH]`) como universo real — no inventar categorías nuevas que no mapeen a datos que existen.

### 2.2 Otros problemas de UX ya identificados
- **Sin jerarquía visual real**: todo el texto pesa casi igual (una sola familia mono, tamaño uniforme). Un evento crítico (`emergency_stop`, `proxy_down`) se ve casi igual que uno informativo (`account_refreshed`).
- **Sin filtros por categoría**: hoy se puede filtrar por operador (`operator_id`) pero no por tipo de evento. Para "reconstruir qué pasó con una cuenta en una semana" (uno de los propósitos centrales del dashboard, ver §4) hoy hay que leer todo el feed.
- **Regla del proyecto que ya se sigue y debe mantenerse**: un badge/estado solo se muestra si es una EXCEPCIÓN accionable — el estado default (todo bien) NO se anuncia, su ausencia ya lo dice. No llenar la UI de badges "ok" que no aportan.

---

## 3. Sistema visual existente (Obsidian Refined) — no partir de cero

El dashboard ya tiene un design system maduro. El rediseño de logs debe **vivir dentro de este sistema**, no inventar una paleta nueva.

**Personalidad:** superficies oscuras glass-morphism, acento verde-teal esparso (NO decorativo en todo, solo en acción), ámbar = dinero/aviso, rojo = solo peligro real.

### Tokens de color (ya definidos, usar estos, no hex sueltos)
```css
--bg: #08090c;                                   /* fondo base */
--surface: rgba(18,20,24,0.60);                  /* superficie con blur */
--text: #eef0f3;  --text-dim: rgba(238,240,243,.72);
--text-muted: rgba(238,240,243,.52);  --text-faint: rgba(238,240,243,.28);
--hairline: rgba(255,255,255,.12);

--accent: oklch(0.50 0.11 160);        /* verde teal — acción/éxito */
--danger: oklch(0.66 0.21 24);         /* rojo — error real */
--warn:   oklch(0.80 0.16 75);         /* ámbar — aviso, 3DS, cooldown */
--gold:   oklch(0.82 0.14 85);         /* dinero, saldo, retiros */
--purple: oklch(0.74 0.17 295);        /* locks, cooldowns, operadores */

/* colores por operador (multi-operador, ya existen 4) */
--op-warn, --op-purple, --op-accent, --op-azure

/* colores por grado de cuenta (A+ a D), reutilizables como referencia de severidad */
A+ oklch(0.75 0.20 152)  A oklch(0.58 0.13 160)  B oklch(0.70 0.16 235)
C oklch(0.80 0.16 75)    D oklch(0.66 0.21 24)   U rgba(255,255,255,.14)
```

### Tipografía
```css
--font: 'Inter';                    /* body */
--font-display: 'Space Grotesk';    /* headings, labels, nav */
--font-mono: 'JetBrains Mono';      /* DATOS, timestamps, códigos — los logs YA usan mono */
```
Escala: 9/10/11/12/13/14/16/18/22/28px. Base body 13px.

### Clases ya implementadas (para no duplicar, y como referencia de "qué tan lejos llega hoy")
```css
.log-line, .log-err, .log-warn, .log-info, .log-debug   /* nivel */
.log-cat-deposit_ok, .log-cat-deposit_fail, .log-cat-withdraw_ok,
.log-cat-withdraw_fail, .log-cat-login_fail, .log-cat-system_error,
.log-cat-refresh                                          /* las 6 categorías del sistema A */
.log-chip, .log-line.log-card-touch                        /* chips clicables (operador/combo/tarjeta/monto) */
```

Archivos fuente de verdad: `static/style.css` (logs viven ~línea 2000-2100), `static/app.js` (parseo/categorización ~línea 2380-2470 y render ~línea 4800+), `docs/DESIGN-SYSTEM.md` del repo (documento completo de tokens).

---

## 4. Qué debe lograr el rediseño (criterio de éxito)

El dashboard existe para **trackear + controlar + monitorear + guardar**. Test de aceptación real: *¿puede Robert reconstruir qué pasó en una cuenta/operador/semana con este feed, sin tener que leer todo?* Si no, no está completo.

Con eso como norte:
1. **Unificar** — un solo modelo de "evento de log" que cubra los 33 `kind` + las 6 categorías heurísticas + `[CARD_TOUCH]`, no dos sistemas paralelos.
2. **Jerarquía visual real** — un evento `emergency_stop`/`proxy_down`/`capmonster_low` (infra crítica) debe pesar visualmente distinto a `account_refreshed` (rutina). Tamaño, peso, color, posición — no todo mono-13px-uniforme.
3. **Categorización agrupable** — agrupar los 33 `kind` en un número MENOR de macro-categorías con las que Robert realmente piensa (propuestas, no cerradas): *Dinero* (deposit, withdrawal, scheduled*, auto_mission), *Cuentas* (lock, unlock, note, account_touch, account_refreshed), *Bot Telegram* (telegram_bot_*), *Sistema/Infra* (capmonster_low, proxy_down, vps_reboot, emergency_stop, global_pause/resume), *Operación manual* (bulk, maintenance_toggle, curp_validated, pool_move).
4. **Filtros por categoría** — poder aislar "solo Dinero" o "solo Sistema/Infra" del feed, además del filtro por operador que ya existe.
5. **Sistema de decisión interactivo** (esto es lo que Open Design debe CONSTRUIR, no solo diseñar en estático): una pantalla/paso donde Robert vea las macro-categorías + los 33 `kind` reales + variables disponibles por evento, con swatches de color por categoría, y pueda **elegir** — qué categorías existen, qué color le corresponde a cada una, qué campos se muestran por defecto vs. bajo click/expand. El resultado de esa elección es el INPUT del rediseño final del feed — no un mockup fijo que Robert tiene que aceptar tal cual.

---

## 5. Restricciones duras (no violar)

- **No enmascarar datos sensibles.** Combos, tarjetas, montos: siempre visibles y copiables en 1 click. Esto es una regla de producto, no un descuido.
- **No agregar badges/estado para el caso "todo bien".** Badge solo si es una excepción que requiere que Robert actúe o se entere.
- **No quitar información al compactar.** Si algo se ve amontonado, la solución es jerarquizar/espaciar — no eliminar un campo porque "ya no cabe".
- **Frictionless ante todo**: cada decisión de diseño se mide contra "¿esto le quita o le agrega fricción a Robert operando en vivo, con TDAH, bajo presión de tiempo real?".
- **Vocabulario**: es un panel de operador técnico (no cliente final). Terminología cruda/operativa está bien — "3DS", "rate-limit", "JWT muerto" no necesitan traducirse a lenguaje "amigable".
- **Debe funcionar en tiempo real** — el feed hoy es streaming (SSE), no una tabla estática que se recarga. El rediseño debe asumir que llegan eventos nuevos constantemente y no debe generar layout-shift violento en cada uno.

---

## 6. Entregable esperado y stack de destino

El resultado de Open Design se va a **traducir a código a mano** en este repo (no hay pipeline de import automático). Stack real de destino:
- **Sin framework** — HTML/CSS/JS vanilla. Nada de React/Vue en la salida esperable de traducir.
- Los tokens de color/tipografía deben mapear 1:1 a los CSS custom properties de §3 (o proponer adiciones ahí, no un sistema de color paralelo).
- El feed se renderiza hoy vía funciones JS puras que devuelven strings de HTML (`_renderLogLine`, `_renderCardTouchLine` en `static/app.js`) — un diseño implementable como plantillas/componentes simples es más fácil de portar que algo que depende de un framework de componentes.

Con esto Robert debería poder ir a Open Design, pegar este documento, iterar la pantalla de decisión + el feed rediseñado, y traer de vuelta algo que se pueda implementar directo sobre `static/app.js` + `static/style.css` sin tener que re-investigar el sistema desde cero.
