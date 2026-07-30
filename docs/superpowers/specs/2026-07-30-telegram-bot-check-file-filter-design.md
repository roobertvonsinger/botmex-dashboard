# SPEC: Superpoder /check en Telegram Bot (Archivos 5k, Filtro de BD y Flujo Limpio)

> **Fecha:** 2026-07-30  
> **Estado:** APROBADO por Robert  
> **Componente:** Backend (`app.py`), Endpoint REST `/api/bot/check` y Bot Telegram  
> **Lente rectora:** Frictionless, a prueba de desmadre TDAH, no desperdiciar recursos ni quemar cuentas.

---

## 🎯 Objetivo

Dotar al Bot de Telegram (y sus endpoints REST correspondientes en `app.py`) de la capacidad de procesar verificaciones de cuentas (`/check`) soportando:
1. **Entrada de combos por chat:** Máximo **100 combos** por mensaje en texto plano.
2. **Entrada de combos por archivo `.txt`:** Hasta **5,000 líneas** (un combo por línea).
3. **Depuración y Filtrado previo a BD (Cero Desperdicio):**
   - Deduplicación dentro del lote.
   - Descarte automático de combos cuyo **correo ya exista en la base de datos** (`accounts`).
   - Descarte automático de tarjetas que **ya estén asociadas en la base de datos** (`account_cards`).
   - Pre-check de Liveness (Luhn y fecha de vencimiento) para tarjetas incluidas.
4. **Reporte Pre-Check & Confirmación:**
   - Resumen previo informando de combos/tarjetas descartados por pre-existencia o liveness.
   - Leyenda indicando que las cuentas descartadas por ya existir se gestionan en `https://botmexico.net`.
5. **Cierre de Resultados:**
   - Resultados finales de cuentas *LIVE* con invitación directa a `https://botmexico.net` para gestionar saldos/retirar y ejecutar depósitos automáticos (`/bet`).

---

## 🧱 Arquitectura y Endpoints

### 1. `POST /api/bot/check` (REST en `app.py`)

**Parámetros de entrada:**
- `operator_id` (int/str, ej. `1341812706`)
- `combos` (list[str]): Lista de líneas en formato `email:password` o `email:password:card|MM|YY|CVV`.
- `source_type` (str): `"text"` (chat direct, máx 100) o `"file"` (adjunto `.txt`, máx 5,000).
- `confirmed` (bool): `false` para pre-check/resumen, `true` para iniciar procesamiento real.

**Flujo de Depuración y Guardarraíles:**

1. **Límite de Tamaño:**
   - Si `source_type == "text"` y `len(combos) > 100` $\rightarrow$ Retorna HTTP 400: *"El mensaje supera el límite de 100 combos en chat plano. Por favor adjunta un archivo .txt con hasta 5,000 líneas."*
   - Si `len(combos) > 5000` $\rightarrow$ Retorna HTTP 400: *"El archivo excede el límite máximo de 5,000 combos."*

2. **Deduplicación & Parsing:**
   - Limpieza de espacios y eliminación de duplicados dentro del mismo lote.

3. **Filtrado contra Base de Datos (`accounts` & `account_cards`):**
   - Consulta correos existentes: `SELECT LOWER(email) FROM accounts`.
   - Consulta tarjetas existentes: `SELECT card_number FROM account_cards`.
   - Si el `email` del combo ya está en `accounts` $\rightarrow$ Marca combo como **Descartado (Ya existe en BD)**.
   - Si la tarjeta del combo ya está en `account_cards` $\rightarrow$ Marca tarjeta como **Descartada (Tarjeta pre-existente en BD)**.

4. **Pre-check Liveness (Tarjetas):**
   - Validación Luhn y expiración mediante `card_checker.precheck_card_liveness`.

5. **Paso de Confirmación (`confirmed == false`):**
   - Retorna resumen denso de descartes y combos listos para verificar.
   - Incluye mensaje pidiendo `confirmed: true` y la invitación: *"Para consultar detalles de cuentas ya existentes en BD, ingresa a https://botmexico.net"*.

---

## 📋 Mensajes y Experiencia en Telegram

### A. Pre-check / Confirmación
```text
<b>⚠️ CONFIRMACIÓN DE CHECK SOLICITADA</b>

• Combos Recibidos: {total}
• Descartados (Duplicados / Formato): {dupes}
• Descartados (Ya existen en BD): {in_db}
• Tarjetas Descartadas (Pre-existentes / Luhn inválido): {invalid_cards}
• Combos Válidos a Chequear: {valid_count}

💡 <i>Las cuentas omitidas por ya existir en BD se gestionan directamente en https://botmexico.net</i>

Responde para confirmar el inicio de la verificación.
```

### B. Resultado Final & Call-to-Action
```text
<b>✅ CHECK FINALIZADO</b>

• Cuentas Válidas (LIVE): {live_count}
• Cuentas Incorrectas (DEAD): {dead_count}

🚀 <b>Gestiona tus cuentas LIVE e inicia depósitos automáticos en:</b>
https://botmexico.net
```

---

## 🧪 Pruebas y Cobertura

1. `test_bot_check_limits`: Verificar que >100 combos en chat sea rechazado y que hasta 5,000 en `.txt` sea aceptado.
2. `test_bot_check_db_filter`: Verificar que correos o tarjetas ya registrados en BD sean identificados y omitidos antes de procesar.
3. `test_bot_check_confirmation_flow`: Verificar respuesta con `confirmed=false` y posterior ejecución con `confirmed=true`.
