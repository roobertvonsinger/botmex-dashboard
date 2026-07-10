# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso
Sesión de rediseño de **La Pantalla** (4 iteraciones): (1) fix rate-limit (cerrado); (2) rediseño 3 columnas + escenario + tamaño fijo; (3) ajustes de layout (movimientos 2:1, botones esquina inf-der, min-width escenario); (4) grade-color por cuenta. **`58c990d` deployado a prod (2026-07-10), Robert revisa visualmente.**

## ▶ Con qué arrancas
Robert está validando los cambios de La Pantalla en prod (movimientos 2:1, botones abajo, grade-color). Si reporta ajuste visual, atenderlo primero. Revisar `docs/FRONTEND.md` sección "La Pantalla" antes de tocar nada para no repetir diagnósticos ya hechos.

## 🧭 Recomendación de approach
Si no hay pendiente de Pantalla: retomar el **bug de saldos desincronizados** (bloqueado hace 3 sesiones esperando 1 dato de prod que Robert no ha corrido — ver query abajo). Es el hilo más viejo sin cerrar.

## ⏳ Pendientes próximos
- [ ] **Robert: correr el `docker exec` de diagnóstico** de la cuenta `ljesus06` (ver bloque abajo) — desbloquea el bug de saldos desincronizados (Panel $0 / Pantalla $1850 / BetMexico $300 + retiros ausentes). Bloqueado desde 2026-07-06.
- [ ] **Bug saldos:** confirmado en código el síntoma A (staleness — La Pantalla no se refresca tras prewarm; solo el depósito emite `account_refreshed`). B/C (balance/retiros) = hipótesis del checker (monorepo) — NO tocar sin el dato de prod.
- [ ] **Migrar el bot de Telegram del monorepo a un repo Forgejo aislado** — pendiente de varias sesiones atrás.
- [ ] **Del cierre 2026-07-05 (sigue abierto):** validar en prod los 4 ajustes del feed KPI Logs + jerarquía combo/nombre de Cuentas a la mano.
- [ ] **Decisión Robert pendiente:** dedup de `account_touch` — ¿1/(operador,cuenta,día) o 1/cuenta/día?
- [ ] Reubicar el filtro "en uso" (quedó inaccesible al quitar Pool del strip). · Vista Actividad: `deposit_step`/`account_touch` caen al fallback genérico `·`.
- [ ] Marquesina "casino" y ositos-avatar — POSPUESTOS, no tocar sin que Robert lo pida.
- [ ] **Verificar en prod (Robert, cuando pruebe un depósito real):** el escenario migrado (`#depStage`) funciona igual en misión batch/matchmaker (varias cuentas a la vez) — no se probó ese caso, solo depósito único. Si se ve raro, avisar.
- untracked en raíz (NO commitear a propósito): `idea_vaga.txt` · `reports/` (xlsx con datos de tarjetas = sensible).

### 🔎 Query de diagnóstico del bug de saldos (correr en prod, solo lectura)
```bash
docker exec betmexico-web python3 -c "
from app import db
with db() as c:
    r=c.execute(\"SELECT email,balance_real,balance_bonos,balance_total,last_checked_at,last_deposit_date FROM accounts WHERE email LIKE 'ljesus06%'\").fetchone()
    print('ACCOUNT:', dict(r) if r else None)
    t=c.execute(\"SELECT txn_date,amount,status,txn_type,gateway FROM account_transactions WHERE account_email LIKE 'ljesus06%' ORDER BY txn_date DESC LIMIT 15\").fetchall()
    print('TXNS:', len(t)); [print(dict(x)) for x in t]
"
```
Decide: BD tiene $0 o $1850 (cuál caché) · ¿hay retiros `txn_type=2`? · si el checker trajo saldo/retiros vacíos → bug del bot (monorepo), no del dashboard.

## ✅ Hecho esta sesión (2026-07-09/10)
- **`cbe9db5`** (rate-limit no-banco, arrastrado de sesión anterior): `app.py`+`deposits.py`+`static/{pantalla,activity_logic}.js`, migración 273 registros reclasificados.
- **`e42376a`** `feat(pantalla): rediseño 3 columnas + escenario de depósito migrado + tamaño fijo anclado a Sistema`
  - **Layout**: La Pantalla pasa de 2 zonas (movimientos estirados a todo el ancho, header que se iba con el scroll) a 3 columnas reales — `.pat-topbar` (nombre+acciones, full width) → `.pat-columns` (`.pat-col-ident` | `.pat-col-txns` compacta con header FIJO | `.pat-col-stage`).
  - **Escenario de depósito migrado**: el progreso (animaciones SVG login/captcha/processing/done + %/sub, antes invisible en la mini-pantallita del panel flotante) se movió a `#depStage`, re-parenteado por JS a la columna derecha de La Pantalla. CSS re-scopeado de `#depos` a `#depStage` (~285 líneas). `depos.js` abre La Pantalla automático si estaba cerrada al arrancar un depósito.
  - **Tamaño fijo, CERO drag/collapse** (pedido explícito de Robert en 2 rondas): se eliminaron `.lp-vgutter`, `.pantalla-banda`, `KpiPanel.toggle/expand/collapse/applyH`. El alto lo fija `ANCHOR_H` (`app.js`) UNA vez al cargar — fórmula pura `PantallaLogic.anchoredPanelH()` (testeada) que alinea "Sistema" (menú) con "Cuentas" (tabla), verificado con `getBoundingClientRect` real, no a ojo.
  - Bug encontrado de paso (documentado en `docs/ERRORS.md`): el header "Movimientos" vivía dentro del contenedor scrolleable y desaparecía al bajar la lista.
  - Docs: `FRONTEND.md` (sección La Pantalla reescrita completa) + `ERRORS.md`. Tests: `pantalla_logic.test.js` +4 casos de `anchoredPanelH`. 5/5 suites JS verdes en cada iteración.
  - **Deployado y validado parcialmente por Robert en prod** (confirmó que Sistema↔Cuentas quedó alineado).
- **`58c990d`** `feat(pantalla): grade-color por cuenta · movimientos 2:1 · botones esquina inf-der` — sesión 2026-07-10 (campo continuo):
  - **Movimientos 2:1**: `.pat-col-txns` pasa de `flex:0 1 420px` a `flex:2 1 0; min-width:380px` — las transacciones toman 2/3 del espacio libre, el escenario 1/3.
  - **Botones abajo**: `.pat-actions` (Fijar/En uso/Depositar) sacado de `.pat-topbar` y anclado a `position:absolute` esquina inferior derecha (`right:18px; bottom:14px; z-index:6`). Cuelga de `.pat-wrap` (no `.pat-topbar` que tiene transform por cuaje). La ✕ de cerrar se queda arriba-derecha.
  - **Grade-color**: `renderPantallaHead` setea `data-grade="APlus|A|B|C|D|U"` en `.pat-wrap`. CSS overrides por selector de atributo reescriben `--pat-gold`/derivados. Paleta: A+ h152, A h160, B h235, C h75, D h24, U h95. Mesh de fondo (`.pantalla-sheet`) intocado.
  - **Escenario**: `min-width:340px` para que el guide de 4 pasos no se apriete.
  - Deployado + restart + health 200. Robert revisa en prod.

## 🔧 Decisiones tomadas
- **La Pantalla es de tamaño FIJO, sin ningún control de resize** — ni ella ni el panel KPI. No reabrir sin que él lo pida.
- **El alto se calcula, no se inventa**: `ANCHOR_H` mide el delta real entre el label "Sistema" del menú y el header "Cuentas" de la tabla — cualquier cambio futuro al sidebar o al filterbar recalcula solo, sin tocar código.
- **`#depStage` se re-parentea, no se duplica**: un solo bloque de escenas SVG, movido por JS entre el panel y La Pantalla según dónde deba pintar.
- **Botones de acción: esquina inferior derecha, no topbar** — el cuaje líquido deja transform en `.pat-topbar` que lo vuelve contenedor de posicionamiento; `.pat-wrap` no tiene transform → ancla limpia. La ✕ se queda arriba (convención universal de cierre).

## 🖥️ Estado del sistema al cerrar
- **web** up (reiniciado, último restart limpio con 58c990d) · **bot** up (esperado) · **health** 200 (924 cuentas) · `/api/version` bumpeado
- **pool** = 202 proxies (200 DataImpulse + 2 NodeMaven) · cero errores en 12h
- Rama `main` == `58c990d` (pusheado a Forgejo), prod consistente con el repo.
