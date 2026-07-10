# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso
**Cierre de la sesión de La Pantalla** (6ª ronda sobre el mismo hilo de campo, empezó 2026-07-09): reparto de columnas, tinte por grade, meta reubicada al topbar, marco completo, fix de flicker de apertura, ancho real del form CURP, cristal aun más mate. `1fa4219` deployado a prod (2026-07-10), Robert queda de revisar visualmente.

## ▶ Con qué arrancas
Robert explícitamente pidió pivotar: **"ver que onda con los cambios recientes al cálculo del grade"** — la próxima sesión NO es más ajuste visual de La Pantalla (salvo que Robert reporte algo roto primero), es **auditar el algoritmo de grading V10** tras los cambios de la sesión pasada (M7 + A+ lifecycle + regla "aprobación reciente sana→A", commits `a71b9e8`/`58c990d` y ver `reference_analyzer_deploy_path` en memoria). Objetivo: confirmar que la distribución de grades en prod tiene sentido con los datos reales (no solo que los tests pasen) — pedir a Robert qué específicamente le preocupa antes de tocar código.

## 🧭 Recomendación de approach
1. Si Robert reporta algo roto de La Pantalla → atenderlo primero (es rápido, ya conocemos el terreno).
2. Si no: pedirle a Robert que aclare qué le inquieta del grading reciente (¿una cuenta específica gradeó raro? ¿la distribución total? ¿quiere ver ejemplos?) — no adivinar el ángulo, la BANDERA prohíbe estimar sin investigar.
3. Trae `docs/AUDIT.md` (capturas 2026-07-09/10 sobre grading) y `test_grading_a_plus_m7.py` como punto de partida — ya hay 16 tests y 2 backfills corridos (v10_m7, v10_m8).

## ⏳ Pendientes próximos
- [ ] **Robert: revisar visualmente en prod** los cambios de La Pantalla de esta sesión (6 rondas: anchos de columna, saldo más chico, Estado corregido, scroll en datos, meta al topbar, marco completo, fix de flicker, ancho real del form CURP, cristal aun más mate). Si algo se ve mal, screenshot + anotación como siempre.
- [ ] **Robert: confirmar que ya no parpadea/abre brusco** al cambiar de cuenta con La Pantalla abierta — el fix (`wasHidden` guard en `pantalla.js` `open()`) es lógicamente sólido (causa raíz confirmada leyendo el código: se re-disparaba toda la animación de entrada en cada click de fila) pero no se pudo probar en un navegador real esta sesión.
- [ ] **Robert: correr el `docker exec` de diagnóstico** de la cuenta `ljesus06` (ver bloque abajo) — desbloquea el bug de saldos desincronizados (Panel $0 / Pantalla $1850 / BetMexico $300 + retiros ausentes). Bloqueado desde 2026-07-06, sigue sin correr.
- [ ] **Migrar el bot de Telegram del monorepo a un repo Forgejo aislado** — pendiente de varias sesiones atrás.
- [ ] **Decisión Robert pendiente:** dedup de `account_touch` — ¿1/(operador,cuenta,día) o 1/cuenta/día?
- [ ] Reubicar el filtro "en uso" (quedó inaccesible al quitar Pool del strip). · Vista Actividad: `deposit_step`/`account_touch` caen al fallback genérico `·`.
- [ ] Marquesina "casino" y ositos-avatar — POSPUESTOS, no tocar sin que Robert lo pida.
- [ ] **Verificar en prod (Robert, cuando pruebe un depósito real):** el escenario migrado (`#depStage`) funciona igual en misión batch/matchmaker (varias cuentas a la vez) — no se probó ese caso, solo depósito único.
- [ ] untracked en raíz (NO commitear a propósito): `idea_vaga.txt` · `reports/` (xlsx con datos de tarjetas = sensible).

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

## ✅ Hecho esta sesión (2026-07-10, continuación de campo sobre `58c990d`)
- **`14af44c`** `fix(pantalla): reparto 2:1 movimientos/escenario · botones a esq inf-der · tinte por grade`
  - Fix de acomodo del deploy anterior (screenshot con flechas rojo/amarillo): `.pat-col-txns` a `flex:2 1 0`, `.pat-col-stage` `min-width:340px` (antes el escenario se comía todo el resto y apretaba el texto).
  - Controles (Fijar/En uso/Depositar) bajan de `.pat-topbar` a esquina inferior derecha, ancla `.pat-wrap` (no `.pat-topbar`, que tiene transform permanente por el cuaje líquido).
  - Tinte por grade: `data-grade` en `#pantalla`, overrides CSS por atributo reescriben `--pat-gold` family. Mapeo de hue igual al de `grade-dot`/`r-grade-X` en `style.css` (A+152 A160 B235 C75 D24).
- **`f885ec0`** `fix(pantalla): Estado roto (parseo de address sin comas) · reparto afinado · saldo chico · scroll · cristal difumina al grade`
  - **Bug real encontrado** (no era "falta el dato"): `estadoFrom()` (`pantalla_logic.js`) exigía direcciones separadas por coma con nombre completo del estado — las direcciones reales de `accounts.address` NO llevan comas (`"...23040 LA PAZ B.C.S."`, abreviatura postal SEPOMEX al final). Nunca matcheaba NINGUNA cuenta real. Reescrito con tabla de 32 abreviaturas + 10 asserts contra direcciones reales verificadas por `sqlite3` en KVM4.
  - Reparto afinado a ~55:45 (`.pat-col-txns:flex 1.35`, `.pat-col-stage:min-width 380` = viewBox real de las escenas SVG, no inventado). Saldo 36px→26px. Scroll propio en `.pat-col-ident` (antes el contenido se recortaba en silencio).
  - Cristal de La Pantalla se oscurece a la izquierda (legibilidad) y diluye al color del grade hacia la derecha — antes solo bordes/texto cambiaban, no el cristal. Brillo blanquecino recortado a la mitad.
- **`b6f16bb`** `fix(pantalla): meta al topbar · marco completo de la sheet · fix flicker de apertura`
  - Estado/cumpleaños/CURP suben de `.pat-col-ident` a `.pat-topbar-meta` (línea del nombre). Columna de datos: combo→saldo→divisor→guardado directo (sin `margin-top:auto`).
  - Marco completo de TODA la sheet (Robert corrigió alcance — no solo el recuadro de datos): border sube a `--pat-edge-h` + insets en los 4 lados (antes solo top/bottom).
  - Blanquecino recortado otra vez a la mitad.
  - **Bug real encontrado leyendo el código** (causa de "se abre brusco o parpadea raro"): `open()` en `pantalla.js` disparaba TODA la secuencia de entrada (clases + backdrop + scanline) en CADA click de fila, incluso con La Pantalla ya abierta con `backdrop-filter:blur(34px)` activo. Fix: `wasHidden = root.hidden` guarda si es apertura en frío; la secuencia solo corre entonces. Validado con skill `design-engineer` + blur del keyframe recortado (14px→9px, 5px→3px — animar `filter:blur()` propio encima de `backdrop-filter` constante duplicaba el costo de repintado).
- Los 3 commits: deployados a KVM4 (`betmexico-web`), verificados con `StartedAt` > mtime + health 200 + grep del código nuevo en disco en cada ronda. **Ningún cambio se verificó en navegador real** (Robert pidió deploy directo, "lo reviso allá") — pendiente su confirmación visual.
- **`1fa4219`** `fix(pantalla): form CURP con ancho REAL de la columna (no full-width) · cristal aun mas mate` (4ª ronda, ya cerrando)
  - **Bug real**: `data-curp-form` es hijo directo de `.pat-wrap` (flex-column, `align-items:stretch` default) → se estiraba al ancho COMPLETO de la sheet; input+botones (gob.mx/Cancelar/Guardar) terminaban pegados al borde derecho en vez de donde Robert marcó con línea amarilla (borde derecho de `.pat-col-ident`). Fix con MEDIDA REAL, no px inventado (regla `feedback_ui_ancla_medida_no_pixel_inventado`): `pantalla.js` `_syncIdentWidth()` mide `.pat-col-ident.getBoundingClientRect().width` post-render (rAF) y lo escribe como `--pat-ident-w` en `.pat-wrap`; CSS usa `width: var(--pat-ident-w, 300px)`. `.pat-form-row` gana `flex-wrap:wrap` de colchón.
  - Cristal 3ª pasada de "más mate": reflejo glass .012/.006→.005/.003, perlas nácar .05/.04→.03/.025, halo nácar interno .05→.025, filo superior nacarado del box-shadow .10→.06.
  - Deployado y verificado igual que los anteriores (StartedAt>mtime, health 200, grep de `_syncIdentWidth`/`pat-ident-w` en disco). **Tampoco verificado en navegador real.**

## 🔧 Decisiones tomadas
- **FIGMA FIRST para todo diseño UI:** Utilizar Figma para *todo* el mocking up. Mantenemos el diseño centralizado ahí para modificarlo y visualizarlo visualmente antes de pasarlo a código. Apoyados en el MCP `html-to-design` para importar/exportar componentes. Se acabaron las iteraciones visuales a ciegas con deploys directos a prod para features nuevas.
- **Deploy directo sin verificación en navegador cuando Robert lo pide explícitamente** ("deploya alla lo reviso") — no bloquear la iteración esperando un preview local si él va a revisar en prod de todos modos.
- **La Pantalla es de tamaño FIJO, sin ningún control de resize** — ni ella ni el panel KPI. No reabrir sin que él lo pida.
- **Botones de acción: esquina inferior derecha, no topbar** — el cuaje líquido deja transform en `.pat-topbar` que lo vuelve contenedor de posicionamiento; `.pat-wrap` no tiene transform → ancla limpia. La ✕ se queda arriba (convención universal de cierre).
- **Marco completo = toda la sheet, no un recuadro individual** — Robert corrigió esto explícitamente tras mi primera interpretación (que era sobre `.pat-col-ident`).
- **Combo SIEMPRE sin truncar/sin max-width** — al agregar scroll a `.pat-col-ident` se evitó a propósito `overflow-x:hidden`/`max-width` para no repetir el bug de truncado ya resuelto en sesión anterior.
