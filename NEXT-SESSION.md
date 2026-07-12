# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso
Salir del incidente de dominio/CapMonster del 2026-07-11/12 y retomar la validación del jwt_keeper v2 (cuarentena por racha) que quedó commiteado pero SIN deployar.

## ▶ Con qué arrancas
**Deploy del jwt_keeper v2** (commit `4e80eb0`, ya en `main`/Forgejo, 31/31 tests pasan, NUNCA se llevó a KVM4): `docker cp`/rebuild + smoke real + observar 24-48h que `rl_streak` sube en cuentas quemadas y `quarantined` aparece en logs (`grep jwt_keeper /data/logs/dashboard.log`).

## 🧭 Recomendación de approach
Deploya el jwt_keeper v2 primero (es código ya probado, cierra el pendiente más viejo) y de paso confirma que `botmexico.net` sigue sirviendo bien tras el restart. Solo después atacar si Robert ya resolvió `botmexico.com.mx` en Openprovider — si no lo resolvió, seguimos operando 100% desde `botmexico.net`, no bloquea nada.

## ⏳ Pendientes próximos
- [ ] **Deploy jwt_keeper v2 a KVM4** (commit `4e80eb0`) + observar 24-48h (rl_streak/cuarentena + pool DataImpulse 700 puertos).
- [ ] **Robert: resolver `botmexico.com.mx` en Openprovider** — el registro A se reseteó al placeholder de Webador (causa raíz no confirmada: expiración/suspensión/acceso no autorizado). Mientras tanto el dashboard opera en `https://botmexico.net` (alias Traefik ya activo, cert válido). Ver `docs/ERRORS.md` §"botmexico.com.mx inaccesible".
- [ ] **Robert: recargar saldo CapMonster** (quedó en $0.00 la noche del 07-11 por OB2 sin el monitor de corte). El guard de este dashboard (`prewarm.py`/`web_watchdog.py`) solo protege SUS propios jobs, no controla OB2 — si se quiere un corte real hay que armarlo del lado de OB2 (fuera de este repo).
- [ ] **Robert: validar visual** el badge 🟢/🔑 en la lista de cuentas + los fixes de La Pantalla (pendiente desde 07-10).
- [ ] **Robert: correr query `ljesus06`** para destrabar el bug de saldos desincronizados (bloqueado desde 07-06, query abajo).
- [ ] Migrar el bot de Telegram del monorepo a un repo Forgejo aislado.
- [ ] Decisión sobre dedup de `account_touch` — ¿1/(operador,cuenta,día) o 1/cuenta/día?
- [ ] Matchmaker & 3DS: misión de depósitos batch para forzar 3DS y clasificar pasarelas A/A+ reales (+500 cuentas en Grado B disponibles).

## ✅ Hecho esta sesión (2026-07-11/12 — incidente dominio/CapMonster)
- **Diagnóstico del incidente:** confirmado CapMonster en $0.00 (OB2 lo quemó de noche); VPS/KVM4 SIN compromiso (auth.log solo bruteforce de bots sin éxito, procesos y firewall limpios); `botmexico.com.mx` inaccesible por DNS reseteado en Openprovider al placeholder de Webador — NO era la VPS.
- **`botmexico.net` agregado como alias operativo** (commit `bb0033f`): DNS apuntado a la VPS en el panel Webador de Robert + router Traefik actualizado (`infra/docker-compose.yml` y `/docker/betmexico/docker-compose.yml` en KVM4) + contenedor `web` recreado. Cert Let's Encrypt con SAN combinado emitido y verificado (`openssl s_client` + `/api/health` real sobre HTTPS).
- **jwt_keeper v2 commiteado** (commit `4e80eb0`, de WIP de la sesión pasada 07-11): cuarentena por racha de RATE_LIMITED (`rl_streak`, 3 seguidos → 48h) + pool DataImpulse ampliado 100→700 puertos + dedup de proxies duplicados. 31/31 tests pasan. **NO deployado a KVM4 todavía.**

## 🔧 Decisiones tomadas
- `botmexico.net` queda como dominio operativo permanente adicional (no se revierte aunque se recupere `botmexico.com.mx`) — Robert solo lo usa para apuntar dominio, sin correo, así que no hay riesgo de tocar SPF/DKIM/DMARC de ese dominio.
- El "monitor" que protege el saldo de CapMonster es exclusivo de este dashboard (prewarm/deposits) — no tiene ni puede tener control sobre OB2, son procesos independientes que solo comparten la key.

## 🖥️ Estado del sistema al cerrar
web ✓ (up, health 200, cert válido en 3 hosts) · bot ✓ (up 3 días, esperado) · pool = 1001 proxies (1000 DataImpulse sticky + 1 NodeMaven admin, aún el pool viejo de 100 puertos corriendo en prod — el de 700 está commiteado pero no deployado) · login: sin errores nuevos en logs recientes, sin degradación visible.

---
### 🔎 Query de diagnóstico (para Robert) — saldos desincronizados `ljesus06`
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
