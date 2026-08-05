# Handoff — Rediseño + hardening completo del portal `/bet` (botmex-dashboard)

> Prompt autocontenido para orquestar con agentes en otra herramienta (OpenCode u otra).
> No asume contexto de conversación previa — todo lo que necesitas está aquí o referenciado por ruta de archivo.

---

## 0. Quién sos y qué NO hiciste todavía

Sos el orquestador de una tarea de implementación completa: diseño, código, tests, optimización,
review y deploy del portal de operadores de `botmex-dashboard` (repo Forgejo independiente
`Robertvs/botmex-dashboard`, FastAPI + SQLite + vanilla JS sin build step, sin framework frontend).

Una sesión anterior (Claude Code) hizo una pasada de bug-fixing reactivo sobre este portal SIN
verificación visual real (nunca tomó una captura de pantalla — el navegador en ese entorno no
compositaba frames) y sin re-chequear contra el brief de diseño original antes de seguir
construyendo. El resultado: varios bugs de lógica reales sí se encontraron y corrigieron, pero el
diseño visual quedó sin evaluar por nadie con ojos reales hasta que el dueño del producto lo vio en
producción y lo describió como "parecen barajitas mal hechas de turista mundial" y "diseño de
primaria". **No repitas ese patrón.** Cualquier cambio visual que hagas necesita verificación con
capturas de pantalla reales (no solo lectura de DOM/CSS, no solo un audit de código), y necesitás
**parar y mostrar evidencia visual concreta en checkpoints definidos ANTES de escalar un patrón a
todo el sistema** — no construir 10 pantallas con la misma idea sin haber confirmado que la primera
se ve bien.

---

## 1. Restricciones duras (no negociables, ya causaron bugs reales por violarse)

1. **Login SIEMPRE obligatorio para no-SA.** `/user/{id}` exige sesión de `botmexico.net` (usuario/
   contraseña PROPIOS del sistema, `POST /api/auth/login`). Nunca hay landing sin sesión desde un
   link de Telegram ni de ningún otro lado — verificalo vos mismo en `app.py` (`user_portal_page`,
   `_auth.create_session` solo se llama en los handlers reales de login) antes de asumir lo contrario.
2. **"Sin password" es SOLO sobre la contraseña de la cuenta de BetMexico** (el operador nunca la ve
   ni la usa — todo corre server-side vía JWT persistido). NO es "sin login al dashboard". Confundir
   esto ya causó un bug real: un modal mostraba literalmente el texto "Retiro sin password" al
   operador, porque una implementación previa copió un encabezado interno del brief de diseño
   (`docs/plans/2026-08-02-handoff-diseno-portal-bet.md`, sección "Modales de Acción (Sin
   Contraseña)") directo al copy visible. Ver desambiguación completa en `PRODUCT.md`.
3. **Nunca enmascarar datos sensibles**: tarjetas (`num|mm|yy|cvv` pipe puro), combos
   (`email:password`), CLABEs SPEI — SIEMPRE texto plano, copiado instantáneo es la prioridad. Este
   es trabajo de testing/operación propia autorizada, no cara pública.
4. **Anti-detección**: el operador NUNCA debe ver la cadencia real de depósitos automáticos ($150
   cada 60s) ni montos/timers exactos — cualquier feedback de progreso debe estar desacoplado de los
   valores reales (interpolación visual, no countdown real). Esto ya se rompió una vez y se corrigió
   — no lo vuelvas a romper.
5. **Copy de retiro nunca sobreclama entrega**: `status_api:6` de BetMexico significa que BetMexico
   EJECUTÓ el retiro, no que ya aterrizó en el banco del operador. El copy correcto es siempre
   "procesado — confirma en tu banco", nunca "liberado"/"entregado".
6. **Capas operador vs backend**: nunca se filtran internals (stack traces, SQL, nombres de proxy/IP,
   jerga técnica, IDs de misión, tags técnicos) a la superficie del operador. Errores siempre
   humanizados.
7. **Grade A+/A/B/C/D/U es vocabulario de producto fijo** (mapeo de color ya establecido en toda la
   app) — no reinventar el código de color por superficie.
8. **Visibilidad por rol**: operadores no se ven entre sí; SA ve todo y navega cualquier `/user/{id}`
   vía `?view_as=`.
9. **Mobile-first para el portal** (`/user/{id}`): los operadores llegan desde Telegram, en celular.
   Touch targets ≥44px reales (medidos, no solo declarados en CSS).
10. **Norte del producto**: "frictionless" — toda decisión de diseño se mide por si agrega o quita
    fricción, tanto al operador bajo presión de tiempo como al propio desarrollo (no mezclar
    conceptos/IDs/tags que no aportan valor real a nadie).

---

## 2. El requisito central que falta construir: portal de UNA SOLA VISTA

Esta es la tarea de diseño+implementación más grande y explícita pendiente. Está documentada como
requisito en `PRODUCT.md` (sección "Portal del operador") pero **NO implementada todavía**:

- El portal (`static/portal.html` + `static/portal.js`, ruta `/user/{id}`) hoy tiene DOS vistas
  separadas: "Misión Activa" (con `mission_id` visible, progress bar, matches apareciendo) y "Mis
  Cuentas" (grid de cards). Debe ser **UNA SOLA vista**, sin IDs de misión, tags, ni conteos de
  fallidos visibles — eso es ruido, no información accionable para el operador.
- **Regla de visibilidad real**: el operador solo debe ver cuentas con un depósito **ya aterrizado**
  o **actualmente en proceso**. Si un intento de depósito falla, esa cuenta debe **desaparecer por
  completo** de su vista y de su acceso — no queda como card "fallida", no se muestra un stat de
  fallos en ningún resumen.
- Hoy el backend expone esto vía `GET /api/operator/my-accounts` (`app.py`, función
  `operator_my_accounts`) filtrando por `deposit_attempts.status='approved'` — confirmá si esa
  query ya implementa la regla de visibilidad correcta o si hace falta ajustarla para cubrir también
  el caso "en proceso" (misión corriendo, aún sin resolver) sin exponer el estado "failed" en ningún
  lado del payload que el frontend consuma.
- Esto es un rediseño real de arquitectura de información, no un ajuste de CSS. Necesita su propia
  ronda de diseño (qué contenido mínimo por cuenta, cómo se comunica "en proceso" sin mission_id
  visible, cómo transiciona una cuenta de "en proceso" a "con depósito aterrizado" sin recargar la
  página ni mostrar un salto brusco) antes de tocar código.

---

## 3. Calidad visual — por qué el audit anterior no sirvió

Una auditoría de código (`docs/audits/2026-08-04-impeccable-portal.md`, score 16/20) evaluó
accesibilidad/performance/responsive/theming/consistencia de implementación **leyendo CSS**, no
mirando el render real. Por diseño, ese tipo de auditoría **no puede** detectar que algo "se ve
barato" — y no lo detectó. El dueño del producto sí lo vio en producción real. Conclusión: cualquier
trabajo de diseño en esta sesión necesita **capturas de pantalla reales verificadas visualmente**,
no solo lectura de código ni extracción de texto del DOM. Si tu entorno tiene una herramienta de
browser/captura que funciona, úsala en cada iteración visual. Si no funciona (como pasó en la sesión
anterior — el pane no compositaba frames), decilo explícitamente y pedile a Robert que confirme
visualmente en checkpoints concretos — nunca declares "se ve bien" sin haber visto pixeles reales
vos o él.

Dirección de diseño sugerida (no prescriptiva — es una pista, no un mandato): lo actual son cards
chicas (~280-300px), texto apretado en 10-13px, sin jerarquía fuerte, sin foto/hero, sensación de
"lista de stats" — de ahí la comparación con álbum de estampitas. El brief original
(`docs/plans/2026-08-02-handoff-diseno-portal-bet.md`, **leer con la nota de corrección al inicio**)
pedía "Cyber-Mexicana táctica, limpia, veloz" con saldo real "gigante", shimmer/skeleton en cargas,
glow con propósito — varias de esas piezas nunca se construyeron (no hay skeleton loading, el saldo
es 24px que no es "gigante" para un wallet). Usalo como referencia de tono, no como spec literal —
sus tokens de color (`--bg-dark: #0d1117` etc.) NO coinciden con los que terminó usando
`portal.html` (`--bg: #0b0e12` etc.) y la identidad de marca cambió de "cactus 🌵" a bandera
tricolor MX — confirmá con `DESIGN.md` (sección "Surface: /portal + /login") cuál es la identidad
vigente antes de asumir cuál manda.

---

## 4. Estado actual del código (verificado, no asumido)

- **Branch**: `main`, HEAD en `484b002` al momento de este handoff. `git status` limpio.
- **Tests**: `python -m pytest -q` → 383 passed, 0 failed. Correr esto ANTES de empezar y después
  de cada cambio — sin regresión es no-negociable.
- **Sin suite de tests JS** (vanilla, sin build step) — la verificación de frontend es manual/
  navegador, no hay `jest`/`vitest` configurado. Si agregás lógica JS no trivial, considerá si vale
  la pena introducir un harness mínimo o si la verificación en navegador real basta.
- **Deploy**: KVM4, contenedor `betmexico-web` sirve el dashboard+portal (`docker-compose.yml`),
  contenedor separado `betmexico-mock-bot` sirve `telegram_bot_mock/bot.py` — que pese al nombre
  "mock" es el bot REAL de producción para `/bet` (confirmado). El bot legacy en el monorepo
  (`Proyectos/BetMexico/Telegram/betmexico_bot.py`) NO implementa `/bet`, no lo toques por esto.
- **Bugs ya corregidos esta sesión (no los reintroduzcas)**: ver `docs/ERRORS.md` (entries del
  2026-08-04) — timer de poll de retiro por cuenta (no global), copy de retiro no-sobreclamante,
  alertas de mismatch tarjeta/dígitos, CSS que peleaba contra interpolación rAF, sentinel `'N/A'` de
  CURP impreso literal, botón Retirar habilitado sin saldo real, modal con instrucción interna
  expuesta como copy.
- **Archivos clave**: `static/portal.html`, `static/portal.js`, `static/login.html`, `app.py`
  (rutas `/`, `/login`, `/user/{id}`, `/dashboard`, endpoints `/api/operator/*`), `account_refresh.py`
  (gate `withdrawal_ready`), `auto_deposit.py` (matchmaking/grading — no auditado a fondo todavía).
- **Docs a leer, en este orden**: `PRODUCT.md` → `DESIGN.md` → este documento →
  `docs/plans/2026-08-02-handoff-diseno-portal-bet.md` (con su nota de corrección) →
  `docs/AUDIT.md` (estado función por función) → `docs/ERRORS.md` (bugs ya cerrados, no repetir) →
  `docs/FRONTEND.md` (mapa de arquitectura frontend) → `docs/audits/2026-08-04-impeccable-portal.md`
  (hallazgos de a11y pendientes en `login.html`: labels sin `for`/`id`, sin `aria-live`, jerarquía
  tipográfica plana, sin breakpoint responsive).

---

## 5. Proceso esperado (el ciclo completo que se pidió)

1. **Diseño primero, con checkpoint de aprobación visual antes de escalar.** Proponé la dirección
   visual del portal de una sola vista (tokens, layout, cómo se comunica "en proceso" sin IDs),
   construí UN ejemplo real (no 10 pantallas de una vez), tomá captura de pantalla real, y —si tenés
   forma de preguntarle a Robert— confirmá antes de replicar el patrón a todo el portal. Si no podés
   preguntar en el momento, documentá la decisión y el razonamiento en `DESIGN.md` con la misma
   densidad que ya tiene esa sección.
2. **Implementación TDD donde hay lógica real** (backend: filtrado de cuentas, gate de visibilidad).
   El frontend vanilla no tiene TDD formal — verificación en navegador real con capturas.
3. **Tests**: suite completa verde antes de cada commit relevante. Si tocás `operator_my_accounts` u
   otro endpoint, agregá/actualizá los tests de `test_*.py` correspondientes.
4. **Optimización**: nada de animaciones basadas en propiedades de layout (`width`/`height`/`top`)
   sin justificar por qué no usar `transform`/`opacity` — ya hubo un bug real de esto en esta misma
   superficie (transición CSS peleando contra una interpolación JS).
5. **Review adversarial** antes de dar por cerrado: no solo "¿pasa los tests?" sino "¿qué pasa si dos
   eventos llegan casi al mismo tiempo?", "¿qué pasa si el operador tiene 40 cuentas en vez de 3?",
   "¿qué pasa si recarga la página a medio depósito?" — los bugs reales de esta sesión salieron de
   ese tipo de pregunta, no de leer el happy path.
6. **Deploy a KVM4** solo después de suite verde + verificación visual real + aprobación (si el canal
   con Robert está disponible; si no, dejalo listo y documentado para que él dispare el deploy).
   Smoke test funcional real post-deploy (no solo `/health`) — ver `docs/protocols/deploy-checklist.md`
   si existe, o al menos confirmar el flujo real end-to-end contra el servidor desplegado.
7. **Documentación al cierre**: actualizar `docs/AUDIT.md` (estado función por función),
   `docs/ERRORS.md` (si encontrás bugs nuevos), `docs/FRONTEND.md` (arquitectura del portal
   rediseñado), `DESIGN.md` (la nueva dirección visual, con el mismo nivel de detalle que ya tiene),
   y dejar un `NEXT-SESSION.md` actualizado al cierre con: qué quedó hecho, qué quedó pendiente, y
   cualquier decisión de diseño tomada sin confirmación directa de Robert marcada explícitamente
   como tal para que él la revise.

---

## 6. Qué NO hacer

- No reconstruyas el motor de auto-retiro (`docs/plans/2026-08-03-spec-auto-retiro-obfuscado.md`) —
  está explícitamente parqueado, no lo reactives sin que Robert lo pida de nuevo.
- No toques `Proyectos/BetMexico/Telegram/` (monorepo, bot legacy) — no es donde vive `/bet`.
- No inventes un mínimo de retiro en pesos ($1, etc.) sin evidencia — la validación real es
  "monto > 0 y ≤ saldo disponible", ya corregido esta sesión.
- No declares "se ve bien" o "diseño impecable" sin haber visto una captura de pantalla real vos
  mismo. Un audit de código no es un audit visual.
