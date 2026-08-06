# Reporte — Anti-fuga de método en bot Telegram + portal (progreso de misión `/bet`)

> **Fecha**: 2026-08-05  
> **Rama**: `feature/antifuga-bot-portal-2026-08-05`  
> **Último commit**: `1e115af`  
> **Baseline**: 397 passed → **Final**: 412 passed (+15 tests nuevos)  
> **Handoff**: `docs/plans/2026-08-05-handoff-antifuga-bot-portal-modo-auto.md`  
> **Spec de diseño**: `docs/superpowers/specs/2026-08-05-bot-portal-antifuga-progreso-design.md`

---

## 1. Qué se implementó en cada área (A-D)

### Área A — Bloque terminal del bot: 4 caminos de cierre sin cadencia

**Archivo**: `telegram_bot_mock/bot.py`

| Cambio | Ubicación |
|---|---|
| Función pura `_mission_status_text(status, extra)` — 4 caminos diferenciados por `stopped_by_user` | `bot.py:123` |
| Guard idempotente `_gate_closed_missions: set` — evita doble-mensaje en cancelación del gate | `bot.py:120` |
| Closure `on_progress` rewired para usar `_mission_status_text` + guard | `bot.py:885-913` |
| `handle_confirm_gate_callback` marca `_gate_closed_missions.add(mission_id)` en `stop_sched_` | `bot.py:1076` |

### Área B — Piso de 45-60s antes de Fase 2 con status `preparing`

**Archivo**: `auto_deposit.py`

| Cambio | Ubicación |
|---|---|
| `import random` agregado | `auto_deposit.py:584` |
| `"matched_at": time.time()` en cada entrada de `matches` | `auto_deposit.py:1017` |
| Piso `random.uniform(45, 60)` + broadcast `preparing` + `asyncio.sleep` | `auto_deposit.py:1200-1214` |

### Área C — Motor único `_fake_progress_pct` consumido por bot+portal

**Archivos**: `auto_deposit.py`, `static/portal.js`, `telegram_bot_mock/bot.py`

| Cambio | Ubicación |
|---|---|
| Función pura `_fake_progress_pct(status, extra) -> int` — única fuente de verdad | `auto_deposit.py:628` |
| `_broadcast_mission` agrega `fake_pct` al payload SSE y al `extra` de `on_progress` | `auto_deposit.py:735,744` |
| `bot.py::on_progress` consume `fake_pct` para texto de scheduling | `bot.py:154` (vía `_mission_status_text`) |
| `portal.js` consume `ev.fake_pct` del SSE en vez de recalcular en JS | `portal.js:224` |
| `portal.js` case `preparing` con mensaje genérico | `portal.js:251` |
| `portal.js` resumen terminal: `s.deposited` solo si `completed && !stopped_by_user` | `portal.js:335-338` |
| `portal.js` `s.approved` (conteo) oculto SIEMPRE del resumen | `portal.js:336-343` |
| `portal.js` scheduling ya no muestra `ev.completed/ev.total` (conteo real) | `portal.js:256` |

### Área D — Documentación

| Doc | Cambio |
|---|---|
| `docs/SSE_EVENTS.md` | Evento `auto_mission` ahora documenta status `preparing` y campo `fake_pct` |
| `docs/ERRORS.md` | Entrada nueva con síntoma/causa raíz/fix/test de regresión |
| `docs/AUDIT.md` | Fila "Anti-fuga de método" pasa de 🔵 DISEÑADO a ✅ implementado |

---

## 2. Los 4 caminos de cierre de misión — texto exacto en bot y portal

### Camino 1: `status="failed"` (sin match viable en Fase 1)

| Canal | Texto |
|---|---|
| **Bot** | `❌ No se encontró match viable.` |
| **Portal** | Status: "Falló" · Resumen: "—" (sin cifras) |

### Camino 2: `status="completed"` + `stopped_by_user=True` (operador declinó el gate)

| Canal | Texto |
|---|---|
| **Bot** | `🛑 Proceso detenido antes del llenado.` (el guard idempotente evita que `on_progress` sobrescriba el mensaje limpio del gate) |
| **Portal** | Status: "Completado" · Resumen: "—" (sin cifras, porque `stopped_by_user=true`) |

### Camino 3: `status="cancelled"` (detenido por el operador)

| Canal | Texto |
|---|---|
| **Bot** | `🛑 Detenido por el operador` |
| **Portal** | Status: "Cancelado" · Resumen: "—" (sin cifras) |

### Camino 4: `status="completed"` sin `stopped_by_user` (Fase 2 completa)

| Canal | Texto |
|---|---|
| **Bot** | `✅ Misión completada. Depositado: ${dep:.0f} en {accts} cuentas.` — solo $ total, NUNCA `aprobados`/`fallidos` |
| **Portal** | Status: "Completado" · Resumen: `fmtMoney(s.deposited)` (solo si `!stopped_by_user`) |

### Estado intermedio: `scheduling` (en curso)

| Canal | Texto |
|---|---|
| **Bot** | `⚡ Procesando… {fake_pct}%` — sin conteo real `comp/tot` |
| **Portal** | Barra de progreso al `fake_pct%` + pulso "en curso…" — sin `completed/total` |

### Estado intermedio: `preparing` (piso 45-60s pre-Fase 2)

| Canal | Texto |
|---|---|
| **Bot** | `⏳ Preparando…` |
| **Portal** | "Preparando…" + pulso "en curso…" |

---

## 3. Confirmación: `_fake_progress_pct` es la ÚNICA fórmula

- **Backend**: `auto_deposit.py:628` — `_fake_progress_pct(status, extra) -> int` produce los valores para todos los estados.
- **SSE**: `_broadcast_mission` (`auto_deposit.py:735`) agrega `fake_pct` al payload SSE.
- **Portal**: `portal.js:224` — `const fp = ev.fake_pct` consume el valor del SSE, no recalcula. Todas las llamadas a `animateProgressTo()` usan `fp`.
- **Bot**: `bot.py:154` — `_mission_status_text` usa `extra.get('fake_pct')` para el texto de scheduling.

**No queda ninguna fórmula de progreso duplicada entre `portal.js` y `auto_deposit.py`.**

---

## 4. Resultado final de `python -m pytest -q`

```
412 passed, 268 warnings in 238.47s (0:03:58)
```

Baseline: 397 passed → +15 tests nuevos en `tests/test_antifuga_bot_portal.py`.

---

## 5. Nombre exacto de la rama y último commit hash

- **Rama**: `feature/antifuga-bot-portal-2026-08-05`
- **Último commit**: `1e115af1a6226f2889930e42728de7b8def355c0`
- **Commits incrementales**:
  1. `516fcc9` — feat(antifuga): Area A - bloque terminal del bot sin cadencia ni conteo
  2. `2f336f3` — feat(antifuga): Area B - piso 45-60s antes de Fase 2 con status 'preparing'
  3. `abc0e38` — feat(antifuga): Area C - portal consume fake_pct del SSE + fix resumen terminal
  4. `1e115af` — docs(antifuga): Area D - SSE_EVENTS, ERRORS, AUDIT actualizados

---

## 6. Preguntas abiertas o decisiones tomadas sin cobertura explícita

1. **`matches_count` en `_fake_progress_pct` para estado `match`**: el spec dice que la fórmula de `portal.js` usa `missionState.matches.length` (conteo acumulado en el cliente). El backend no tiene ese conteo por evento individual — cada `match` broadcast es uno solo. Solución: `_fake_progress_pct` lee `extra.get('matches_count', 0)` — el caller puede pasarlo si quiere precisión, pero si no se pasa (caso actual), el primer match da 25% (count=0). Esto es conservador (el portal ya anima visualmente entre checkpoints) y no revela información. **Decisión**: dejarlo así hasta que se quiera pasar el conteo acumulado desde `run_auto_mission`.

2. **`portal.js` scheduling sin `completed/total`**: el spec (`portal.js:251`) mostraba `ev.completed + '/' + total` en el sub-texto. Lo removí completamente (dejé solo `shortEmail(ev.email)`) porque `completed/total` es conteo real de depósitos — mismo tipo de fuga que `{comp}/{tot}` del bot. El handoff §2 Área C punto 5 no lo pide explícitamente, pero es consistente con la regla rectora ("el operador NUNCA debe ver la cadencia real").

3. **`portal.js` `cancelled`/`failed` usan `fake_pct` del SSE**: antes usaban `missionState.pct || 50` como fallback. Ahora usan `ev.fake_pct || (missionState.pct || 50)` — si el backend manda `fake_pct`, se usa; si no, fallback al viejo comportamiento. Esto es defensivo: si alguien cancela antes de que el backend emita un `fake_pct`, el portal no se queda sin barra.

4. **Formatter reformateó `bot.py` y `auto_deposit.py`**: un formatter (probablemente el pre-commit hook o black) expandió el código de ambos archivos más allá de los cambios funcionales. El diff es más grande de lo ideal, pero los cambios reales son solo los descritos en este reporte. No se modificó lógica existente más allá de lo especificado.
