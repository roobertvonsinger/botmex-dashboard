# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso
Plan anti-abuso completo (Fases 1-3 + 5 frentes extra de UX/bugs) cerrado y deployado 2026-07-16. Sin objetivo activo abierto — la sesión que sigue arranca de pendientes puntuales, no de una fase en curso.

## ▶ Con qué arrancas
Ninguna acción de código pendiente. Primer punto: **F2.3** — verificar en prod con datos reales que el refresh manual de 1 cuenta con JWT expirado sí actualiza `balance_real` (comando SQL abajo, en Pendientes). Después: decidir si arrancar la migración del bot a Forgejo (ya planeada, ver Pendientes) o atender el bug viejo de saldos desincronizados.

## 🧭 Recomendación de approach
Prioriza F2.3 (5 min, cierra el loop de verificación end-to-end del fix de balance) antes de abrir cualquier frente nuevo — es la única pieza de esta sesión sin evidencia de campo post-deploy. La migración del bot a Forgejo y el bug de saldos desincronizados son ambos de 1 sesión dedicada cada uno; no mezclar.

## ⏳ Pendientes próximos
- [ ] **F2.3 — verificación de campo del fix de refresh** (comando listo, no ejecutado por requerir cuenta real + clic de operador):
  ```bash
  KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"; HOST="root@100.77.154.31"
  ssh -i "$KEY" $HOST 'docker exec betmexico-web sqlite3 /data/betmexico_accounts.db "SELECT id,email,balance_real,jwt_expires_at,updated_at FROM accounts WHERE jwt_expires_at < strftime(\"%s\",\"now\") LIMIT 1;"'
  # anotar id/balance_real, hacer clic ↻ en esa fila desde la UI real, luego re-consultar el mismo id y confirmar updated_at más reciente.
  ```
- [ ] **Migrar el bot de Telegram a repo Forgejo aislado** — plan detallado en la sección de abajo (F1.3), 1 sesión dedicada, no mezclar con cambios funcionales.
- [ ] **Robert: correr query `ljesus06`** para destrabar el bug de saldos desincronizados (pendiente viejo, sigue abierto — ver memoria `project_saldos_desincronizados_checker`).
- [ ] Observar el jwt_keeper 24-48h más (deployado 07-14, sigue en observación).
- [ ] Actualizar la lista de fallos pre-existentes en memoria: son **21**, no 16 (ver Decisiones tomadas abajo) — memoria `reference_pre_existing_test_failures` desactualizada.

### Plan de migración bot Telegram → Forgejo (documentado, no ejecutado)
Crear `Robertvs/betmexico-bot` en Forgejo, `git init` sobre `Proyectos/BetMexico/Telegram/`, filtrar historial con `git filter-repo` igual que se hizo con botmex-dashboard, separar `shared/` (hoy compartido por import directo con el dashboard) en un paquete versionado o duplicado explícito, y actualizar `docs/protocols/deploy-protocol.md` con el nuevo flujo de deploy (ya no `scp` directo a `/docker/betmexico/code/` sino build+push de imagen).

## ✅ Hecho esta sesión (2026-07-16) — plan `docs/superpowers/plans/2026-07-16-6-frentes-anti-abuso-y-ux.md`, rama `feature/6-frentes-anti-abuso-ux` mergeada a `main`
- **F1** (`Proyectos/BetMexico/Telegram/`, monorepo, excepción autorizada): `is_superadmin(1341812706)` nuevo en `betmexico_config.py`; `hit_detail_cb`/`view_txns_cb` en `betmexico_search.py` restringidos a SA-only (antes `ADMIN_USERS` de 3 personas + subadmin tenían visibilidad global de combo/balance/transacciones vía bot). `/check` (ingestión+match) intacto. Deployado a KVM4, restart limpio verificado.
- **F2** (`cac2fc5`): root-cause del guard anti-abuso (`4c42517`) que bloqueaba también el refresh manual de 1 sola cuenta, no solo el bulk — fix `prewarm.py:732`. TDD, 32 tests verdes. Entry nueva en `docs/ERRORS.md`.
- **F3** (`db35640`): restaurado copy-on-click del combo email:password en la tabla (`app.js`), sin romper selección múltiple Ctrl/Shift+click.
- **F4** (`93f91f0`): exclusión mutua real de estado entre el panel de depósitos flotante y La Pantalla (`isOpen()` nuevo en `DeposWindow`, ya no `relayout()` ciego) — resuelve el pisado visual z-index 200 vs 40.
- **F5**: verificado que el stage de depósito ya vive migrado en `#patStageSlot` (arriba-derecha de La Pantalla) desde una sesión previa — premisa original del pedido (migrar a `#pantallaScene`) era incorrecta, ese slot es para el Task 7 pendiente (detalle de un movimiento). Sin cambios de código necesarios a 1920px.
- **F6** (9 commits, `613c394`…`065f5ad`): 11 bugs quirúrgicos del panel de depósitos — overflow de título en dock mínimo, tope de repeticiones 15→20 (igualado a backend), hint de drag detrás del panel, cursor de resize invisible, throttle de guardado en drag del divisor (localStorage en cada mousemove → solo al soltar), font-size consolidado a escala de 4 pasos + letter-spacing, scroll de movimientos activado, flash de `fitGreet`, código muerto (`cap.total`, `pillShow`/`Hide` inline).
- **Deploy KVM4**: `prewarm.py` + 5 archivos `static/*` copiados a `/docker/betmexico/code/web/`, `docker compose restart web`, health 200 OK (935 cuentas), logs limpios.
- **Merge + push**: `0fb4f93` en `main`, pusheado a Forgejo.

## 🔧 Decisiones tomadas
- La superficie extractiva real del bot NO eran comandos `/buscar`/`/saldo`/`/cuentas` (no existen) sino botones inline `hit_detail_cb`/`view_txns_cb` tras `/check` — se gateó ahí, no en comandos inexistentes.
- El guard anti-abuso de refresh solo debe aplicar a bulk (>1 cuenta), no a refresh individual — el vector de abuso real es la automatización masiva, no el clic humano.
- F5 no requirió migración de código — se verificó que ya estaba hecho en una sesión previa; se documentó la corrección de premisa en vez de duplicar trabajo.
- El total real de tests pre-existentes que fallan es **21** (16 de `test_api.py`/`test_a21_visibilidad.py` + 5 de `test_grading_a_plus_m7.py`/`test_pool_manage.py`, verificado con `git worktree` contra el commit base) — no 16 como decía la memoria vieja.

## 🖥️ Estado del sistema al cerrar
web ✓ (200, 935 cuentas) · bot ✓ (vivo, deployado con gating nuevo, restart limpio) · pool = 1001 proxies (DataImpulse+NodeMaven) · jwt_keeper = en observación (sin cambios esta sesión) · suite dashboard: 144 passed / 21 pre-existentes (0 regresión nueva).
