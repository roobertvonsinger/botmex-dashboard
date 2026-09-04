# 07 — Retiros, Reconciliación y Ficha SPEI

> **Ubicación:** `withdrawals.py`, `clabe_fetch.py`, `renapo_validator.py`.
> **Canvas Detallado:** [[07 — Retiros y Reconciliación.canvas]]
> **Modelo Mental:** [[09 — Arquitectura de Grafo de Agentes (Cocina)]] (Estación de Emplatado Final y Caja de Cobro).

---

## 💸 Ficha Técnica y Flujo de Dispersión

### 1. Detección y Trigger de Retiro
- Se activa cuando una cuenta alcanza balance acreditable > \$0 sin bloqueos de seguridad activos.
- **Triggers:** Disparo manual desde el portal web (`Retirar`), botón en Telegram o liquidación programada.
- Aplica bloqueo atómico `auto_lock_for_deposit` para prevenir condiciones de carrera con depósitos concurrentes.

### 2. Ejecución y Validación Bancaria (`execute_withdrawal`)
- Verifica que la **CLABE interbancaria** corresponda a STP (Sistema de Transferencias y Pagos) y que la **CURP** coincida con el titular.
- Persiste el nombre exacto de la institución bancaria devuelto por la pasarela de BetMexico.
- Refresca el balance inmediatamente tras la solicitud reutilizando el token JWT de la misma llamada.

### 3. Loop de Reconciliación de Fondo (`_withdrawal_resolution_loop`)
- Ciclo autónomo cada 60 segundos que consulta el estatus de retiros pendientes en los servidores de BetMexico.
- Detecta transiciones: `pending` → `approved` / `rejected`.
- Emite eventos reactivos por SSE (`withdrawal`, `withdrawal_ready_changed`) para actualizar el dashboard sin recargar la página.

### 4. Generación de Ficha SPEI 1-Tap Copy
- Emite la tarjeta final en Telegram y Web con formato monoespaciado:
  ```
  TITULAR: JUAN PEREZ
  CURP:    PEJU890101HDFRRN01
  CLABE:   646180123456789012 (STP)
  MONTO:   $1,250.00 MXN
  ```
- Permite al operador transferir o verificar el depósito en 1 solo tap desde su teléfono móvil.
