# Handoff de Auditoría y Verificación: Rediseño Portal `/bet` (Vista Única)

> Documento de traspaso para **Claude Code** para auditar y validar los cambios realizados en el portal `/bet` de `botmex-dashboard`.

---

## 1. Contexto y Objetivos Cumplidos

Siguiendo el brief de producto (`PRODUCT.md`), el handoff de orquestación (`docs/plans/2026-08-04-handoff-orquestacion-portal-bet.md`) y las restricciones de diseño de Robert:

1. **Portal del operador de UNA SOLA VISTA** (`static/portal.html`, `static/portal.js`):
   - Se eliminaron las pestañas y botones de cambio de vista ("Misión Activa" vs "Mis Cuentas").
   - La sección de proceso en vivo (`#missionView`) y el grid de cuentas (`#accountsSection`) ahora **conviven en la misma pantalla**.
   - Se removió la visualización del `mission_id` técnico, tags internos y estadísticas de fallidos (`mv-stat` de fallidos descartado).
2. **Regla de Visibilidad Backend** (`app.py`, `operator_my_accounts`):
   - Ajustada la query SQLite para devolver solo cuentas con depósito **aprobado** (`d.status='approved'`) O **actualmente en proceso** (`a.locked_by IS NOT NULL` / ganchadas por el operador).
   - Cuentas fallidas o que nunca alcanzaron depósito desaparecen de la vista del operador.
3. **Persistencia & Repositorio**:
   - Cambios commiteados y pusheados a `origin/main` (commit `1e95694`).
   - Suite completa de backend `python -m pytest -q` ejecutada: **383 passed, 0 failed**.

---

## 2. Archivos Modificados a Auditar

- `app.py`: Endpoint `GET /api/operator/my-accounts` (L4258-L4295).
- `static/portal.html`: Estructura HTML y layout CSS de la vista única (L182, L292-L300).
- `static/portal.js`: Lógica SPA, renderizado de `#missionView` y eliminación de ruidos (L5-L10, L126-L133, L306-L330, L582-L586).
- `DESIGN.md`: Sección "Surface: /portal + /login".
- `docs/FRONTEND.md`: Sección "Portal de operadores (`/portal`)".
- `docs/AUDIT.md`: Registro de auditoría actualizado.
- `NEXT-SESSION.md`: Estado del repo al cierre.

---

## 3. Checklist de Verificación y Auditoría Sugerida

- [ ] **Verificación de backend**: Correr `python -m pytest -q` (debe dar 383 passed).
- [ ] **Auditoría de Visibilidad API**: Consultar `GET /api/operator/my-accounts` con una sesión de operador y comprobar que NO retorne cuentas con depósitos fallidos o sin `locked_by`.
- [ ] **Verificación Visual / UI**:
  - Levantar dev server (`python app.py` o TestClient).
  - Abrir `/user/{telegram_id}` en navegador/Playwright.
  - Comprobar que no hay tabs "Mis Cuentas" / "Misiones" en el header.
  - Probar con `?match=MISSION_ID` y confirmar que `#missionView` (barra de progreso) y el grid de cuentas se muestran simultáneamente.
  - Confirmar que no hay `mission_id` impreso en el banner.
- [ ] **Deploy a KVM4**: Disparar deploy a producción si la verificación visual es satisfactoria.

---

*Handoff generado automáticamente para el ciclo de revisión en Claude Code.*
