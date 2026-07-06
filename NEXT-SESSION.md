# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso
Los **2 KPIs accionables** (📋 Logs + 📌 Cuentas a la mano) están deployados en prod y en fase de **pulido fino guiado por Robert operando en vivo**. Esta sesión pulió a fondo el **feed KPI Logs** (orden, agrupación, color, anti-spam) y la **jerarquía de Cuentas a la mano**. Todo mergeado a `main` y deployado con smoke verde.

## ▶ Con qué arrancas
**Robert prueba en prod** (`https://botmexico.com.mx`, Ctrl+F5) los ajustes recién deployados y reporta lo que falte afinar. Próximo turno **depura lo que reporte**. Si no hay reporte, la acción inmediata es verificar runtime end-to-end: abrir una cuenta (¿`account_touch` con dedup 1/operador/cuenta/día + su color?) y hacer 2+ depósitos a la misma cuenta (¿se agrupan en 1 fila con `▸ ×N` desplegable?).

## 🧭 Recomendación de approach
Seguir en **depuración fina en prod** (el pulido visual se hace con datos reales, no en local — no hay BD/sesión/SSE en local). Medir objetivamente lo que se pueda (getBoundingClientRect), no a ojo. El backend está probado; los cambios de esta sesión son frontend + un ajuste aditivo de payload en `/api/activity`.

## ⏳ Pendientes próximos
- [ ] **Robert: validar en prod** los 4 ajustes del feed (agrupación desplegable, dedup de interacciones, color por operador, alerta de saldo muerta) + la jerarquía combo/nombre de Cuentas a la mano.
- [ ] **Decisión Robert: dedup de `account_touch`** — se implementó **1 por (operador, cuenta, día)** para no perder a un segundo operador que entre a la misma cuenta. Si lo quiere estrictamente **1 por cuenta/día** sin importar quién, es 1 línea (quitar `who_id` de la clave `_touchSeen`).
- [ ] **Punto de fondo aún abierto:** ¿qué más es "señal" en el feed SA además de rechazos-con-causa+tarjeta y patrones de quema? (info accionable que oriente, `project_inteligencia_medible`).
- [ ] Reubicar el filtro "en uso" (quedó inaccesible al quitar Pool) — `feedback_no_quitar_compactar`.
- [ ] Vista completa de Actividad (`activity_logic.js`): `deposit_step`/`account_touch` siguen cayendo al fallback genérico `·` (el KPI card sí tiene render dedicado; la vista completa no).
- [ ] **Limpieza futura (no urgente):** el backend emite `account_touch`/`deposit_step` en hora MX y el resto en UTC — mezcla de zonas que `_feedEpoch` absorbe en el front. Unificar backend a UTC-iso quitaría el parche (mayor superficie). Ver `docs/ERRORS.md`.
- [ ] Marquesina "casino" — POSPUESTA (`project_marquesina_casino`). Ositos-avatar — pospuesto.
- untracked en raíz (NO commitear a propósito): `idea_vaga.txt` · `reports/` (auditoría + **xlsx de TARJETAS = datos sensibles**).

## ✅ Hecho esta sesión (2026-07-06) — pulido del feed KPI Logs + Cuentas a la mano
- `1771bc9` **KPI Logs cronológico + día + Cuentas combo protagonista** — `_feedEpoch(ts,kind)` normaliza los `ts` (MX naive / UTC naive / UTC-tz, medidos en prod) a epoch absoluto → orden por tiempo real (los locks ya no se pinean arriba) + cabeceras Hoy/Ayer/fecha en tz MX. Corrige el `+6h` latente de deposit/lock. Cuentas a la mano: combo `email:password` protagonista, nombre chico al lado, fuera el `LIVE` (badge solo si bloqueada/DEAD).
- `f0a1797` **feed: agrupar + dedup + color + anti-spam** — depósitos repetidos colapsan en 1 fila con badge `▸ ×N` desplegable (sublista con hora); `account_touch` dedup 1/operador/cuenta/día; `●` de color por operador (esquema `USER_COLORS`) en vista SA; alertas de servicio (capmonster/proxy/salud) fuera del feed y de notificaciones (spameaban por polling); `/api/activity` ahora trae `who_color`/`who_id`.
- `7e06166` **merge a `main`** (--no-ff) + push a Forgejo.
- **Deploy KVM4:** `app.js` + `style.css` (hot-mount) + `app.py` (restart SIGKILL/up). Smoke verde: md5 servido == repo (3 archivos), health 200 (923 cuentas), 0 errores de arranque, `who_color` cargó.

## 🔧 Decisiones tomadas
- `_feedEpoch` es **frontend-only** (no tocar backend/BD/flujos de depósito) — menor riesgo; absorbe la mezcla de zonas de origen.
- `account_touch` dedup en el feed **por (operador, cuenta, día)** — preserva el "quién" (pendiente de confirmar con Robert si lo quería sin importar quién).
- **Badge/estado solo habla cuando es excepción accionable** (bloqueada/DEAD); `LIVE` = default usable = **sin badge**. Mostrar estados default = adorno sin criterio (ver memoria `feedback_badge_solo_excepcion`).
- Alertas de servicio NO van al feed ni a notif — su estado vive en el indicador de salud del header. Robert: "ya lo estoy viendo, no hace falta que mame".
- Color por operador reusa `USER_COLORS` del backend (RobertVS=warn, Lau=purple, Luisito=accent, Magdiel=azure), no un esquema paralelo.

## 🖥️ Estado del sistema al cerrar
- **web** up (recién deployado, restart limpio) · **bot** up · **health** 200 (923 cuentas) · **pool** 102 (100 `dataimpulse` + 2 `nodemaven`) · **login** ok (sin 406/504/ProxyError en 12h). Rama `main` == `origin/main` (`7e06166`). Todo pusheado.
