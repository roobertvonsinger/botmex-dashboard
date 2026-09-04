# 04 — Flujo Auto-deposit & Motor de Depósitos

> **Ubicación:** `deposits.py`, `auto_deposit.py`, `web_grading.py`, `shared/betmexico_payment_analyzer.py`.
> **Canvas Detallado:** [[04 — Flujo Auto-deposit.canvas]]
> **Modelo Mental:** [[09 — Arquitectura de Grafo de Agentes (Cocina)]] (Estaciones de preparación, línea de fuego, auditor de sabor y auto-healing).

---

## 🍳 Ficha Técnica y Estaciones del Grafo

### 1. Estación de Ruteo e Ingesta (Maitre d')
- **Inicia el flujo:** Petición POST `/execute-stream` (single), `/multi/stream` (batch de hasta 5 cuentas × 5 tarjetas) o `/scheduled/create` (programado con prefetch de captcha).
- **Entrada:** Lote de tarjetas en formato pipe (`PAN|MM|YY|CVV`) o trigger de operador.
- **Acción:** Asigna `mission_id`, inicializa contadores y emite evento SSE `mission_started`.

### 2. Estación de Matchmaking (Prep Station)
- **Función:** `select_accounts_for_auto`
- **Cuotas de Calidad:** Tier 40% Grado A / 40% Grado B / 20% Grado C para distribuir carga y rotar cuentas sanas.
- **Filtros Exclusivos:**
  - Descarte de cuentas `DEAD` o en `rate_limited_cooldown` (429/406).
  - Anti-Mezcla: Si una cuenta tiene saldo $\ge \$100$ fondeado en las últimas 24h, PROHIBIDA una tarjeta diferente.
  - Tarjeta Casada: La misma tarjeta casada SÍ puede volver a fondear la misma cuenta hasta el tope 24h de $1,499.
- **Tie-Break Eficiente:** Dentro del tier LOW, preferir cuentas con JWT activo para evitar captchas y logins costosos.
- **Piso Anti-Huella:** Delay aleatorio de 45-60s con estado `preparing` para disimular ráfagas ante la pasarela.

### 3. Estación de Fuego y Ejecución (Line Cook)
- **Función:** `_run_deposit_with_phases` en `deposits.py`.
- **Egress Residencial:** Ejecución envuelta en `call_with_proxy_failover` (conmuta en <1s si el proxy arroja 402 o timeout).
- **Captcha Pool:** Prefetch de tokens reCAPTCHA v2 (tiempo de vida máximo de 55s; refresco proactivo).
- **Llamadas Gateway:** `BeginDeposit` → `makePayment` → `verifyPayment`.

### 4. Estación de Auditoría y Calidad (Taste Tester)
- **Función:** `classify_deposit_status` apoyada por el Algoritmo V10.
- **Inspección de Respuesta:** Evalúa headers, códigos de error bancario y transacciones acreditadas.

### 5. Estaciones de Recuperación Local (Self-Healing — "Burned Potatoes")
Aquí reside la solidez del sistema: **un fallo en una tarjeta o red jamás mata la cuenta**.

| Estado Detectado | Significado | Acción de Recuperación (Auto-Healing) |
|---|---|---|
| **✅ APPROVED** | Depósito exitoso y acreditado | Casa la tarjeta (`is_married=1`), actualiza saldo en SQLite WAL, emite SSE y genera ficha SPEI in-bot. |
| **⚠️ BANK_REJECTED** | El banco emisor declinó | **Papa quemada:** Se jubila la tarjeta (`burned`). La cuenta de BetMexico permanece limpia y lista para la siguiente tarjeta. |
| **🛑 CARD_LOCKED** | Tarjeta ligada a otra cuenta | Jubilación inmediata de la tarjeta sin reintentos para no quemar el pool. |
| **🔄 TRANSITORIO** | Timeout de red o HTTP 5xx | Reintentos controlados (hasta `MATCH_TRANSIENT_RETRIES = 4`) con jitter de 25s. |
| **⏳ 429 / 406** | Rate limit o Captcha denso | **NO matar a DEAD.** Se asigna cooldown de 24h (`rate_limited_cooldown`) y entra en reposo. |

---

## 📡 Telemetría y Controles de Operador
- **Progreso Visual SSE:** Incrementos no lineales (25% → 40% → 55% → 70% → 85% → 95% → 100%).
- **Botón de Emergencia:** Flag `_stop_requested` que cancela la misión en curso de forma ordenada, liberando bloqueos de cuentas en SQLite.
