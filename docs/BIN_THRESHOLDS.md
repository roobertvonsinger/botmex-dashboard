# Thresholds por BIN — inteligencia de tarjetas (BetMexico)

> **Bitácora viva.** Observaciones EMPÍRICAS de Robert en operación real (no
> certezas — refinar con más datos). Cada BIN (primeros 6 dígitos de la tarjeta)
> tiene su propio límite que el procesador/banco impone. Al **sobrepasarlo**, la
> transacción se rechaza — unas veces como **3DS** (no acreditada), otras como
> **BANK_REJECTED directo**.
>
> **TODOS los thresholds se RESETEAN cada 24h** (ventana móvil de BetMexico). Por
> eso el dashboard ya tiene un recordatorio que avisa cuándo pasaron las 24h para
> reintentar. Misma ventana que nuestro cap (`_window_status`: `first_at + 24h`).

---

## Tabla de thresholds conocidos `[MANUAL]`

| BIN | Límite monto / 24h | Máx. # txns aprobadas | Tope por txn | Al exceder se manifiesta como | Notas |
|-----|--------------------|-----------------------|--------------|-------------------------------|-------|
| `511916` | **~$1500** acumulado | — (no observado) | — | **3DS** (se ve como "fondos insuficientes" tras depositar bien antes) | Deposita bien hasta ~$1500; el intento que cruza $1500 lanza 3DS. Coincide ~ con nuestro cap genérico (1499). |
| `491366` | **~$750** (3 × $250) | **3** aprobadas | **$250** c/u | **BANK_REJECTED directo** (sin 3DS) | Tras la 3.ª aprobada rechaza de inmediato. Cada aprobada tope $250. |
| `526424` | **$1000** acumulado | — | **< $200** por bloque | rechazo | Solo hasta $1000/24h, en bloques de **menos de $200** cada uno. |

> Formato para agregar BINes nuevos: una fila con lo observado. Si un campo no se
> ha medido, dejar `—` (no inventar).

---

## Cómo se relaciona con lo que ya existe `[MANUAL]`

- **Cap genérico actual**: `DEP_MAX_24H = 1499` por CUENTA (`deposits.py`), ventana
  24h vía `_window_status`. Es un tope global; NO conoce el BIN.
- **Problema**: para BINes MÁS restrictivos que 1499 (491366 = $750, 526424 = $1000),
  el cap genérico NO protege → se llega al límite del BIN y rebota (3DS/rechazo),
  quemando intentos y, en 511916, disparando 3DS que aborta misiones programadas.
- **Recordatorio 24h**: ya existe en el dashboard (avisa cuándo se puede reintentar
  tras el reset). Ver notificaciones / watchdog.

---

## Pendiente — enforcement por BIN (propuesta, NO implementado aún) `[MANUAL]`

Para que el sistema "le ponga atención" (Robert 2026-05-29) y no solo lo documente:

1. **Cap por BIN en ventana 24h**: además del cap por cuenta (1499), aplicar el
   límite del BIN (el más restrictivo gana). Contar lo acumulado por esa tarjeta/BIN
   en 24h (de `deposit_attempts` approved) y bloquear ANTES de intentar si el monto
   cruzaría el threshold del BIN.
2. **Reglas por BIN** (no solo un número): 491366 necesita contar # de aprobadas
   (máx 3) + tope por txn ($250); 526424 tope por bloque (< $200) + total ($1000).
3. **Alerta preventiva en UI**: al pegar una tarjeta cuyo BIN tiene threshold, avisar
   "este BIN aguanta ~$X/24h, llevas $Y" antes de lanzar la misión.
4. **Fuente de verdad**: estructurar estos thresholds en BD o config consumible
   (no solo este .md) para que `_check_caps` los lea.

Decisión de Robert pendiente: ¿implementamos el enforcement automático o por ahora
queda documentado + el operador lo vigila manualmente?

---

## Histórico `[MANUAL]`

| Fecha | BIN | Observación |
|-------|-----|-------------|
| 2026-05-29 | 511916 | 3DS al cruzar ~$1500 en `guardianhidalgo` (había depositado 9× bien, $1496 acumulado; el 10.º intento sobrepasaba $1500 → 3DS). |
| 2026-05-29 | 491366 | 3 aprobadas máx ($250 c/u), luego BANK_REJECTED directo. |
| 2026-05-29 | 526424 | Hasta $1000/24h en bloques < $200. |
