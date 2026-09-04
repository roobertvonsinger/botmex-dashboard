# 00 — BotMex System Map (Nivel 0: Panorama Soberano)

> **Propósito:** Entender el sistema completo de BetMexico en 20 segundos sin sobrecarga cognitiva ni parálisis por análisis.
> **Canvas Raíz:** [[00 — BotMex System Map.canvas]]
> **Modelo Mental:** [[09 — Arquitectura de Grafo de Agentes (Cocina)]] (Estaciones de trabajo independientes y auto-sanables).

---

## 🗺️ Estructura de Capas del Ecosistema

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. ENTRADAS Y CANALES (Cyan "5")                                        │
│    [📱 Telegram Bot]              [🖥️ Dashboard FastAPI & Portal Web]  │
├─────────────────────────────────────────────────────────────────────────┤
│ 2. CONTROL, EVENTOS Y SOPORTE (Morado "6" / Cyan "5")                   │
│    [🔐 Auth & Roles RBAC]  [📡 Eventos SSE / Broadcast]  [🤖 Agente IA] │
├─────────────────────────────────────────────────────────────────────────┤
│ 3. MOTOR DE NEGOCIO & ESTACIONES (Morado "6" / Amarillo "3")            │
│    [💳 Flujo /bet] ──► [⚙️ deposits.py (Multi/Sched)] ──► [🔍 Algoritmo V10] │
│                        [💸 Retiros y STP]                                │
├─────────────────────────────────────────────────────────────────────────┤
│ 4. SERVICIOS DE FONDO Y PERSISTENCIA (Verde "4")                        │
│    [🔑 JWT Keeper]  ──► [🔄 Account Refresh (5m)] ──► [🗃️ SQLite WAL]   │
├─────────────────────────────────────────────────────────────────────────┤
│ 5. INFRAESTRUCTURA Y SALIDA RESIDENCIAL (Gris / Naranja "2")             │
│    [🌐 Proxy Pool Failover]   [🤖 Ruthopia Bridge :8787]  [🏦 Gateway]  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Reglas Semánticas de Color (Estándar Visual)

- **Cyan ("5"):** Canales humanos, visores, interfaces y telemetría (`Telegram Bot`, `Dashboard`, `SSE Stream`).
- **Morado ("6"):** Orquestadores, motores de ejecución y APIs backend (`deposits.py`, `app.py`, `Matchmaker`).
- **Verde ("4"):** Éxito validado, balances acreditados, sesiones activas y persistencia limpia (`SQLite WAL`, `JWT Keeper`).
- **Amarillo ("3"):** Estaciones de auditoría, checkers de calidad, scoring de BINs y decisiones de negocio.
- **Naranja ("2"):** Zonas de recuperación local, cooldowns 24h, backoff gentil y reintentos transitorios.
- **Rojo ("1"):** Tarjetas declinadas/quemadas, bloqueos inmutables (Married Card) y guardrails 403.

---

## 🔗 Dominios del Ecosistema (Mapas Detallados)

1. [[01 — Telegram Bot]] — Interfaz interactiva de operadores y Superadmin.
2. [[02 — Dashboard y Portal]] — Portal web FastAPI (`/dashboard`, `/user/{id}`, `?view_as=`).
3. [[03 — Auth, Roles y Visibilidad]] — Matriz de permisos y aislamiento de cuentas.
4. [[04 — Flujo Auto-deposit]] — El motor principal de depósito y matchmaking por cuotas Tier.
5. [[05 — Validación de Tarjetas]] — BIN Intelligence, algoritmo V10 y puente con Ruthopia.
6. [[06 — Sesiones, JWT y Refresh]] — Mantenimiento de cuentas "hot", prewarm y refresco sin captcha.
7. [[07 — Retiros y Reconciliación]] — Dispersión SPEI, verificación CLABE/CURP y loop de 60s.
8. [[08 — BD, Eventos e Infraestructura]] — Docker KVM4, proxies residenciales y concurrencia WAL.
9. [[09 — Arquitectura de Grafo de Agentes (Cocina)]] — **Guía visual del modelo de nodos y auto-healing.**
