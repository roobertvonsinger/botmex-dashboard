# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso

**Rediseño de interacción universal del dashboard** — "La Pantalla" (vidrio ámbar translúcido premium sobre los KPIs). Rama **`feat/la-pantalla`** (NO mergeada a main aún). Fase A (densidad + dedup + acabado + controles) y Fase B (click-izquierdo + selección Excel) **completas y en PROD**. Falta la **AUDITORÍA** antes del veredicto de Robert y el merge.

## ▶ Con qué arrancas — AUDITORÍA en sesión limpia (pedido de Robert)

**NO escribir código nuevo primero.** Hacer un **review/auditoría completo de todos los avances de la rama `feat/la-pantalla`** (Fase A + Fase B, commits `ee17523` + `5a1acb1`), combinando:
- **Skills de review:** `/code-review` (o `security-review`) + `feature-dev:code-reviewer` sobre el diff `main...feat/la-pantalla`.
- **Skill de debugging:** `superpowers:systematic-debugging` para cazar regresiones de interacción (el click-izq cambió el hábito de la tabla; verificar que selección múltiple, depósito bulk, copiado, lock/unlock, y el acordeón viejo `openDetailModal` no quedaron rotos).
- **Design skills (nuevas, instaladas global):** `design-engineer` + `micro-100-200ms` + `hover-interactions` para auditar el *feel* de La Pantalla y los controles manita (timing, spring/squash, contraste, nitidez, reduced-motion).

Entregar un **reporte de hallazgos** (bugs, riesgos, mejoras de feel) → **Robert da su veredicto** → recién ahí se aplican fixes y **Claude mergea a main** (ver memoria `feedback-merge-en-checkpoints`: el merge lo hace Claude, Robert solo recibe aviso).

## 🧭 Recomendación de approach

Correr la auditoría por capas: (1) diff review de lógica (dedup en `app.py`, handlers de `app.js`), (2) debugging de interacción (probar los flujos que tocaban la tabla), (3) crítica de diseño del feel. Priorizar la **dedup** (toca datos que Robert usa para trackear) y la **selección Excel** (cambió muscle-memory, alto riesgo de regresión en el flujo de depósito bulk).

## ⏳ Pendientes próximos

- [ ] **AUDITORÍA** (arriba) → veredicto de Robert → fixes → **Claude mergea `feat/la-pantalla` a main** y avisa.
- [ ] Verificar en PROD (Robert presente): dedup no oculta txns legítimas; selección Excel + depósito bulk; click-izq no rompe nada.
- [ ] **Panel de depósitos:** colores intuitivos (rechazo ≠ aprobado) · countdown del programado siempre visible · 1 cuenta → 1 tarjeta contorno premium.
- [ ] Bordes de resize de `depos_window` — decisión tomada: quedan con flechas `ns/ew-resize` (comunican eje). Revisar si Robert insiste en manita.
- [ ] **(heredado)** flujos C3/M3/M4/M7/M9, drawer bloqueo diferenciado, pendientes proxy.

## ✅ Hecho esta sesión (2026-07-03)

- **Fase A** (`ee17523`): fechas completas en txns (fix regex ISO), divisor datos|txns, tarjetas+notas en pequeño, tinte de filas por resultado, colapso de columna vacía, combo en perla, acabado perla translúcida, contorno de texto, **dedup de transacciones dashboard/betmex** (aprobados+rechazados, ±3min, consume firma — verificado con datos reales), control de tamaño = manita en todo el borde + fix pointer-events, manita unificada en gutters + spring/squash.
- **Fase B** (`5a1acb1`): click IZQUIERDO abre La Pantalla; selección Excel (Ctrl+Click toggle, Shift+Click rango); retirado contextmenu + checkboxes + drag-select (mouse y pointer); `.sel-cell` = indicador de selección (dot).
- **Skills instaladas (global):** `design-engineer` + `micro-100-200ms` + `hover-interactions` (evaluadas de skills.sh; se descartaron las de Tailwind/React/3D).
- **Limpieza:** se cerraron 3 sesiones de Claude idle (liberó ~1.1 GB RAM).
- Docs: `FRONTEND.md` (sección La Pantalla + handlers), `ERRORS.md` (dedup + grip pointer-events). Ambas fases pusheadas a Forgejo. Deploy PROD por hot-mount (estáticos) + 1 restart (app.py dedup); md5 servido == repo verificado en cada deploy.

## 🔧 Decisiones tomadas

- **Merge lo hace Claude**, no Robert (las ramas lo confunden); solo se le avisa. Ver `feedback-merge-en-checkpoints`.
- **Dedup conserva el registro del dashboard** (nuestro, con operador+tarjeta), omite el eco de BetMexico. "Es uno u otro".
- **Combo en perla**, dorado reservado al saldo. Acabado perla = detalle en bordes, contenido por encima del grano.
- **Controles deslizantes = manita** (grab/grabbing); resize por borde de ventana flotante = flechas.

## 🖥️ Estado del sistema al cerrar

`betmexico-web` Up · health 200 (923 cuentas) · `betmexico-bot` Up · pool **102 proxies** (dataimpulse ×100, nodemaven ×2) · login/proxies sanos, sin errores recientes.

## 🔧 Notas técnicas

- **Preview local NO sirve** para La Pantalla (sin DB local no hay qué renderizar). Verificación = PROD. La auditoría de código sí es local (leer el diff).
- Cache-bust actual: `?v=20260703n` (app.js, pantalla.js, style.css, pantalla.css).
