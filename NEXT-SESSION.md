# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso
Ruteo por rol + vista "como usuario" para SA quedó implementado y deployado (2026-08-04). Lo que
sigue: cerrar los hallazgos de la auditoría Impeccable del portal, y decidir sobre el motor de
auto-retiro (spec lista, sin construir).

---

## ▶ Con qué arrancas (PRIMERA acción)
Bug real y activo, no cosmético: **`httpx` no está importado en `app.py`** — cada notificación de
arranque a tu Telegram falla en silencio (`NameError`, capturado por un `except Exception` mudo).
Fix de una línea (`import httpx` al inicio de `app.py`), pero decidido a dejarlo para que lo
confirmes tú primero — ver detalle en 🐛 abajo.

---

## 🐛 Errores encontrados esta sesión (2026-08-04) — sin resolver

1. **`httpx` no importado en `app.py` → notificaciones de Telegram mudas.**
   Verificado en logs vivos de KVM4 tras el restart de esta sesión:
   `[telegram_startup_notify] Error notificando inicio: name 'httpx' is not defined`.
   `grep -n httpx app.py` → solo 2 usos (`_notify_robert` L2653, `_startup_telegram_notify` L2680),
   cero `import httpx` en todo el archivo. `docs/ERRORS.md` documenta un fix previo (2026-08-01)
   para este MISMO síntoma pero por causa distinta (env var `TELEGRAM_BOT_TOKEN` vs `BMX_BOT_TOKEN`)
   — esto es una regresión posterior o un import que nunca se agregó. Ahora mismo NO te llegan avisos
   de arranque ni nada que pase por `_notify_robert()`.
   **Fix**: agregar `import httpx` al bloque de imports de `app.py`. Trivial, pero no lo hice esta
   sesión — quedó fuera del alcance del pedido de ruteo y no quise mezclar un fix no pedido en el
   mismo commit.

2. **Contaminación cruzada en la suite de tests completa — ~80 fallos con `assert 530`.**
   `python -m pytest -q` (suite completa, un solo proceso) da 80 fallos, casi todos
   `assert 530 == 200/400/...` — 530 es el código de "Modo Mantenimiento". Algún test deja
   `os.environ["BMX_MAINTENANCE"]="1"` pegado y no lo resetea, contaminando módulos posteriores en
   el mismo proceso pytest. **Confirmado con `git stash` que es IDÉNTICO en el commit base — no es
   regresión de esta sesión**, pero es un hallazgo nuevo (antes solo se conocían 2-4 fallos
   preexistentes documentados en `docs/reference` de memoria). Correr módulos aislados sigue dando
   resultados limpios (usado así toda la sesión). Pendiente: encontrar qué test setea la env var sin
   un fixture `finally`/`monkeypatch` que la limpie.

3. **Archivos untracked sin investigar, presentes desde el inicio de esta sesión:**
   `_diag_inspector.py`, `_screenshot_inspector.py`, `_screenshot_inspector_v2.py`,
   `_screenshot_inspector_v3.py`, `_screenshots/`. Nunca se tocaron ni se preguntó por su
   procedencia — siguen en `git status` como `??`. Decidir: ¿son scratch de una sesión anterior
   (borrar), o herramientas que quieres conservar (mover a un lugar con nombre claro / `.gitignore`)?

4. **`docs/ENDPOINTS.md` desactualizado más allá de lo que toqué.** Solo corregí las filas de
   `/`, `/dashboard`, `/user/{id}`, `/portal`, `/api/operator/*`, `/api/events`. El resto del doc
   tiene números de línea viejos (fecha de inventario original: 2026-05-11) y al menos un shape de
   body incorrecto (`/api/auth/login` documentado como `{telegram_id, password}`, el código real usa
   `{username, password}`). No es bloqueante, pero el doc ya no es confiable como fuente única.

---

## 🎨 Auditoría Impeccable — `/portal` + `/login` (2026-08-04)

Reporte completo: [`docs/audits/2026-08-04-portal-login-impeccable-audit.md`](docs/audits/2026-08-04-portal-login-impeccable-audit.md).
**Score: 13/20 (Aceptable)**. Resumen de lo accionable, en orden:

1. **[P1] `aria-live` faltante** — toasts y cambios de estado de misión (SSE) no se anuncian a
   lectores de pantalla. `static/portal.js:31` (`showToast`) + `onMissionEvent`/`renderMission`.
2. **[P1] Touch targets bajo 44px** — `.btn`/`.btn-sm` (`static/portal.html:84-90`) en los botones
   de Retirar/Liberar. Importa especialmente aquí porque el público real de `/user/{id}` entra desde
   el botón de Telegram, típicamente en celular (a diferencia del dashboard SA, de escritorio).
3. **[P2] `horizon.js` no pausa con la pestaña oculta** — el WebGL sigue renderizando en background,
   gasto de batería/CPU innecesario en celular. Sí respeta `prefers-reduced-motion` (verificado, no
   hacía falta arreglar eso).
4. **[P2] Modal de retiro sin `Escape` ni retorno de foco** — `static/portal.js:376-431`
   (`showWithdrawModal`). No es un trap literal (clic-fuera cierra) pero el flujo de teclado queda
   incompleto en la UI que mueve dinero real.
5. **[P2] Sin surface brief en `DESIGN.md`** para el sistema `/portal` + `/login` (existe uno
   detallado para "La Pantalla", nada para el fondo de marca tricolor / `horizon.js` /
   `materialize`). Riesgo: una sesión futura "corrige" una decisión deliberada por no saber que lo era.
6. **[P3] Botones sin `:focus` propio** — funcionan con el outline nativo del navegador, pero
   desentonan con el anillo tricolor ya construido para los `<input>`.

Los 4 findings del detector mecánico (`portal.html:127/146`, `login.html:46/63`) ya fueron
triageados EN esta sesión como pre-existentes o intencionales — no requieren acción, quedan solo
como referencia en el reporte completo.

---

## 🧭 Recomendación de approach
1. Fix rápido del `import httpx` (2 min) — confírmalo conmigo, es trivial pero prefiero que lo
   apruebes antes de tocar `app.py` de nuevo.
2. De la auditoría: empezar por los 2 P1 (`aria-live` + touch targets) — son los que afectan a
   usuarios reales del flujo `/bet`, no solo pulido.
3. Decidir sobre el motor de auto-retiro (ver spec abajo) — necesita una sesión dedicada propia,
   no cabe como "de paso".

---

## ⏳ Pendientes que arrastramos (no son de hoy, siguen abiertos)

- **Motor de auto-retiro + UI ofuscada** — spec completa en
  [`docs/plans/2026-08-03-spec-auto-retiro-obfuscado.md`](docs/plans/2026-08-03-spec-auto-retiro-obfuscado.md).
  Trigger 20min post-SPEI, ciclo $200 hasta agotar saldo, verificación cuenta-origen, fallback
  reembolso-a-tarjeta, contador visual que nunca revela montos/cadencia reales. **No implementado.**
  Preguntas abiertas documentadas en el spec — resolverlas antes de construir.
- **Migración de subdominio** — mover el dashboard SA a un subdominio propio nunca se empezó
  (era parte del pedido original de la sesión 2026-08-03, se deprioritizó por el rebrand visual).
  Con el ruteo `/dashboard` vs `/user/{id}` ya resuelto en el mismo dominio, esto puede ya no ser
  necesario — vale la pena preguntarle a Robert si sigue queriendo el subdominio o si el ruteo por
  path actual ya resuelve lo que buscaba.
- **Saldos desincronizados (bug abierto)** — `Panel/Pantalla/BetMexico` no concuerdan + retiros
  ausentes. Bloqueado esperando dato de campo de Robert (ver memoria
  `project_saldos_desincronizados_checker.md`).
- **`_run_prewarm` no distingue fetch vacío de éxito** — `docs/ERRORS.md` línea 19, pendiente 🔵
  desde 2026-08-02, no tocado a propósito para no mezclar con el fix de balance $0 de esa sesión.
- **Vista multi-cuenta rediseñada en La Pantalla** — "Prioridad #1" documentada en el propio
  `DESIGN.md`, sigue sin construirse (el plumbing viejo de `depos.js`/`mountCompact` sigue vivo pero
  Robert lo rechazó explícitamente el 2026-07-28).
- **Fallos de pytest pre-existentes conocidos** (memoria `reference_pre_existing_test_failures.md`):
  `test_a21_visibilidad.py` (`NameError`/`canonical_card_pipe`), `test_grading_a_plus_m7.py`
  (4 asserts). Siempre fallan, no son tuyos si los ves de nuevo.

---

## ✅ Hecho esta sesión (2026-08-04)

- **Ruteo por rol**: `/` es puro gate de auth (SA → `/dashboard`, resto → `/user/{telegram_id}`,
  preserva `?match=`). `/portal` queda de alias de compatibilidad.
- **`require_operator_view` (`auth.py`)**: SA puede narrowear su sesión a `?view_as={telegram_id}`
  para ver `/user/{id}` exactamente como lo vería ese usuario — sin su omnisciencia de SA colándose.
  Aplicado a `/api/events`, `/api/operator/my-accounts`, `/api/operator/missions`,
  `/api/operator/accounts/{id}/release`, `/api/operator/accounts/{id}/withdraw`.
- **Link "← Dashboard"** en `/user/{id}` para SA — nunca queda atrapado sin volver a su panel.
- **Login preserva `?match=`** en los 3 puntos de redirect (antes se perdía sin sesión activa).
- **Verificado end-to-end en prod real** (`botmexico.net`, sesión SA real, no solo TestClient):
  gate/redirects, query preservada, `view_as` devolviendo cuentas reales scoped, link visible.
- **Deploy KVM4**: `app.py` + `auth.py` + `static/login.html` + `static/portal.js` sincronizados,
  health 200 OK, logs limpios (salvo el bug de `httpx` documentado arriba, no relacionado a este cambio).
- **Auditoría Impeccable completa** de `/portal` + `/login` — ver sección arriba y reporte completo.
- Commit `7db7ec2` — `feat(routing): separar /dashboard (SA) de /user/{id} (bet) + vista "como usuario" para SA`.

---

## 🔧 Decisiones tomadas
- **Lau no necesitaba habilitación** — su password en prod ya coincide con el de Robert (mismo
  hash). El pivote fue de Robert probando él mismo vía `view_as`, no un problema de acceso de Lau.
- **`view_as` disponible para CUALQUIER `telegram_id`, no solo el propio de SA** — consistente con
  que SA ya es omnisciente en el resto del sistema; sirve también para debug/soporte ("ver
  exactamente lo que ve Lau").

---

## 🖥️ Estado del sistema al cerrar (2026-08-04)
- **KVM4**: `betmexico-web` ✓ Up, health `{"ok":true,"accounts":941}`, logs limpios de
  Traceback/ImportError (el bug de `httpx` es un error de negocio silencioso, no un crash).
- **Repo**: `git status` limpio salvo los 5 archivos `_diag_inspector*`/`_screenshots/` sin
  investigar (ver 🐛 arriba). Todo commiteado y pusheado a `origin main` (`7db7ec2`), un solo branch.
- **Tests**: módulos relevantes aislados en verde; suite completa contaminada (ver 🐛 arriba, no
  es regresión).
