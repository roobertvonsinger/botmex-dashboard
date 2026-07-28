# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primario: Robert, TDAH diagnosticado — Dev Chief y operador dueño (superadmin) del sistema. Secundario: un pequeño equipo de operadores humanos que ejecutan fraude-ops manual/asistido sobre cuentas de BetMexico (casino online) — abren cuentas, prueban tarjetas, depositan, retiran, verifican KYC, dejan notas — bajo presión de tiempo y en sesiones largas de trabajo repetitivo de alto volumen. La superficie se usa de noche, en escritorio, típicamente con varios monitores/pestañas abiertas en paralelo.

## Product Purpose

El dashboard NO es decoración — es una bitácora operativa que trackea cada intento de depósito/retiro (tarjeta, monto, estado, operador, latencia), deja que el operador decida y el sistema ejecute+reporte, monitorea servicios externos (CapMonster, proxies MX, WebScraping.ai) y persiste todo lo útil. Test de éxito explícito: si en 1 semana alguien necesita reconstruir qué pasó con la cuenta X (qué tarjetas, cuándo, cuánto, qué resultado, qué operador) — el dashboard debe poder responderlo. Si no puede, falta funcionalidad.

## Positioning

Debe ganarle en fluidez a usar BetMexico directamente — si operar desde el dashboard es más lento o más pesado que ir al sitio real, el operador se va y el tracking muere. El mecanismo que un competidor genérico no podría copiar sin el mismo trabajo de campo: pooling de cuentas con grading de riesgo (A+/A/B/C/D/U) derivado de comportamiento real, más reglas anti-detección medidas en campo (cooldowns 60s/5s, topes de declines, cap de cuentas por tarjeta) que imitan pacing humano contra el antifraude de BetMexico, más un motor de depósito/retiro que ejecuta sin que el operador tenga que salir del dashboard.

## Operating Context

Trabajo de escritorio, sesiones largas, alto volumen, con foco roto/recuperado constantemente (usuario primario TDAH). El operador copia y pega credenciales, números de tarjeta y clabes SPEI docenas de veces por sesión — el copiado tiene que ser instantáneo y sin fricción. Necesita señales de confianza al vistazo (grade de la cuenta) antes de actuar, no después. Cada acción de dinero real (depósito, retiro) es irreversible y cuesta dinero de verdad si sale mal — el diseño no puede esconder ni demorar la información que decide esa acción.

## Capabilities and Constraints

- Stack: FastAPI + SQLite + vanilla HTML/CSS/JS sin build step; deploy hot-mount (frontend sin restart, backend con restart de contenedor).
- Regla dura "no quitar, compactar": ninguna capacidad existente se elimina al rediseñar, solo se reorganiza/compacta.
- Regla dura "no enmascarar": combos (email:password), tarjetas (pipe puro num|mm|yy|cvv) y clabes SPEI se muestran SIEMPRE en texto plano, nunca censuradas — el copiado rápido es prioridad sobre la sensación de "seguro". Este es trabajo de testing/operación propia autorizada, no cara pública.
- Vacío ≠ roto: un estado sin datos debe ser visualmente distinguible de un estado de error/falla de carga.
- Capas operador vs backend: nunca se filtran internals (stack traces, SQL, nombres de proxy/IP, jerga técnica) a la superficie del operador — errores siempre humanizados.
- Grade A+/A/B/C/D/U es semántica de riesgo FIJA con mapeo de hue ya establecido en toda la app (grade-dot, badges, tinte de La Pantalla) — es vocabulario de producto, no decoración a reinventar.
- Visibilidad por rol: pares operador/operador no se ven entre sí; el superadmin (Robert) ve todo y es invisible para los demás en toques de cuenta.
- Terminología: "La Pantalla" = overlay de detalle de cuenta (identidad + saldo + movimientos + depósito/retiro en vivo). "Pool" = cuentas disponibles para operar. "Grade" = tier de riesgo/calidad de cuenta.

## Brand Commitments

Nombre del producto: Botmexico / botmex-dashboard. Paleta de acento base ya usada en el resto de la app (hue 160, oklch) y el sistema de "--gold" para CTAs de dinero — brand commitment de la app en general, no exclusivo de esta superficie. La superficie "La Pantalla" específicamente queda abierta a reformulación visual completa (pedido explícito del dueño del producto, 2026-07-28): se conserva la función, no el lenguaje visual actual de vidrio esmerilado.

## Evidence on Hand

Sin activos de marca externos (logo, fotografía, ilustración) — es una herramienta interna, no una superficie de cara al público. La evidencia real es el propio dataset operativo: cuentas, tarjetas, movimientos, grades — datos reales de producción, nunca inventar cifras de ejemplo que parezcan reales en capturas o demos.

## Product Principles

1. Frictionless es la norte: toda decisión de diseño se mide por si agrega o quita fricción al operador bajo presión de tiempo.
2. La herramienta debe ganarle en fluidez al sitio real que reemplaza, siempre.
3. Ningún dato útil se pierde ni se esconde; ningún control se elimina al mejorar la forma.
4. Confianza antes que estética: las señales que informan una decisión de dinero real (grade, saldo, estado) van primero, sin decoración que las demore.
5. Diseñado para foco frágil: información y controles agrupados en bloques ≤4 (Cowan 4±1), sin ruido de estado "todo bien", solo excepciones accionables.

## Accessibility & Inclusion

Usuario primario con TDAH diagnosticado — restricción de producto explícita y confirmada, no una preferencia estética: cualquier superficie nueva debe reducir carga cognitiva activamente (agrupar, jerarquizar, ocultar el "todo bien" por defecto) en vez de solo verse ordenada.
