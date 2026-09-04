# 06 — Sesiones, JWT y Refresh (Mantenimiento de Cuentas)

> **Ubicación:** `account_refresh.py`, `jwt_keeper.py`, `prewarm.py`.
> **Canvas Detallado:** [[06 — Sesiones, JWT y Refresh.canvas]]
> **Modelo Mental:** [[09 — Arquitectura de Grafo de Agentes (Cocina)]] (Estación de Mantenimiento y Despensa de Cuentas Vivas).

---

## 🔑 Ficha Técnica y Ciclos de Sincronización

### 1. Loop de Refresco de Cuentas (`account_refresh.py`)
- **Ciclo:** Ejecución continua en background cada 5 minutos (`ACCOUNT_REFRESH_INTERVAL_SEC=300`).
- **Filosofía Cero-Captcha:** Reutiliza el JWT vigente para consultar saldos y movimientos en BetMexico sin disparar logins ni gastar saldo de CapMonster.
- **Persistencia Exacta:** Registra el balance real en SQLite WAL (incluyendo saldo \$0 confirmado).
- **Caché `withdrawal_ready`:** Si detecta saldo acreditable, precachea el estado de retiro listo y la institución bancaria.

### 2. Prioridad para Cuentas "Hot" (`is_hot_account`)
- **Criterio Hot:** Saldo > \$50, autolock activo o retiro en curso no reconciliado.
- **Fast-Track:** Las cuentas hot se procesan al inicio del lote, omitiendo restricciones de grado o bloqueos ordinarios de pool.

### 3. Servicio de Despertado (`jwt_keeper.py`)
- Monitorea sesiones próximas a expirar en lotes de 50 cuentas.
- **Login Gentil:** Incorpora pausas aleatorias (jitter) y backoff para evitar el código 406 `FAILURE_IN_CAPTCHA`.
- Si un JWT expira durante el refresco, emite el evento asíncrono `_wake_jwt_keeper` con debounce de 5 minutos para renovar la sesión sin ráfagas.

### 4. Router Prewarm (`prewarm.py`)
- Permite a los operadores 'calentar' cuentas bajo demanda.
- **Cap de Seguridad:** Máximo 30 peticiones por operador cada 10 minutos. Omite cuentas revisadas hace menos de 5 minutos.
