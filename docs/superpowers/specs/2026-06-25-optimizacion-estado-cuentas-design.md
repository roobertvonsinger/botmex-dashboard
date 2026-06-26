# Optimizacion logica de estado de cuentas — diseno (workflow)

## Modelo de estados
MAQUINA DE ESTADOS PULIDA (fuente unica de verdad: locked_by + locked_until + published_to_pool). Cada cuenta vive en EXACTAMENTE 1 de 5 estados derivados de 3 campos, sin columna de rol nueva.

ESTADOS:
1. TRASTIENDA = published_to_pool=0, locked_by NULL. Solo SA. Reposo administrativo.
2. POOL = published_to_pool=1, locked_by NULL, status='LIVE'. Visible a todos los non-SA. Disponible.
3. EN_USO (operador) = locked_by=<tg_operador no-SA>, locked_until=ISO no-nulo (reloj real). Invisible a otros operadores, visible al dueno + SA.
4. RESERVADA_SA (NUEVO) = locked_by='1341812706' (tg del SA, verificado en auth.py:10) Y locked_until IS NULL. Permanente, sin reloj. Invisible a non-SA. Ningun watchdog la toca (todos exigen locked_until IS NOT NULL). Solo sale por unlock manual del SA.
5. DEAD = status!='LIVE'. Fuera del juego.

DISCRIMINADOR CLAVE estado 3 vs 4 = locked_until, NO un campo de rol nuevo. Reloj presente=lock temporal; reloj NULL=lock perpetuo (solo lo pone el SA). Reusa el guard que el janitor YA tiene (app.py:1339 WHERE locked_until IS NOT NULL).

TRANSICIONES (disparador -> efecto):
- POOL->EN_USO: operador inicia deposito (_auto_lock_for_deposit) o lock manual. SET locked_by=tg, locked_until=now+Nh.
- POOL/EN_USO->RESERVADA_SA: SA inicia deposito o lock manual (override si era de otro). SET locked_by=tg_SA, locked_until=NULL.
- EN_USO->POOL: (a) operador unlock manual; (b) janitor: lock vencido + sin trabajo 24h. UN solo camino de codigo (ver pulido).
- EN_USO->EN_USO (sticky): janitor ve deposito/tarjeta <24h en lock vencido -> extiende locked_until+24h. No toca published_to_pool.
- RESERVADA_SA->POOL/TRASTIENDA: SOLO unlock manual del SA. Ningun watchdog.
- TRASTIENDA<->POOL: SA publish/hide. Guard nuevo: prohibir hide si locked_by!=NULL.
- *->DEAD: marcado dead (fuera de alcance).

INVARIANTES:
- I1 lock atomico: locked_by NULL <=> locked_until NULL (ambos o ninguno).
- I2: published_to_pool solo lo cambia un watchdog en el UNICO release canonico (=1).
- I3: locked_until NULL + locked_by NOT NULL => perpetuo (solo SA); ningun watchdog libera.
- I4: el trabajo (account_cards/balance/txns) se ata a email, nunca a locked_by => liberar no borra ni expone trabajo (cards/details siguen filtrados por rol).

## Pulido (consolidacion watchdogs)
CONSOLIDACION: 3 watchdogs que se pisan -> 1 LIBERADOR canonico + 2 NOTIFICADORES puros.

RAIZ verificada en codigo: 3 loops liberan la misma cuenta desde 3 origenes de tiempo distintos:
- _run_lock_janitor (app.py:1326, 5min): locked_until<=now. Libera/sticky. NO limpia notif_*, NO republica.
- _run_window_watcher fase 3 (app.py:1459, 2min): MIN(deposit_attempts.created_at)+24h; a las 25h libera Y republica. Tracking in-memory _window_notified (se pierde al reiniciar).
- _release_watchdog_tick caso 1 (app.py:1545, 60s): last_deposit_date (MX naive)+27h. Libera, limpia notif_*. NO republica.
=> misma cuenta liberada 2-3 veces, broadcasts duplicados, comportamiento dependiente de timezone.

PLAN:
1) Un helper unico `_release_account(c, id, email, reason, prev)` ATOMICO y SIEMPRE igual: UPDATE locked_by=NULL, locked_at=NULL, locked_until=NULL, notif_pre24h_sent_at=NULL, notif_at24h_sent_at=NULL, notif_at24h10_sent_at=NULL, published_to_pool=1 WHERE id=?; + un solo _broadcast(kind=unlock_auto, reason). Elimina las 3 variantes inconsistentes (notif limpia siempre, republica siempre).
2) Colapsar roles de los loops:
   - _run_lock_janitor = UNICO LIBERADOR. Ya es el unico que respeta locked_until IS NOT NULL (clave para RESERVADA_SA). Su rama "vomitada" llama _release_account(). Su origen de tiempo (locked_until, que _auto_lock_for_deposit SIEMPRE setea) es el unico valido.
   - _run_window_watcher = SOLO notificador (fases 1 y 2 warning/expired). Se QUITA la fase 3 (release+republish).
   - _release_watchdog = SOLO notificador (pre24h/24h/24h10). Se QUITA el caso 1 (auto-release 27h).
   Desaparecen los 3 origenes de tiempo; solo manda locked_until.
3) _window_notified in-memory: ya no libera, queda solo para de-dup de avisos. Reinicio = a lo mucho 1 aviso repetido (benigno), no perdida de datos.

POR QUE ES MAS FLUIDO:
- Un solo punto decide cuando se suelta => cero race entre liberadores.
- Liberar SIEMPRE republica + limpia notif => se acaba el limbo "liberada pero invisible" y las notif fantasma (el smell de notif_* sin limpiar en janitor).
- RESERVADA_SA sale gratis: el unico liberador exige locked_until IS NOT NULL; el lock SA tiene locked_until NULL => SA inmune sin codigo de rol en watchdogs.
- Sticky infinito (deposito cada 23.5h => lock eterno): acotar con techo opcional via locked_at+MAX_STICKY_DAYS; menor, documentarlo, no bloquea el rework.

## Fix bloqueo diferenciado por rol
BLOQUEO DIFERENCIADO POR ROL — minimo cambio, cero ruptura. Clave: lock perpetuo del SA = lock con locked_until NULL (los liberadores ya exigen locked_until IS NOT NULL, app.py:1339). No hace falta columna locked_by_role.

CAMBIO 1 (deposits.py:280 _auto_lock_for_deposit): si is_sa, locked_until=None. `locked_until = None if is_sa else (now+timedelta(hours=hours)).isoformat()`. SA que deposita -> RESERVADA_SA permanente; operador igual que hoy (2h/4h). El broadcast manda locked_until=None (frontend: "sin reloj/SA").

CAMBIO 2 (app.py:1638 lock_account manual): si caller es SA, locked_until=None y habilitar override SA (hoy el manual NO hace override y tira 409 hasta para SA — inconsistente con auto_lock). Operador manual: igual.

CAMBIO 3 (visibilidad GET /api/accounts, app.py:412-419): NO cambia. Non-SA ya solo ve locked_by NULL o suyo => una RESERVADA_SA (locked_by=tg_SA) cae fuera, invisible. SA ve todo. Cumple "invisible indefinidamente" sin tocar el filtro.

CAMBIO 4 (notificadores): agregar `AND locked_until IS NOT NULL` al WHERE de _run_window_watcher y de _release_watchdog_tick, para no spamear avisos de expiracion sobre RESERVADA_SA. window_watcher hoy NO lo tiene -> unico hueco real; release_watchdog filtra por locked_by pero conviene el guard explicito.

CAMBIO 5 (unlock manual SA): ya funciona (SA desbloquea cualquiera, app.py:1741). Solo verificar que pase por _release_account (limpia todo + republica).

RESULTADO: SA agarra cuenta (deposito o manual) -> locked_until NULL -> permanente, invisible a operadores, intocable por watchdogs; solo unlock manual del SA la regresa. Operador intacto. Costo: ~4 lineas efectivas (un ternario en cada lock + un AND en cada notificador). Aditivo.

## Diffs propuestos
- **deposits.py**: _auto_lock_for_deposit (~L280): cambiar locked_until = (now+timedelta(hours=hours)).isoformat() por: locked_until = None if is_sa else (now+timedelta(hours=hours)).isoformat(). El UPDATE (L298) ya inserta locked_until; pasara None para SA. Ajustar el broadcast (L307) a locked_until (puede ser None).
  - _por que_: Convierte el lock del SA en perpetuo (RESERVADA_SA) reutilizando el guard locked_until IS NOT NULL que ya tienen los liberadores. is_sa ya esta calculado en L281.
- **app.py**: Nuevo helper _release_account(c, account_id, email, reason, prev_locked_by): UPDATE accounts SET locked_by=NULL, locked_at=NULL, locked_until=NULL, notif_pre24h_sent_at=NULL, notif_at24h_sent_at=NULL, notif_at24h10_sent_at=NULL, published_to_pool=1 WHERE id=?; + un solo _broadcast(kind=unlock_auto, reason, prev_locked_by). Colocar cerca de _run_lock_janitor.
  - _por que_: Unifica las 3 liberaciones inconsistentes (janitor no limpiaba notif_* ni republicaba; release_watchdog no republicaba). Liberacion atomica y uniforme.
- **app.py**: _run_lock_janitor (L1367-1381 rama 'else' / vomitada): reemplazar el UPDATE+broadcast inline por _release_account(c, r['id'], r['email'], 'lock vencido sin trabajo 24h', r['locked_by']).
  - _por que_: Hace del janitor el UNICO liberador automatico, usando locked_until como unico origen de tiempo. Ya respeta locked_until IS NOT NULL => no toca RESERVADA_SA.
- **app.py**: _run_window_watcher (L1458-1472 fase 3): ELIMINAR el bloque que hace UPDATE locked_by=NULL...published_to_pool=1. Dejar solo el broadcast window_expired/warning (fases 1 y 2). Agregar 'AND locked_until IS NOT NULL' implicito filtrando en el loop (saltar si la cuenta tiene lock perpetuo).
  - _por que_: Quita el segundo liberador (origen de tiempo distinto: created_at+24h) que causaba doble-release y republish con otra logica. Queda como notificador puro.
- **app.py**: _release_watchdog_tick (L1544-1564 caso 1, hours>=27): ELIMINAR el auto-release. Mantener solo notifs (casos 2-4). Agregar 'AND locked_until IS NOT NULL' al SELECT (L1518) para no notificar sobre RESERVADA_SA.
  - _por que_: Quita el tercer liberador (origen last_deposit_date+27h en MX naive, fragil por timezone). El janitor cubre la liberacion via locked_until.
- **app.py**: lock_account manual (L1638-1658): detectar is_sa = _user.get('role')=='superadmin'; si SA -> locked_until=None y permitir override (UPDATE sin la condicion AND locked_by IS NULL, o re-lock). Si non-SA -> comportamiento actual (409 si ocupada).
  - _por que_: Alinea el lock manual con el auto-lock (que ya hace override SA) y hace que el lock manual del SA tambien sea perpetuo. Corrige la inconsistencia semantica detectada.
- **app.py**: publish_accounts/hide_all_accounts (L1675-1706): antes de poner published_to_pool=0, excluir o rechazar cuentas con locked_by IS NOT NULL (ej: WHERE ... AND locked_by IS NULL, o devolver lista de skipped).
  - _por que_: Evita el smell 'SA oculta una cuenta EN_USO y al liberarse desaparece' (published=0 + locked=NULL invisible para todos).
- **app.py**: Migracion _migrate (L143): aditiva opcional, backfill defensivo UPDATE accounts SET locked_until = locked_at_plus_2h WHERE locked_by IS NOT NULL AND locked_until IS NULL AND locked_by != '1341812706' (cuentas legacy sin locked_until que el janitor ignora para siempre). NO tocar las que ya sean del SA.
  - _por que_: El smell 'LOCKED_UNTIL NULLABLE PERO REQUERIDO': locks legacy sin locked_until nunca se liberan. Backfill los rescata sin afectar el nuevo RESERVADA_SA del SA.

## Edge cases
- Cuentas YA lockeadas hoy por operador (locked_until con valor): siguen como EN_USO normal; el janitor las libera al vencer. Sin migracion necesaria salvo las legacy sin locked_until (cubierto por backfill defensivo).
- Cuentas legacy con locked_by pero locked_until NULL que NO son del SA: hoy el janitor las ignora para siempre (lock eterno accidental). El backfill las re-temporiza. CUIDADO: correr backfill ANTES de desplegar el cambio que hace locked_until NULL = perpetuo-SA, si no se confundirian con RESERVADA_SA. Filtrar por locked_by != tg_SA.
- Deposito EN CURSO al migrar: _auto_lock_for_deposit corre al inicio del stream; si el deposito ya seteo locked_until, el cambio nuevo no lo altera retroactivamente. Un deposito del SA iniciado ANTES del cambio quedo con locked_until temporal; el SA tendra que re-lockear o re-depositar para volverlo perpetuo. Documentar.
- Frontend que consume /api/accounts: ahora puede recibir locked_until=None con locked_by!=NULL (RESERVADA_SA). El front debe interpretar 'sin reloj' = lock SA permanente y NO mostrar countdown ni boton de auto-release. Verificar el render del chip de lock antes de desplegar.
- Liberacion manual del SA sobre RESERVADA_SA: unlock_account ya lo permite (SA desbloquea cualquiera) y limpia campos. Asegurar que use _release_account para republicar consistentemente.
- SA toma una cuenta que YA estaba EN_USO de un operador: override (auto_lock ya lo hace; lock manual con CAMBIO 6). El operador anterior la pierde de su vista (locked_by paso a tg_SA). Recomendado: broadcast con prev_locked_by para que el operador vea en su feed que el SA la tomo (auditoria minima; hoy se pierde el dato).
- Cuenta RESERVADA_SA y el SA deposita de nuevo: idempotente (mismo locked_by); locked_until sigue NULL. OK.
- Race: janitor (5min) vs notificadores ahora puros: los notificadores ya no mutan locked_by, asi que no hay doble UPDATE. El unico mutador automatico es el janitor. Race residual solo entre janitor y unlock manual concurrente -> ultimo gana, ambos dejan locked_by=NULL (estado consistente).
- Sticky infinito: operador que deposita cada <24h mantiene la cuenta EN_USO para siempre via extension del janitor. No es bug de seguridad pero acapara pool. Opcional: techo MAX_STICKY desde locked_at original. Fuera del alcance critico.
- GET /api/cards/all y /api/deposits sin filtro de visibilidad (smell aparte): una RESERVADA_SA no expone mas que hoy, pero estos endpoints siguen filtrando nada. No lo arregla este rework; flaggear como deuda de seguridad separada (exposicion de credenciales).

## Verificacion adversarial
VEREDICTO: replantear: El diseño tiene intuición correcta pero requiere 4 cambios críticos PREVIOS: (1) Arreglar lock_account para SA override (2-3 líneas app.py:1645). (2) Backfill locked_until para cuentas legacy ANTES de cambiar deposits.py (crítico para 923 cuentas). (3) Guards locked_until IS NOT NULL en notificadores (window_watcher app.py:1412, release_watchdog app.py:1514). (4) Guardrail publish_accounts/hide_all_accounts contra cuentas EN_USO. Sin estos, doble-liberación, locks eternos, spam de notifs y cuentas fantasma garantizados."

- [alta] Invariante I1 (atomicidad lock) rota: lock_account manual no hace override SA como _auto_lock_for_deposit; asimetría en limpieza
  - mitigacion: app.py:1645: agregar OR is_sa=True antes WHERE. Consolidar liberadores en _release_account() que limpia TODOS atomicamente.
- [alta] Cuentas legacy (locked_by!=NULL, locked_until=NULL) nunca se liberan (janitor: WHERE locked_until IS NOT NULL); bloques eternos en 923 cuentas
  - mitigacion: Migración en _migrate() ANTES de desplegar: UPDATE accounts SET locked_until = datetime(locked_at,'+24 hours') WHERE locked_by IS NOT NULL AND locked_until IS NULL AND locked_by != '1341812706'. Correr UNA VEZ.
- [alta] 3 watchdogs distintos (janitor/window/release) con 3 orígenes de tiempo (locked_until/created_at+24h/last_deposit_date+27h) liberan concurrentemente; broadcasts duplicados
  - mitigacion: Interim: agregar AND locked_until IS NOT NULL a window_watcher/release_watchdog. Roadmap: consolidar a 1 liberador canonical.
- [media] Notificadores spamean sobre RESERVADA_SA (locked_until=NULL) que nunca se liberan; avisos falsos
  - mitigacion: Cambio: AND locked_until IS NOT NULL en SELECT de _run_window_watcher (app.py:1412) y _release_watchdog_tick (app.py:1514).
- [media] publish_accounts/hide_all_accounts sin guardrail: cuentas EN_USO ocultadas (published=0) quedan fantasma si se liberan asimétricamente
  - mitigacion: Excluir locked_by IS NOT NULL en publish/hide. O: liberador SIEMPRE republica (published_to_pool=1) con unlock.
- [media] Frontend desconoce locked_until=None para SA: riesgo countdown NaN, parse error, botón auto-release sobre lock perpetuo
  - mitigacion: Auditoría UI: chip de lock debe manejar locked_until=null. Si locked_until==null && locked_by!=null => 'Lock SA permanente' sin countdown.
- [baja] Sticky infinito: operador deposita cada 23.5h, lock eterno, acapara pool
  - mitigacion: Opcional: techo MAX_STICKY_DAYS en janitor. Documentar como comportamiento esperado.
- [baja] Race janitor vs unlock manual: ambos actualizan mismo id concurrentemente
  - mitigacion: SQLite DEFERRED isolation. Last-write-wins => locked_by=NULL. Aceptable eventual consistency.
