# Referencias — Glosario de Decisiones

- **Married Card (Tarjeta Casada):** Regla inviolable. 1 Tarjeta = 1 Cuenta BetMexico para siempre. Reutilizarla en otra cuenta resulta en baneo fulminante de ambas.
- **Cuotas Tier 40/40/20:** Regla de selección que distribuye la misión: 40% cuentas Tier A (altas), 40% Tier B (medias), 20% Tier C (bajas).
- **Piso Anti-Huella (45-60s):** Tiempo de espera inicial en estado `preparing` antes de tirar depósitos, simulando navegación humana.
- **Transitorio (`MATCH_TRANSIENT_RETRIES = 4`):** Fallos de red o errores 5xx de pasarela que admiten hasta 4 reintentos con 25s de gap sin quemar la tarjeta.
- **429 Rate Limit:** Bloqueo temporal por exceso de peticiones. NO debe matar la cuenta a `DEAD`; debe mandarla a cooldown de 24h.
