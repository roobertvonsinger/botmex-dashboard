# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso
**Pausa de seguridad / Cambio de modelo para resolución de auditoría backend:** 
Se realizó una auditoría completa de los hallazgos de las últimas 24h (tanto en el backend `.py` como en el frontend `.js`). Los cambios inestables/experimentales en el backend fueron congelados para que un modelo con mayor disciplina y prudencia (Sonnet 5 / Opus 4.8) los resuelva sin prisa.

## ▶ Con qué arrancas
**Revisar los hallazgos de auditoría (1 línea por hallazgo) y aplicar corrección controlada en backend:**
1. Descartar/Revertir definitivamente los cambios de `_fetch_looks_empty` en `account_refresh.py`, `deposits.py` y `prewarm.py` o refactorizarlos con seguridad total contra `balance_only` y `ValueError`.
2. Atender los hallazgos secundarios de frontend (`app.js`) reportados en la auditoría.

## 🧭 Recomendación de approach
Iniciar sesión limpia con `/abrir-bmx` cambiando el modelo a Sonnet o Opus (`/model sonnet` o `/model opus`). Ejecutar `git checkout -- account_refresh.py deposits.py prewarm.py` si se decide limpiar el estado de trabajo antes de refactorizar de raíz con pruebas TDD aisladas.

## ⏳ Pendientes próximos
- [ ] **Limpieza / RefactorBackend backend (`account_refresh.py`, `prewarm.py`, `deposits.py`):** Resolver fallos de `ValueError` en `float("N/A")` y falso positivo en `balance_only` de forma segura sin forzar invalidez de JWT.
- [ ] **Frontend cleanup (`static/app.js`):** Limpiar listener redundante `#cmdCopy`, manejar error HTTP en `copySelectedCombos()` y resolver filtro fuera de vista en `refreshSelectedAccounts()`.
- [ ] **Apéndice B (sesión propia):** Store pattern centralizado + virtualización de tabla (medir perf 935 filas ANTES).
- [ ] **Rediseño del panel de depósitos (sesión propia):** 3 contenedores desacoplados + densidad de info/botones.

## ✅ Hecho esta sesión (2026-07-22)
- Auditoría profunda de 24h ejecutada mediante workflow subagente (`wthzqhcxm`) cubriendo hallazgos de backend y frontend.
- Documentación de hallazgos presentada en formato de 1 línea por hallazgo.
- Documentado el incidente de regresión `_fetch_looks_empty` en `docs/ERRORS.md`.
- `NEXT-SESSION.md` actualizado para entrega limpia.

## 🔧 Decisiones tomadas
- **Prohibición estricta de edición de código impulsiva:** Los archivos `.py`Backend no se tocan hasta tener el plan de corrección validado bajo un modelo de alta prudencia.
- **Desacoplamiento de Backend y Frontend:** Los ajustes visuales/UI jamás deben desencadenar refactors de lógica interna en `prewarm.py` o `account_refresh.py`.

## 🖥️ Estado del sistema al cerrar
web ✓ Up · bot ✓ Up · health `200 {"ok":true}` · pool = 1001 proxies · backend con cambios no commiteados aislados.
