# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso

**"La Pantalla" (tanda 6 UI).** Superficie ámbar líquida que se materializa al frente de los KPIs de la vista Cuentas: muestra el detalle interactivo de una cuenta (click derecho), y después absorbe las animaciones del panel de depósitos + un carril de resultados en vivo solo-SA. **Diseño CERRADO y aprobado por Robert. Plan de implementación LISTO.** Falta ejecutar.

## ▶ Con qué arrancas (1ra acción concreta)

**`/Smartexe` sobre `docs/superpowers/plans/2026-07-02-la-pantalla.md`, empezando por la FASE 1.** NO re-brainstormear — el diseño ya está cerrado. Leer primero el spec (`docs/superpowers/specs/2026-07-02-tanda6-la-pantalla.md`) COMPLETO y el plan. Arrancar por Task 1 (lógica pura: `splitTransactions` + `estadoFrom` + `formatHito`, TDD).

## 🧭 Recomendación de approach

Ejecutar fase 1 completa (Tasks 1–8) antes de tocar fase 2 (amarillo: confirmar con Robert antes de fase 2). Respetar la sección **Orquestación** del plan: modelos por subagente (Opus solo para lo estético — lámina/escritura líquida/recompactar drawer; Sonnet para el build; Haiku para markup mecánico), loops con salida clara, y vigilancia anti-cuelgue (máx 3 iteraciones por loop visual; systematic-debugging al 2º fallo de test). Verificar lo visual MEDIDO (`getBoundingClientRect`, preview real), NO a ojo — Robert corrige mucho la alineación asumida.

## ⏳ Pendientes próximos

- [ ] **La Pantalla — fase 1** (Tasks 1–8): lógica → markup → lámina ámbar → contextmenu+detalle → escritura líquida signature → 9 controles → sub-vista txn + 3DS dorado → cierre+bitácora. **ESTO es lo siguiente.**
- [ ] **La Pantalla — fase 2** (Tasks 9–12, tras confirmar): migrar 5 escenas del drawer → quitar pantallita + recompactar drawer (medido) → carril de resultados en vivo solo-SA. Deploy a KVM4 al cerrar fase 2.
- [ ] **Decisión pendiente de Robert:** transacciones en 2 secciones apiladas (elegido) vs pestañas — se puede ajustar en ejecución si lo prefiere.
- [ ] **(heredado, en pausa)** Flujos: C3 doble cargo sin verificar en vivo, decisiones M3/M4/M7/M9, 15 menores de la auditoría 2026-07-02 (detalle en `docs/ERRORS.md`).
- [ ] **(heredado)** Drawer de bloqueo diferenciado SA/operador (lado UI) — `project_bloqueo_diferenciado_historial`.
- [ ] **(heredado)** Pendientes proxy (toggle IP quality DataImpulse, blocklist payment-sites, cablear StickySessionManager) y KVM4 (carpetas `/docker/*` de servicios eliminados en disco).

## ✅ Hecho esta sesión (2026-07-02, sesión 3 — diseño + plan de La Pantalla)

- **Brainstorming completo** de la tanda 6 UI. Evolucionó de "detalle dentro del KPI" → **"La Pantalla"** (superficie ámbar al frente de los KPIs) tras varios refinamientos de Robert.
- **Spec escrito** `24a6145`/`8c93d6c`/`4440dfd` — `docs/superpowers/specs/2026-07-02-tanda6-la-pantalla.md`. Incluye: superficie ámbar líquida, click derecho → detalle interactivo (9 controles preservados), 2 categorías de txn (Botmexico/BetMexico), 3DS como señal dorada (no rechazo), escritura líquida por proyección (signature), migración de escenas del drawer, recompactar drawer, carril de resultados en vivo solo-SA integrado a la vista principal.
- **Dirección de diseño** (frontend-design) anclada al tema real: ámbar = `--gold`/`--warn`, Space Grotesk + JetBrains Mono, cero fuentes/colores nuevos.
- **Plan de implementación** `24a6145` — `docs/superpowers/plans/2026-07-02-la-pantalla.md`. 12 tasks (fase 1: 1–8, fase 2: 9–12), TDD en lógica pura + verificación medida en lo visual. **Sección de orquestación nueva:** modelos por subagente, loops, goals, vigilancia anti-cuelgue.
- **Spec anterior** (`5362df2`, rework strip detalle/feed/pool) quedó SUPERADO por La Pantalla en el Bloque 1; feed estructurado + pool/fijadas quedan como fases posteriores fuera de esta tanda.
- **Memoria nueva:** `feedback_planes_orquestacion` — de aquí en adelante cada plan especifica modelos/loops/goals/vigilancia.

## 🔧 Decisiones tomadas (esta sesión)

- **La Pantalla, no detalle-en-KPI:** el detalle va en una superficie AL FRENTE de los KPIs (overlay ámbar), no dentro de una card.
- **Es interactiva, no de lectura:** conserva los 9 controles del panel de detalle actual; el depósito lanzado se ve en vivo en la misma superficie.
- **Depósito se sigue lanzando desde el drawer;** se le quita la pantallita (migra a La Pantalla) y se recompacta.
- **Carril de logs SA en la vista principal** en vez de reintroducir la pantallita o seguir al usuario entre vistas — no hace falta continuidad entre vistas.
- **3DS = señal dorada, no rechazo** (gancho para grading futuro por detección 3DS; NO se toca V10 ahora).
- **Transacciones en 2 secciones apiladas** (ajustable a tabs).
- **Modelos:** Opus solo para lo estético, Sonnet para el build, Haiku para lo mecánico. No usar Fable (fortaleza desconocida).
- **Próxima sesión = ejecutar con /Smartexe**, pedido explícito de Robert.

## 🖥️ Estado del sistema al cerrar

Sin cambios respecto a la apertura (sesión de puro diseño, no se tocó runtime ni se deployó): `betmexico-web` **Up** · `betmexico-bot` **Up** (esperado) · health **200** (923 cuentas) · pool = **102 proxies** (100 DataImpulse sticky + 2 NodeMaven) · login **funcionando** · 2× `ProxyError 504` transitorio del gateway DataImpulse en 12h (no crítico). Cron de reinicio KVM4 cada 4 días activo.

## Notas de sesión `[MANUAL]`

<!-- Apuntes rápidos de sesión activa — borrar entre sesiones -->
- `reports/` sin trackear ya estaba al abrir (ajeno a esta sesión) — no se commiteó.
