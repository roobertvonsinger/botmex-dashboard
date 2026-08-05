# Handoff de Diseño y Especificación Técnica: Portal Operador `/bet` — BotMexico

> Documento máster para trabajo en Open Design / Figma / Frontend Refactoring.
> Define la arquitectura visual, tokens, affordances, microinteracciones y flujo sin fricción desde Telegram hasta el Landing Page `/portal`.

> **⚠️ Corrección 2026-08-04 (Robert, campo real):** la frase de abajo "NO requiere ingresar
> contraseñas" se leyó mal en al menos una implementación como "sin login al dashboard" —
> **falso**. Se refiere ÚNICA y EXCLUSIVAMENTE a la contraseña de la cuenta de BetMexico
> (el operador nunca la ve/usa). El login al dashboard con usuario/contraseña PROPIOS del
> sistema es y debe ser siempre obligatorio para cualquier no-SA. Ver desambiguación completa
> en `PRODUCT.md`. Este documento también describe un flujo de dos vistas (misión + grid) con
> `mission_id` visible que Robert marcó como ruido innecesario el mismo día — ver corrección
> en `PRODUCT.md` sección "Portal del operador" antes de usar este doc como referencia de diseño.

---

## 1. Visión y Filosofía de Marca (BoTMexico UX)

- **Nombre & Esencia:** BoTMexico — "El Cactus de la Suerte" 🌵 (Cyber-Mexicana táctica, limpia, veloz, cero fricción).
- **Core Goal:** El operador inicia `/bet` en Telegram con 1 a 4 CCs, toca el enlace dinámico y cae en una experiencia web inmersiva, interactiva y automatizada que **NO requiere ingresar contraseñas** y **bloquea cualquier bypass fuera del dashboard**.
- **Jerarquía:** Todo movimiento de capital (retiro, liberación de lock, copia de CLABE STP, monitoreo de ciclo) se gestiona con 1-Click directo en la web usando los JWTs persistidos en backend.

---

## 2. Tokens de Diseño y Sistema Visual

```css
:root {
  /* Paleta Base (Cyber Graphite) */
  --bg-dark: #0d1117;
  --bg-card: #161b22;
  --bg-elevated: #1c2129;
  
  /* Bordes & Estructura */
  --border-subtle: #30363d;
  --border-hover: #484f58;
  
  /* Colores de Estado & Acentos */
  --accent-blue: #58a6ff;      /* Links & Selecciones */
  --green-bright: #3fb950;     /* Saldo Real, Matches OK, Live */
  --green-glow: rgba(63, 185, 80, 0.15);
  --gold-accent: #d4a843;      /* Misiones Activas, Locks, Misiones */
  --gold-glow: rgba(212, 168, 67, 0.12);
  --red-alert: #f85149;       /* Errores, Strikes, Abortar */
  --text-primary: #f0f6fc;
  --text-secondary: #8b949e;
  
  /* Radios & Sombras */
  --radius-lg: 12px;
  --radius-md: 8px;
  --radius-sm: 6px;
  --shadow-card: 0 4px 16px rgba(0, 0, 0, 0.35);
}
```

---

## 3. Arquitectura del Flujo (Telegram → Landing Page)

```
[ Telegram Chat ] ──► /bet <CCs> ──► Liveness Check (Ruthopia Gate) ──► Confirmation Gate
                                                                             │
┌────────────────────────────────────────────────────────────────────────────┘
▼
[ Landing Web: /portal?match={mission_id} ]
├── 1. Misión Activa (Modo Live Stream SSE)
│    ├── Banner de Estado (Rastreando ➔ Llenando ➔ Completado)
│    ├── Progress Fill Bar animada con relámpago glow
│    ├── Reloj Countdown (60s por ciclo de depósito)
│    └── Match Cards (Aparecen con animación SlideIn + Check Verde + CLABE STP)
│
└── 2. Grid de Cuentas del Operador (Modo Gestión 1-Click)
     ├── Card de Cuenta (Saldo Real $XX MXN gigante + Bonos + Grade A+/A/B/C)
     ├── Bloque CLABE STP monoespaciada (Copia rápida 1-Tap)
     ├── Botón "💸 Retirar" (Modal 1-Click usando JWT sin password)
     └── Botón "🔓 Liberar" (Desbloqueo inmediato si la cuenta tiene Lock)
```

---

## 4. Affordance Table (Frecuencias de Interacción)

| Componente / Elemento | Affordance UI | Acción de Código / API | Feedback Visual / Microanimación |
|---|---|---|---|
| **Pill Misión (`?match=ID`)** | Badge dorado destacado | `GET /api/deposits/auto/{id}/status` | Pulse suave en color oro (`--gold-glow`) |
| **Barra de Progreso Misión** | Fillbar horizontal | Eventos SSE `auto_mission` | Transición suave `width 0.4s ease` con resplandor |
| **Match Row (Cuenta ↔ CC)** | Fila flotante con check | Stream SSE en tiempo real | `animation: slideIn 0.3s cubic-bezier(0,1,0.5,1)` |
| **CLABE Box** | Contenedor monoespaciado | `navigator.clipboard.writeText` | Botón cambia a `✓` verde por 2s + efecto ripple |
| **Botón 💸 Retirar** | Botón primario verde | `POST /api/operator/accounts/{id}/withdraw` | Abre modal con input numérico y saldo máx |
| **Botón 🔓 Liberar** | Botón peligro borde rojo | `POST /api/operator/accounts/{id}/release` | Quita el badge `🔒 Bloqueada` al instante |

---

## 5. Especificaciones de Microinteracciones y Polish

1. **Estado de Cargas (Zero Flicker):**
   - Transiciones suaves entre la vista de `Misión Activa` y `Mis Cuentas`.
   - Uso de Skeletons y Shimmer effect en lugar de spinners molestos.

2. **Modales de Acción (Sin Contraseña):**
   - **Retiro Express:** El modal toma foco automático en el campo de monto (`#wdAmount`). Al dar Enter, liquida usando el JWT de la BD y lanza Toast `✓ Retiro enviado: TX-XXXX`.
   - **Locks:** Al dar clic en `🔓 Liberar`, la card conmuta su estado visual sin recargar la página.

3. **Responsividad Móvil (Mobile First):**
   - El viewport de 375px (Smartphones) acomoda el grid en 1 sola columna limpia.
   - Los botones mantienen una altura mínima de `44px` (Fitts' Law) para tap táctil cómodo.

---

## 6. checklist de Verificación para Open Design / Figma

- [ ] Logotipo "BoTMexico 🌵" con brillo sutil en el Navbar superior.
- [ ] Tarjeta de cuenta con tipografía monoespaciada para la CLABE STP de 18 dígitos.
- [ ] Badge de Calificación (Grade `A+`, `A`, `B`, `C`) con código de color dinámico.
- [ ] Modal de Retiro express con límite máximo fijado al saldo real disponible.
- [ ] Soporte completo de Server-Sent Events (SSE) `/api/events` para actualización en vivo.

---

*Generado automáticamente por ZCode para el ciclo de iteración en Open Design — BoTMexico Dashboard v2.*
