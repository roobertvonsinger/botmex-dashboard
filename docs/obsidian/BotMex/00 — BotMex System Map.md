# 00 — BotMex System Map (Nivel 0: Panorama)

> **Propósito:** Entender el sistema completo de BetMexico en 20 segundos sin sobrecarga cognitiva.
> **Canvas Asociado:** [[00 — BotMex System Map.canvas]]

---

## 🗺️ Estructura de Capas

```
┌─────────────────────────────────────────────────────────────┐
│ 1. ENTRADAS / CANALES (Azul)                                │
│    [📱 Telegram Bot]        [🖥️ Dashboard / Portal Web]    │
├─────────────────────────────────────────────────────────────┤
│ 2. CAPA DE CONTROL Y EVENTOS (Morado)                       │
│    [🔐 Auth y Roles]        [📡 Eventos SSE / Broadcast]    │
├─────────────────────────────────────────────────────────────┤
│ 3. MOTOR DE NEGOCIO (Morado / Verde)                        │
│    [💳 Flujo /bet] ──► [⚙️ Auto-deposit] ──► [🔍 Cards]    │
│                        [💸 Retiros y Reconciliación]        │
├─────────────────────────────────────────────────────────────┤
│ 4. SERVICIOS Y ESTADO (Verde / Morado)                      │
│    [🔑 JWT Keeper]  ──► [🔄 Account Refresh]                │
│    └──────────────────► [🗃️ SQLite / DB]                   │
├─────────────────────────────────────────────────────────────┤
│ 5. INTEGRACIONES EXTERNAS (Gris)                            │
│    [🌐 Proxy Pool]    [🤖 Ruthopia Bridge]  [🏦 BetMex API] │
└─────────────────────────────────────────────────────────────┘
```

## ⚡ Reglas Semánticas de Color
- **Azul ("5"):** Entradas e interfaces humanas (Telegram, Web).
- **Morado ("6"):** Orquestadores y motores centrales (`/bet`, `auto_deposit`, `withdrawals`).
- **Verde ("4"):** Persistencia, sesiones vivas y estados aprobados (`SQLite`, `JWT Keeper`).
- **Amarillo ("3"):** Reglas, decisiones en curso y cambios propuestos.
- **Rojo ("1"):** Riesgos, bloqueos y guardrails inmutables (`Married Card`, `DEAD`).
- **Gris:** Infraestructura externa y proxies.

---

## 🔗 Navegación Rápida a Dominios
1. [[01 — Telegram Bot]]
2. [[02 — Dashboard y Portal]]
3. [[03 — Auth, Roles y Visibilidad]]
4. [[04 — Flujo Auto-deposit]]
5. [[05 — Validación de Tarjetas]]
6. [[06 — Sesiones, JWT y Refresh]]
7. [[07 — Retiros y Reconciliación]]
8. [[08 — BD, Eventos e Infraestructura]]
