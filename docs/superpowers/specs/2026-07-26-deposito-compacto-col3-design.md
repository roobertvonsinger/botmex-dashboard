# Depósito compacto conviviendo con retiro en La Pantalla (col 3)

> Spec de diseño — sesión 2026-07-26 noche. Brainstorm cerrado y aprobado por Robert.
> Alcance: **100% frontend**. El motor de depósitos (`depos.js`, `depos_logic.js`, endpoints backend) **no cambia**.

## Objetivo

Robert vio el panel de retiro nuevo en col 3 de La Pantalla y quiere que el depósito **conviva ahí mismo, compacto**,
en vez de excluirse mutuamente (hoy: CSS `:has()` oculta el retiro cuando hay una misión de depósito activa —
seguirá así solo para el estado ACTIVO; en reposo ambos deben verse). El panel de depósito actual "funciona bien
pero se ve horrible" — el trabajo es de síntesis visual, respetando 100% la lógica y los controles existentes.

## Alcance — qué se toca y qué NO

- **NO se toca**: `depos_logic.js` (reglas puras: `deriveMode`, `presetsForMode`, validaciones), el motor de depósitos
  (`deposits.py`, caps `DEP_MAX_PER_TXN`/`DEP_MAX_24H`, backoff, clasificación de resultado), ningún endpoint backend.
- **SÍ se toca**: cómo y dónde se PINTA el panel de depósito cuando La Pantalla de una cuenta está abierta. Nuevo
  modo de render "compacto" en `depos.js`, montado en `.pat-col-stage` con clases CSS nuevas (estilo `pat-*`, el
  mismo lenguaje visual que ya se construyó para retiro) — **NO se reutiliza el CSS/look del panel viejo**
  (`depos.css` actual: banner, saludo rotativo, `.duo` de 2 columnas).
- **La ventana flotante/dockeable vieja (`DeposWindow`) se desactiva SOLO cuando hay una cuenta abierta en La
  Pantalla.** Se mantiene intacta (motor + su propio look) como fallback para el multi-select tipo Excel de la
  tabla (`openDepositModal(null, {ids:[...]})`, `app.js:6192`) — ese flujo no tiene ninguna cuenta anclada, no puede
  vivir dentro de una La Pantalla que no está abierta.

## Reglas por tipo de depósito (YA EXISTEN, se preservan tal cual — `depos_logic.js`)

El modo se **infiere automáticamente**, nunca se elige a mano:

```
deriveMode(nCuentas, reps):
  nCuentas > 1        → multi
  nCuentas <= 1, reps>1 → scheduled (programado)
  nCuentas <= 1, reps=1 → single
```

| Modo | Presets monto | Input manual | Reps visible | Nota |
|---|---|---|---|---|
| `single` / `scheduled` | $10, $50, $150, $300, $490 | SÍ (además de presets) | SÍ (stepper reps) | "Toca un monto o escríbelo · ($10 a $499)" |
| `multi` | $10, $50, $490 | NO (solo presets — evita typos en batch) | NO | "Montos fijos para varias cuentas · $490 = monto alto (tope $499)" |

El único control que distingue single de scheduled es el valor del stepper de reps (reps=1 → single, reps>1 →
scheduled) — mismo control, sin toggle aparte. El panel compacto debe seguir esta MISMA regla exactamente
(`presetsForMode(mode)` decide qué presets/inputs mostrar, sin reimplementar la lógica en el nuevo render).

## Layout en col 3

Apilado, ambos compactos y visibles en reposo (por default, sin misión activa):

```
┌ .pat-col-stage ──────────────────┐
│ 🏧 Retirar — email@cuenta        │  ← ya existe, sin cambios
│ Saldo Real: $XXX.XX               │
│ [monto input]                     │
│ [status]                          │
├───────────────────────────────────┤
│ 💳 Depositar — email@cuenta       │  ← NUEVO, estilo pat-*
│ Cuentas: [chip actual] [+agregar] │
│ Tarjeta: [chip] [chip] [+agregar] │
│ Monto: [presets] [input si single]│
│ Reps:  [stepper, solo si aplica]  │
│ [status / pausar-abortar si activo]│
└───────────────────────────────────┘
```

- Si no caben ambos completos en el alto disponible → el bloque de depósito scrollea internamente (mismo patrón
  `.pat-cramped` ya implementado hoy para el overflow horizontal — aquí es vertical, misma filosofía: medir, no
  inventar un breakpoint).
- **Estado ACTIVO** (misión de depósito corriendo): el escenario animado (`#depStage`) sigue tomando la columna
  COMPLETA y oculta ambos paneles compactos (retiro y depósito) — mismo comportamiento de hoy, sin cambios. Una
  cuenta no se deposita y retira a la vez (el lock de 2h ya lo impide), así que esto no pierde nada.

## Qué se corta vs qué se mantiene

**Se corta (basura visual, cero pérdida funcional):**
- Banner `depositos-banner.jpg` + saludo rotativo (`#greet`).
- `.duo` de 2 columnas (cuentas | tarjetas lado a lado) → se apila a 1 columna (a ~358px de ancho útil, combos
  largos se truncarían feo en 2 columnas; apilado no pierde nada, solo ocupa más alto).
- Mini-lista de movimientos de la misión (`#mov`) — redundante dentro de La Pantalla: la columna 2 (movimientos de
  la cuenta) ya muestra el intento en vivo vía el mismo SSE (`account_refreshed`/`deposit`) que hoy alimenta `#mov`.
  El depósito se sigue registrando igual en BD/actividad global — solo se quita la vista duplicada.
- Botón "Depositar" interno del panel (`#dep`). Ver más abajo.

**Se mantiene 100% funcional:**
- Chips de cuentas (agregar/quitar) — default: solo la cuenta actual (igual que retiro).
- Chips de tarjetas (agregar/quitar).
- Monto (presets + manual según modo).
- Reps (stepper, solo cuando aplica).
- Pausar/Abortar durante misión activa.
- "+Otro depósito" (misión paralela) — se mantiene, compacto.
- Toda clasificación de resultado, guardarraíles, caps — sin tocar (viven en backend/`depos_logic.js`).

## Botón único de disparo (`.pat-actions`)

Hoy: click en "Depositar" (`.d-deposit-btn`, en `.pat-actions`) llama `openDepositModal(accId)` → abre la ventana
flotante vieja. **Cambia a**: dispara DIRECTO, sin popup — mismo patrón ya aprobado para "Retirar"
(`.d-withdraw-fire`). Toma el estado actual del panel compacto de abajo (cuentas/tarjetas/monto/reps ya armados) y
llama la misma función interna que hoy dispara `#dep` (`runSingle`/`runMulti`/`runScheduled` según `_dx.mode`
derivado). El botón interno viejo (`#dep`, dentro del panel) desaparece — queda **un solo botón total** en
`.pat-actions`, igual que retiro. Resultado: 1 click = depósito, sin popup, con la cuenta ya precargada.

## Automático vs manual (resumen para Robert)

**Automático** (el operador no lo toca): cuenta precargada, modo inferido (`deriveMode`), escenario/animación,
refresco de saldo/tabla al terminar (SSE), registro en BD/actividad.

**Manual** (controles visuales que sí se tocan): tarjeta, monto, cuentas extra (opcional, para armar multi), reps
(solo si se arma programado), pausar/abortar (solo con misión activa), 1 botón "Depositar" en `.pat-actions`.

## Testing / verificación

- Verificación visual en navegador real (mismo patrón que el fix de ancho medio de hoy — `getBoundingClientRect`,
  sin inventar breakpoints).
- Smoke funcional: 1 depósito real chico ($10) desde el panel compacto, confirmando que el modo se infiere bien
  (single), la tarjeta/monto se envían igual que hoy, y el resultado se refleja en col 2 + tabla sin el `#mov`
  duplicado.
- Confirmar que el multi-select de tabla (`openDepositModal(null, {ids:[...]})`) sigue abriendo la ventana flotante
  vieja sin cambios (no debe romperse por este trabajo).

## Riesgos / notas

- El panel compacto reutiliza `_dx` (estado interno de `depos.js`) y las funciones `runSingle/runMulti/runScheduled`
  — se requiere que el nuevo render y el viejo NO corran simultáneos para la misma cuenta (mismo principio que ya
  aplica hoy entre ventana flotante y La Pantalla — `pantalla.js:146` ya oculta/relayoutea `DeposWindow` al abrir La
  Pantalla).
- `#depStage` (escenario) ya vive reparentado en `.pat-col-stage` — no cambia su mecanismo de montaje, solo qué lo
  rodea en el estado de reposo.
