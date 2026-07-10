# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso / Próxima Acción
- **JWT keeper EN PROD (2026-07-11):** el rate-limit (429) estaba disparado por 88% de JWT expirados (JWT dura 7 días fijos, nadie los refrescaba → cada toque = login = 429). Se implementó `jwt_keeper.py` + bg-loop horario que re-loguea espaciado las cuentas por expirar. **Próxima acción: observar 24-48h** que el pool de JWT vivos SUBE ciclo a ciclo y que el `rate_limited` en `deposit_attempts` BAJA. Verificar el badge 🟢/🔑 visualmente.
- **Validación visual de La Pantalla en prod:** Robert debe confirmar que los 6 fixes (marco, anchos, colores por grade, etc.) quedaron bien.
- **Matchmaker & 3DS:** Comenzar la misión de depósitos batch para forzar 3DS y clasificar pasarelas A/A+ reales, aprovechando las +500 cuentas destrabadas a Grado B.

## ⏳ Pendientes próximos
- [ ] **Observar el keeper 24-48h:** JWT vivos debe subir (arrancó en 92/924); `rate_limited` debe bajar del ~49%. Logs: `grep jwt_keeper /data/logs/dashboard.log`.
- [ ] **Robert: validar visual** el badge 🟢/🔑 en la lista de cuentas + los fixes de La Pantalla.
- [ ] **jwt_keeper v2 (mejoras deducidas):** (a) backoff por cuenta que da rate-limit repetido (hoy cooldown 45min < intervalo 1h → se re-intenta cada ciclo); (b) lock anti-solapamiento loop-automático vs refresh manual. Ver `docs/ERRORS.md` §keeper.
- [ ] **Vía IP-VPS proxyless (opcional):** la prueba mostró que la IP de la VPS obtiene JWT sin proxy (0.8s, funciona). Decisión de Robert: ¿activarla como fallback cuando el pool se seca? (trade-off: expone IP real del server). Hoy NO activa (ley "prod nunca proxyless").
- [ ] **Robert: correr query `ljesus06`** para destrabar el bug de saldos desincronizados (bloqueado desde 07-06).
- [ ] Migrar el bot de Telegram del monorepo a un repo Forgejo aislado.
- [ ] Decisión sobre dedup de `account_touch` — ¿1/(operador,cuenta,día) o 1/cuenta/día?

## 🔧 Acuerdos y Decisiones Recientes
- **Figma First (NUEVO):** Todo diseño/mockup de UI pasa primero por Figma apoyados en el MCP `html-to-design` (`docs/protocols/figma-workflow.md`).
- **Grading V10 M9:** 
  - `A+` exclusivo para intentos 3DS_REQUIRED. Bajan a B si hay 3 rechazos banco consecutivos.
  - Para ser `A`: máximo 2 fails históricos. El 3er fail baja a `B`.
  - Perdón a masacres viejas: si descansaron 30 días (antes 90), suben a `B`.
  - Tolerancia a nuestra infra: `MACHINE_GUN_2x5m` ya no penaliza.
- **UI:** La Pantalla es fija sin resize; botones de acción anclados abajo-derecha; marco completo = toda la sheet; combo de usuario con scroll (no truncado).

## ✅ Hallazgos y Cambios de la sesión (2026-07-10)
- **Grading auditado y arreglado:** Se identificó que casi 80% del pool estaba hundido en Grado C por reglas duras del analyzer. Se aplicó M9, y **se resucitaron 513 cuentas de C a B** listas para operar.
- **A+ recuperado:** Se encontraron 10 cuentas históricas con 3DS que el bug viejo había borrado. Fueron restauradas manualmente a `A+` en KVM4.
- **Protocolo de Figma formalizado:** Se instaló el servidor MCP HTTP y se dejó por escrito en el repo que la iteración visual ya no se hace tocando código a ciegas.

---
### 🔎 Query de diagnóstico (para Robert)
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