# Plan de Implementación: Anti-Abuso, Cero Fugas y Guardias Operativas (Frictionless)

## 🎯 Objetivo
Blindar el dashboard y el bot de Telegram contra abusos (intencionales o por descuido) de los operadores. Proteger el saldo de CapMonster, limitar la concurrencia de depósitos, y visibilizar claramente el estado de las cuentas (enfriamiento vs listas).

## 🤖 Orquestación de Agentes (vía 9router)
Para optimizar tokens, velocidad y capacidades, el plan delega las fases a los modelos configurados en tu 9router:

*   **`rita-chat` (Gemini-3-flash / mimo-auto)**
    *   *Misión:* Modificaciones de UI Frontend (`static/app.js`, `static/style.css`). Tareas rápidas de parseo de DOM y CSS.
*   **`rita-tech` (DeepSeek-v4-flash / nemotron-3-ultra)**
    *   *Misión:* Lógica core backend (`prewarm.py`, `deposits.py`). Lógica de concurrencia en asyncio, límites de fallos y validación de permisos en Python puro.
*   **`rita-prime` (Gemini-pro-agent / Claude-opus-4-6-thinking)**
    *   *Misión:* Sellado del Bot de Telegram en el monorepo. Requiere precisión arquitectónica para no romper la ingestión de combos pero mutar comandos de consulta sin causar regresiones.

---

## 🛠️ Fases de Ejecución

### Fase 1: Frontend & UI (Delevar a `rita-chat`)
1. **Mover Badge JWT:** 
   * Modificar el renderizado de la tabla en `static/app.js` para que los iconos `🟢` y `🔑` aparezcan a la **izquierda** del combo `email:password`, haciéndolos lo primero que ve el operador.
2. **Visibilidad universal del Badge:** 
   * Asegurar que los operadores vean este badge (quitar la restricción que lo limitaba solo al Superadmin).
3. **Indicador Visual de Rate-Limit (Enfriamiento):**
   * **CSS:** Agregar una clase `.account-cooling` con `opacity: 0.5` (o grayscale) y `cursor: not-allowed`.
   * **JS:** Aplicar esta clase a las filas que tengan `cooldown_min > 0` o `status == 'DEAD'`.
   * **Interacción:** Si el operador hace clic en una cuenta que está enfriando, interceptar y mostrar un Toast/Alerta: *"❌ Cuenta en enfriamiento. No tocar."*

### Fase 2: Backend Guards & CapMonster (Delegar a `rita-tech`)
1. **Bloqueo de Actualización Manual (`prewarm.py`):**
   * En el endpoint de refresh/prewarm manual, validar si el usuario es SA.
   * Si es operador y la cuenta NO tiene JWT vivo (`jwt_alive == False`), abortar la petición con error 403/400: *"❌ Cuenta en descanso. Espera a que el sistema la recupere."* (Esto garantiza cero gasto de CapMonster por operadores).
2. **Límites de Concurrencia y Fallos (`deposits.py`):**
   * *Concurrencia:* Implementar un límite duro global (ej. semáforo de max 2 procesos simultáneos combinando matchmaker y scheduled).
   * *Fallos:* Frenar misión/depósitos en una cuenta al alcanzar **2 intentos fallidos**, marcándola automáticamente para cooldown/enfriamiento.

### Fase 3: Sello del Bot de Telegram (Delegar a `rita-prime`)
> *Nota Crítica: Excepción temporal al monorepo autorizada en CLAUDE.md para sellar fugas.*
1. **Restricción de Comandos Extractivos:**
   * Archivos target: Directorio `Proyectos/BetMexico/Telegram/...` (ej. `bot.py` o módulo de handlers).
   * Inyectar validación `if message.from_user.id not in PERSISTENT_USERS:` (o checar contra el SA_ID) al inicio de todos los comandos que exponen datos (`/buscar`, `/saldo`, `/cuentas`, `/info`).
   * El bot debe ignorar silenciosamente o devolver "Comando no autorizado" a los operadores.
2. **Preservar Ingestión:** 
   * Asegurar que el bot siga recibiendo combos en texto plano y ejecute la validación inicial (login_orchestrator) y agregue las cuentas exitosas al DB del pool, pero bloqueando la fuga de datos confidenciales.

---

## 🏁 Criterios de Éxito (Checklist de Vigilancia)
- [ ] Un operador intentando dar refresh a una cuenta gris (sin 🟢) recibe un rechazo del servidor.
- [ ] La tabla de cuentas muestra los semáforos verdes a la extrema izquierda para todos los usuarios.
- [ ] Las cuentas quemadas o en cooldown se ven opacas en la UI (Frictionless visual).
- [ ] El dashboard no permite correr más de 2 misiones de depósito pesadas en paralelo.
- [ ] El bot de Telegram ignora comandos de consulta de cualquier ID distinto al de Robert (SA).
- [ ] 0% de gasto de CapMonster por clics manuales de operadores (el control total del saldo regresa al `jwt_keeper`).