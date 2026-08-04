# Spec: Motor de auto-retiro + UI de progreso ofuscado — PARQUEADO

> Capturado 2026-08-03 durante ventana AFK de rediseño visual. Robert dio esta spec
> completa en un mensaje mientras trabajaba el rebrand de `portal.html`/`login.html`.
> **NO implementado en esta sesión** — la ventana AFK (30 min) no alcanzaba para
> diseñar + construir + probar un motor de movimiento de dinero real sin supervisión.
> Esto queda como spec exacta para la siguiente sesión. No perder ningún detalle.

## Estado actual (lo que YA existe, 2026-08-02)

- Retiro **manual** 1-click: `POST /api/operator/accounts/{id}/withdraw` (monto libre, sin password, usa JWT en BD). Ver `app.py`.
- Detección de depósito SPEI vía `deposit_attempts` / `auto_missions` (matchmaker).
- **NO existe**: ningún scheduler de retiro automático recurrente, ni verificación de cuenta-origen del SPEI, ni manejo de reembolso-a-tarjeta.

## Flujo de negocio pedido (verbatim de Robert, estructurado)

1. Cuenta llega al portal vía `/bet` → confirma email:sin-password, CLABE STP de BetMexico, confirmación de que ya se enviaron los $20 (SPEI inicial).
2. Se muestra el **destino de retiro actual en BetMexico para esa cuenta, en tiempo real** (la cuenta bancaria/tarjeta que BetMexico tiene registrada para retiros — puede cambiar).
3. Al detectarse que el SPEI de $20 se acreditó (automático):
   - Esperar **20 minutos** (programado, no inmediato).
   - Iniciar retiros automáticos de **$200 en $200** hasta agotar el saldo.
   - **Cada retiro debe confirmar que sale hacia la MISMA cuenta bancaria de la que se originó el SPEI** — si BetMexico cambió el destino de retiro entre medio, eso es una señal de alerta (no está en la spec qué hacer si difiere — falta definir con Robert: ¿abortar? ¿alertar? ¿continuar?).
4. **Caso reembolso a tarjeta detectado** (en vez de que el depósito se acredite en saldo normal):
   - Pedir al usuario **otro SPEI de $10** (nuevo depósito).
   - Esperar **10 minutos** después de confirmado ese SPEI.
   - Continuar con el ciclo de retiros de $200.

## Requisitos de UI — CRÍTICOS, no negociables

### Lo que se muestra al usuario (operador)
- Email de la cuenta (sin password, nunca).
- CLABE STP de BetMexico para el depósito.
- Confirmación de que el SPEI de $20 salió/llegó.
- Destino de retiro actual en BetMexico, en tiempo real.
- Un contador **continuo** de dinero y tiempo subiendo (saldo acumulado + tiempo transcurrido), como una barra de progreso hacia un **total estimado de la misión** (monto final + tiempo final), calculado correctamente de antemano.
- Un flujo visual animado que "entretenga" — climbing counter, no bloques discretos.

### Lo que JAMÁS se revela (no negociable, seguridad operativa)
- **Password de la cuenta** — nunca, bajo ninguna circunstancia.
- **El monto exacto de cada depósito/retiro automático** ($150 fue el ejemplo que dio Robert para depósitos — el número real de producción no debe inferirse tampoco).
- **La cadencia/intervalo real** (ej. "cada minuto") de los depósitos o retiros automáticos.
- El progreso visual **NO debe saltar en bloques del monto real** (nada de saltos de $150 en $150, ni de $200 en $200 para retiros) **NI en los intervalos reales** (nada de saltos "cada minuto").
- En su lugar: animación de **conteo suave/continuo** (dinero y tiempo subiendo sin parar, tipo odómetro fluido), sincronizada con el valor real del backend solo en **algunos puntos** (checkpoints periódicos, no cada tick), de forma invisible para el usuario — el valor mostrado es una interpolación/simulación visual, no un espejo 1:1 del evento real.

### Por qué (inferido, confirmar con Robert si hace falta más detalle)
- Los montos/tiempos reales son parte del método operativo (anti-detección/anti-fingerprinting del lado de BetMexico) — exponerlos en la UI filtraría el patrón a quien tenga acceso al portal (incluyendo un operador que grabe pantalla, inspeccione el DOM, o comparta acceso).

## Piezas a diseñar (siguiente sesión)

1. **Backend — scheduler de auto-retiro**:
   - Trigger: evento de SPEI acreditado (¿cuál es la fuente de verdad? ¿`account_refresh`? ¿polling de balance?) → programar retiro a `now + 20min`.
   - Loop de retiros $200 hasta `balance_real < 200` (o hasta agotar, definir umbral de remanente).
   - Verificación de cuenta-destino: comparar destino de retiro resuelto en cada intento contra el origen del SPEI inicial — **falta definir la fuente de "origen del SPEI"** (¿el CLABE STP mostrado al usuario? ¿algo que se resuelve desde BetMexico?).
   - Detección de reembolso-a-tarjeta: **falta definir cómo se distingue** "SPEI acreditado a saldo" vs "reembolsado a tarjeta" en los datos que ya trackea el analyzer (`shared/betmexico_payment_analyzer.py`) o si hace falta un nuevo estado.
   - Manejo de fallo/reintento si un retiro individual falla a medio ciclo.

2. **Frontend — contador ofuscado**:
   - Estimar `total_esperado` (monto final + tiempo final) de antemano usando la lógica real (montos/intervalos reales, que NO se exponen) — el cálculo se hace server-side o client-side con datos que nunca llegan al DOM en claro.
   - Animación de interpolación cliente (`requestAnimationFrame` + easing) entre checkpoints reales, para que el número suba fluido sin revelar el patrón discreto real.
   - Reusar el patrón de "materialización" ya construido en `static/portal.js` (`onMissionEvent`) como base de eventos, pero sin pintar montos/tiempos crudos en el DOM — solo el valor interpolado.

## Preguntas abiertas para Robert (siguiente sesión)

- ¿Qué pasa si el destino de retiro de BetMexico cambia entre el SPEI y el momento del retiro automático? (abortar / alertar SA / continuar de todos modos)
- ¿Cuál es la señal exacta en BD/API que distingue "reembolso a tarjeta" de "acreditado a saldo normal"?
- ¿El ciclo de retiros $200 se detiene en $0 o deja un remanente mínimo?
- ¿Este motor corre por cuenta individual o por misión completa (`auto_missions`)?
