# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso

**Afinar la UI del dashboard al feedback de Robert (post-reorg) — tanda 3 CERRADA y deployada a prod (2026-06-29).** 7 ajustes visuales/interactivos vivos en `https://botmexico.com.mx`. **Robert dijo "hay algunos ajustes por hacer pero bien por ahora.. te digo en sesión nueva"** → hay más feedback de UI pendiente, sin especificar todavía.

## ▶ Con qué arrancas (1ra acción concreta)

**Escuchar el feedback de UI que Robert traiga** — él dijo que lo dice en sesión nueva. NO hay acción predefinida; arrancar preguntando/recibiendo qué ajustes quiere y atacarlos al pixel/comportamiento. Si no trae nada, cerrar los pendientes de abajo (filtros propios del buscador es el más natural).

## 🧭 Recomendación de approach

Todo lo de la tanda 3 ya está en prod y verificado (md5 servido==repo + smoke público). Lo visual/interactivo solo se valida en runtime — Robert lo prueba logueado. Atacar lo que marque; medir layout objetivo con `getBoundingClientRect` contra el entry real si hay ajuste de pixeles (NO a ojo). El backend (leyes de dominio) sigue test-cubierto y sin tocar — no re-tocar sin razón.

## ⏳ Pendientes próximos

- [ ] **Ajustes de UI adicionales de Robert** (sesión nueva, sin especificar aún). PRIORIDAD — los dice él.
- [ ] **Cenefa: ¿CSS o raster?** La hice **recreada en CSS** (wordmark tricolor + glow), NO con el PNG que adjuntó (no existía como asset, no lo tengo como binario). Es fiel y mejor para una banda delgada (nítida, sin distorsión). **Si Robert quiere el raster exacto** → dejar el PNG en `static/assets/` y cambiar `.cenefa` por un `<img>` (1 min). Confirmar con él.
- [ ] **Filtros propios del buscador** (Robert lo dejó explícito "para después"). Hoy la búsqueda es dominante e ignora TODOS los filtros; el siguiente paso es darle filtros simples propios.
- [ ] **Minors diferidos** (heredados, no bloquean):
  - `account_cooling` NO llega a la marquesina (se emite inline en deposits.py, no vía `_broadcast`→`/api/events`). Copy ya listo; faltaría emitirlo por `_broadcast` (motor, fuera de scope UI).
  - Tabla: combos >56ch se truncan con ellipsis (valor completo en el detalle). Subir `--combo-width` si Robert quiere verlos enteros en la fila.
  - `/api/pool/publish` sin guardrail de cuenta lockeada (SA-only, benigno).
- [ ] **(heredado) e2e anti-rate-limit con cuentas frescas** — JWT cache hit, 429→cooling→saltar, re-login al 401. Bloqueado por proxy bajo.
- [ ] **(heredado) recargar plan DataImpulse** (~43 MB) — sin proxy fresco el login LIVE no resuelve.
- [ ] Retirar drawer viejo de depósitos (`#depDrawer`) + limpiar CSS muerto.

## ✅ Hecho esta sesión (2026-06-29 — tanda 3 de UI, deployada + smoke verde)

Commit en `main`, pusheado a Forgejo:
- **`b2f56e7`** `feat(ui): cenefa superior + marquesina lenta/click + combos copia+detalle + busqueda dominante + fix card desbordado` — 7 ajustes:
  1. **Cenefa superior** — banda delgada (`--cenefa-h: 30px`) full-width en el top del top; wordmark `botmexico.com.mx` tricolor (`.g/.w/.r`) + glow verde + puntos rojos. CSS, no raster. `.shell` → `calc(100vh - var(--cenefa-h))`; drawer y sidebar-mobile bajan `top: var(--cenefa-h)`.
  2. **Marquesina** — velocidad adaptativa `max(30, N*2.2)s` (antes 20s fijos = veloz); pausa al hover; click fila → `openAccountByEmail` → **detalle** (sin fallback a búsqueda; toast si no resuelve).
  3. **Recientes + combo de tabla** — click en las letras del combo **copia Y abre el detalle** (handler global de copia detecta `data-id`/`data-email` de cuenta). Tarjeta/CURP/pipe solo copian.
  4. **Búsqueda DOMINANTE** — `fetchAccounts` con `status=all` y sin grade/cards cuando hay query → corre sobre TODOS los registros, ignora filtros. `getVisible` ignora `filterInUse`. UI: `.search.has-query` se ilumina + `body.searching` atenúa filtros.
  5. **Botón X en el buscador** (`#searchClear`, `_clearSearch`, también Esc) → limpia + reload + foco al input.
  6. **Botón Restaurar reubicado** a la `.filterbar` (junto a los filtros), `.reset-btn` verde cuando hay algo que restaurar (antes en pagebar, invisible).
  7. **Fix card Pool desbordada** — root cause: `availW()` en `initLpResize` no restaba el padding del `.lpanel` (44px) → las columnas px se desbordaban. Fix: restar `getComputedStyle().paddingLeft/Right`. Auto-sana en próximo load. (Ver `docs/ERRORS.md`.)
- **Docs:** `FRONTEND.md` (cenefa + interacción cuentas + marquesina) + `ERRORS.md` (Pool card desbordada). MAP.md/MAP_DEEP.md regenerados por el hook.
- **Deploy KVM4 (2026-06-29):** 3 estáticos (`index.html` + `app.js` + `style.css`) → `/docker/betmexico/code/web/static/` (hot-mount, sin restart). **Verificado:** md5 servido==repo (los 3 exactos), markers presentes, health 200 (923 cuentas), smoke público vía Traefik OK (cenefa/searchClear/marquesina-lenta/búsqueda-dominante/availw-fix servidos). Cache-bust `20260629g`.

## 🔧 Decisiones tomadas (esta sesión)

- **Cenefa = CSS, no raster**: el PNG adjuntado no estaba como asset; el wordmark CSS es fiel y superior para una banda delgada (nítido, theme-aware, sin distorsión). Reversible a `<img>` si Robert insiste.
- **Búsqueda dominante ignora TODOS los filtros** (status/grade/cards/inUse): la búsqueda corre sobre todos los registros. Filtros propios del buscador = después.
- **Combo click = copia + detalle simultáneo** (cuenta), scopeado por `data-id`/`data-email`: tarjeta/CURP/pipe siguen solo copiando.
- **Marquesina = velocidad adaptativa** (ritmo constante sin importar # de eventos) en vez de duración fija.
- **Click en fila (marquesina/recientes) abre detalle, NO busca**: el fallback a búsqueda era el "torpe".

## 🖥️ Estado del sistema al cerrar

`betmexico-web` **Up 10h** · `betmexico-bot` **Up 4 días** · health **200** (923 cuentas) · sin errores (ProxyError/406/504/Traceback) en últimas 12h. Todo en `main`, pusheado a Forgejo (`b2f56e7`). **Login/proxies NO testeados esta sesión** (fue 100% UI). **Pool NO medido esta sesión** — último dato conocido (cierre anterior): 52 proxies (50 DataImpulse rotatorio + 2 NodeMaven, ⚠️ plan DataImpulse posiblemente bajo ~43MB, heredado).

## ⚠️ Nota de tests (no alarmarse)

Esta sesión fue UI pura (sin Python, sin lógica unit-testeable nueva). Los **16 fallos PRE-EXISTENTES** de `pytest` siguen ahí (idénticos en la base, NO del cambio): `tests/test_api.py` (harness viejo) + `test_a21_visibilidad.py` (`canonical_card_pipe`, dep del bot ausente en local). Ver memoria `pre-existing-test-failures`.

## Notas de sesión `[MANUAL]`

<!-- Apuntes rápidos de sesión activa — borrar entre sesiones -->
