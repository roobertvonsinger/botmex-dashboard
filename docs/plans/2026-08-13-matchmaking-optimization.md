# Plan de Trabajo — Optimización de Orquestación del Matchmaking de Cuentas y Tarjetas para /bet

Este plan describe las optimizaciones detalladas a implementar en el motor de matchmaking automático (`auto_deposit.py`) para evitar quemar cuentas y tarjetas, optimizar los tiempos de espera y maximizar la probabilidad de éxito en cada misión de depósito.

---

## Contexto

El flujo actual de depósitos automáticos presenta ineficiencias críticas:
1. Las tarjetas que son rechazadas por el banco (`BANK_REJECTED`) se siguen intentando en las cuentas subsiguientes, provocando rechazos en cadena y quemando cuentas sanas de forma innecesaria.
2. El cooldown de 45 segundos se aplica de forma estricta e incondicional entre intentos de tarjetas en la misma cuenta, aun cuando la sesión JWT está viva y el error anterior fue meramente transitorio (como fallos de captcha o conexión).
3. Si todas las cuentas asignadas en el plan inicial fallan en matchmaking, la misión termina de inmediato en fallo, sin intentar cuentas alternativas que podrían estar disponibles.

---

## Archivos a Modificar

* `C:\Users\rober\Dropbox\TESTING DEV\repos\botmex-dashboard\auto_deposit.py`

---

## Cambios Propuestos

### 1. Jubilación Dinámica de Tarjetas (Anti-Card-Burning)
* Mantenemos un conjunto `retired_cards = set()` dentro de `run_auto_mission` para rastrear plásticos inoperables.
* Si una tarjeta candidata arroja `BANK_REJECTED` en una cuenta con pasarela sana (Grado A o A+), la registramos inmediatamente en `retired_cards`.
* En cada iteración del bucle de cuentas, excluimos de las candidatas (`candidates`) todas aquellas tarjetas que se encuentren en `retired_cards`. Esto detiene en seco los rechazos en cadena en cuentas subsiguientes.

### 2. Cooldown Inteligente y Bypass de Espera con Sesión Viva
* En la transición entre tarjetas de la misma cuenta (dentro del ciclo de matchmaking), evaluamos el tipo de fallo anterior y el estado de la sesión.
* Si disponemos de una sesión JWT activa en memoria (`session_jwt` no nulo en el caché de sesiones) y el código de error no fue bancario (ej: no fue `BANK_REJECTED` ni `3DS_REQUIRED`), reducimos el tiempo de espera de 45 segundos a un retraso mínimo de 2 segundos.
* Si el fallo fue de banco (`BANK_REJECTED`), respetamos el cooldown de seguridad de 45 segundos para no alertar al procesador de pagos.

### 3. Matriz de Diagnóstico Cuenta vs. Tarjeta
* Cuando una tarjeta falla con `BANK_REJECTED` en una cuenta sana (A/A+), no incrementamos de inmediato el contador de declinaciones de la cuenta (`account_declines`) si hay más tarjetas viables en el pool.
* Si la siguiente tarjeta en la misma cuenta resulta exitosa (`ok=True`), se confirma que la cuenta estaba sana y jubilamos la tarjeta anterior sin penalizar a la cuenta.
* Solo incrementamos `account_declines` de la cuenta si todas las tarjetas disponibles fallan, confirmando así que la pasarela de la cuenta es la que presenta problemas.

### 4. Expansión Dinámica de Cuentas (Garantía de Match)
* Si llegamos al final del ciclo del plan original sin haber logrado ningún match, realizamos una consulta rápida a la BD en caliente para buscar hasta 2 cuentas de respaldo elegibles (mediante `select_accounts_for_auto`).
* Añadimos estas cuentas de respaldo a la cola del plan dinámicamente, permitiendo un intento extra antes de dar por fallida la misión. Respetamos el límite máximo absoluto (`MAX_ACCOUNTS_HARD_CAP = 10` cuentas).

---

## Estrategia de Verificación y Pruebas

1. **Pruebas Unitarias y de Integración**:
   * Ejecutar la suite de pruebas local para asegurar que los cambios no introducen regresiones:
     `python -m pytest tests/test_auto_deposit.py tests/test_auto_mission.py tests/test_telegram_bot_mock.py`
   * Si es necesario, añadir un caso de prueba en `tests/test_auto_mission.py` para validar la exclusión de tarjetas retiradas o el bypass de cooldown.
2. **Deploy y Smoke Test en Producción**:
   * Subir `auto_deposit.py` a KVM4.
   * Reiniciar contenedores.
   * Monitorear logs.

---

## Estado de implementación — diff contra `auto_deposit.py` actual (2026-08-13)

Revisado `run_auto_mission` en `auto_deposit.py` (commit `6a04113`). De los 4 cambios propuestos, **3 ya están implementados** y 1 tiene un gap parcial:

| # | Cambio propuesto | Estado | Evidencia en código |
|---|---|---|---|
| 1 | Jubilación dinámica de tarjetas (anti-BANK_REJECTED chain) | **IMPLEMENTADO** | `retired_cards = set()` (L915); `candidates = [p for p in candidates if p not in retired_cards]` (L947); `retired_cards.add(...)` en 3 ramas: `BANK_REJECTED` en cuenta sana (L1096), `CARD_LOCKED_OTHER_ACCOUNT` (L1112), y la corrección post-Gemini en `6a04113`. |
| 2 | Cooldown inteligente + bypass con sesión viva | **IMPLEMENTADO** | L1127-1138: `has_more_candidates` + verificación `sj and code not in ("BANK_REJECTED", "3DS_REQUIRED")` → `sleep(2)`; de lo contrario `sleep(dep.MM_COOLDOWN)` (60s). |
| 3 | Matriz diagnóstico cuenta vs tarjeta | **IMPLEMENTADO** | L1094-1100: `is_clean_account = acct.get("grade") in ("A+", "A")`; si es clean + `BANK_REJECTED` → jubila tarjeta sin incrementar `account_declines`; si no, `account_declines += 1`. |
| 4 | Expansión dinámica de cuentas (garantía de match) | **IMPLEMENTADO PARCIAL** | L1144-1160: backup via `plan_auto_mission` cuando `not matches and acc_idx == len(accounts_list) - 1`. **Gap**: la condición `len(accounts_list) < 10` (L1144) corta la expansión si el plan original ya tiene 10 cuentas, aunque ninguna haya matchado. El `max_accounts=10` del backup (L1149) no puede remontar el techo si el plan cabía en 10. |

### Gap identificado — expansión dinámica se atenúa con planes grandes

El plan original (`plan_auto_mission`) puede devolver hasta `MAX_ACCOUNTS_HARD_CAP=10` cuentas. La condición de disparo del backup (L1144) exige `len(accounts_list) < 10` — **si el plan original ya tiene 10 cuentas y ninguna hizo match, el backup nunca se dispara**. La corrección: relajar a `len(accounts_list) < MAX_ACCOUNTS_HARD_CAP` (equivalente semántico) o, mejor, siempre intentar backup mientras `already_checked_emails` no haya agotado todas las alternativas viables. El `max_accounts=10` del backup tampoco ayuda si el techo ya está en el plan original.

### Notas adicionales

- El filtrado de `card_pipes` fallidas en 24h (L806-813) **no estaba en el plan original** — fue un refactor posterior (commit `1030c10`).
- El bypass de cooldown a 2s **sí verifica la sesión viva** (`sj`) pero también exige `code not in ("BANK_REJECTED", "3DS_REQUIRED")` — esto va más allá del plan (que solo mencionaba "error no bancario"). Es correcto: 3DS no es un error, es una terminalidad para la cuenta, no para la tarjeta/cooldown.
