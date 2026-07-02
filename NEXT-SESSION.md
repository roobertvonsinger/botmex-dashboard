# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso

**Auditoría de los 7 flujos → deployada y verificada en vivo.** `94fd057` (3 críticos + 5 mayores) ya está en KVM4, con smoke funcional completo y C1/C2 confirmados con tráfico real. Cierra el ciclo de "flujos" por ahora. **Próxima sesión: pivote a UI** (pedido explícito de Robert).

## ▶ Con qué arrancas (1ra acción concreta)

**Preguntar a Robert qué área de UI ataca** — no hay spec en cola (tanda 5 ya cerrada en `c044428`). Candidato conocido: el drawer de bloqueo diferenciado (SA agarra cuenta = invisible/permanente vs operador 2h/24h) sigue pendiente del lado UI — ver memoria `project_bloqueo_diferenciado_historial`. Si Robert trae algo nuevo, usar `superpowers:brainstorming` antes de tocar código.

## 🧭 Recomendación de approach

Sin spec, no asumir alcance — dejar que Robert defina objetivo concreto primero (brainstorming corto), armar spec solo si es sustancial, y evitar reabrir tanda 5 sin necesidad. Los pendientes de flujos (M3/M4/M7/M9 + 15 menores) quedan en pausa hasta que Robert los retome explícitamente.

## ⏳ Pendientes próximos

- [ ] **UI — próxima sesión.** Sin spec en cola; arrancar preguntando a Robert.
- [ ] **C3 doble cargo** — el índice ya está confirmado en prod, pero el guard (`SUBMIT_ERROR`/`UNKNOWN_TXN_STATUS_n` terminal, evita re-submit) NO se probó en vivo — no hubo depósito real en la ventana de smoke. Verificar en el próximo run real o forzar un caso.
- [ ] **Decisión M3** — ¿"Actualizar visibles" respeta cooldown 30s o siempre fuerza live? (con C1+C2 el costo por click ya bajó mucho).
- [ ] **Decisión M4** — stagger inter-task en `REFRESH_PARALLEL=8`; medir 429 real con pool nuevo antes de tocar.
- [ ] **Decisión M7** — grade `B` absorbe masacres recientes (15-59d) etiquetándolas "alta probabilidad de éxito"; rebalanceo umbrales V10 (criterio de negocio).
- [ ] **Decisión M9** — `web_auth.py:98 MASTER_PASSWORD="Kashau2022"` hardcodeado (muerto, solo `_legacy/`) → mover a env o borrar.
- [ ] **Menores (15)** de valor: instrumentar `captcha_cost` (medir drenaje), `deposit_attempts.source` por flujo, código muerto (`_drain_stale_tokens`/`_ensure_fresh_captcha`, `_get_grade`, constantes prewarm), `velocity_skip` duerme 30s dentro del `gather`, balance_before/after NULL, proxy/IP visible a admin. Detalle completo en `docs/ERRORS.md` §Auditoría 2026-07-02.
- [ ] **(heredado) Pendientes proxy**: activar toggle "IP quality" en panel DataImpulse (no verificable por código), confirmar blocklist payment-sites con soporte, cablear `StickySessionManager` con el lote nuevo (`docs/plans/login-orchestration-rework.md` §6).
- [ ] **(heredado) KVM4**: carpetas `/docker/{litellm-gvuk,n8n-mgzp,agent-zero-6fhd,sim-studio-12dk,open-webui-m0vf,ollama-zzvy,hermes-agent-0kl1}` quedaron en disco (solo compose+.env, sin contenedor/imagen) — decisión pendiente de Robert si se borran del todo o se quedan por si se revive algo.

## ✅ Hecho esta sesión (2026-07-02, sesión 2 — deploy + verificación en vivo + higiene KVM4)

- **Deploy `94fd057` a KVM4**: scp de `app.py`/`deposits.py`/`prewarm.py` + `docker compose kill -s SIGKILL web && up -d web`. md5 remoto == local confirmado.
- **Smoke funcional**: health 200 · índice `idx_acct_txn_email_lower` creado · M6 auth 401 con password vacío · router `/deposits/multi/stream` carga (401, no 503) · logs de arranque sin errores.
- **C1/C2 verificados EN VIVO** (Robert corrió "Actualizar visibles" real): 4 cuentas cache-hit → log `[gentle_login] {email} JWT cache HIT (sin captcha)` + `process_log.jwt_from_cache=true`, cero captcha. 8 cache-miss → login real con proxy, **cero líneas "proxyless" en todo el log** (guard C1 nunca se activó porque el pool de 102 proxies respondió). 2× `httpcore.ProxyError: 504` transitorio del gateway DataImpulse — no relacionado al fix.
- **JWT caching confirmado óptimo**: `login_orchestrator.py:250` ya preserva el JWT mientras tenga >60s de vida y solo cae a captcha si de verdad venció. TTL real medido del JWT de BetMexico: **~7 días**. No requiere cambio — Robert preguntó, se verificó con datos reales de DB, ya es el comportamiento correcto.
- **KVM4 — cron de reinicio**: instalado `0 0,12 */4 * *` (reinicio cada 4 días a las 00:00 y 12:00, root crontab, log en `/var/log/scheduled-reboot.log`). Todos los contenedores verificados `unless-stopped` + Docker `enabled` al boot antes de instalar.
- **KVM4 — limpieza**: eliminados (contenedores+volúmenes+imágenes) `litellm-gvuk`, `n8n-mgzp`, `agent-zero-6fhd`, `sim-studio-12dk`, `open-webui-m0vf`, `ollama-zzvy`, `hermes-agent-0kl1` — sin uso real (solo tráfico de bots/crawlers en logs), confirmado por Robert. Memoria: 5.3Gi→2.0Gi usada · disco: 12% uso (170GB libres, era ~23GB usados antes de medir bien el delta exacto).

## 🔧 Decisiones tomadas (esta sesión)

- **Deploy ejecutado de corrido** tras luz verde de Robert (regla `feedback_deploy_pace`).
- **KVM4 reinicio**: cada 4 días a las 00:00 y 12:00, vía cron nativo de la VPS (no Hostinger API) — elegido por Robert.
- **KVM4 limpieza**: se conservan las carpetas `/docker/<nombre>` (compose+.env) de los servicios eliminados por si se revive config — no se pidió borrar disco/config, solo runtime.
- **openclaw-ruth es de Ruthopia, no de RITA** — corregido; yo lo había asumido mal. Guardado en memoria para no repetir.
- **Próxima sesión = UI**, pedido explícito de Robert — flujos/backend quedan en pausa salvo que él los retome.

## 🖥️ Estado del sistema al cerrar

`betmexico-web` **Up** (reiniciado hoy, corriendo `94fd057`) · `betmexico-bot` **Up 6 días** · health **200** (923 cuentas) · pool = **102 proxies** (100 DataImpulse sticky + 2 NodeMaven) · login **funcionando** (C1/C2 confirmados con tráfico real, sin fuga proxyless) · KVM4 memoria **2.0Gi/15Gi** usada, disco **12%** (170GB libres) · cron de reinicio cada 4 días activo.

## Notas de sesión `[MANUAL]`

<!-- Apuntes rápidos de sesión activa — borrar entre sesiones -->
