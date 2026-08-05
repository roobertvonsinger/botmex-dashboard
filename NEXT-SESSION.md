# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

Sesión 2026-08-04 (sexta parte). **Rediseño completo del portal de operadores (`/user/{id}`) a VISTA ÚNICA.**

- Backend: Query `GET /api/operator/my-accounts` ajustada para incluir cuentas aprobadas (`d.status='approved'`) O actualmente en proceso (`a.locked_by IS NOT NULL`), filtrando cuentas fallidas/abandonadas.
- Frontend (`portal.html`, `portal.js`):
  1. Eliminados botones/tabs de cambio de vista ("Misión Activa" vs "Mis Cuentas").
  2. `#missionView` (progreso vivo) y `#accountsSection` (cuentas del operador) conviven en la misma vista sin taparse.
  3. Eliminados IDs de misión (`mission_id`), tags técnicos y estadísticas de intentos fallidos (`mv-stat` de fallidos descartado).
  4. Suite de tests completa pasó a **383/383** verde.

---

## ▶ Con qué arrancas (PRIMERA acción)

1. Ejecutar `python -m pytest -q` — debe dar **383 passed**.
2. Verificar visualmente o con Robert el render de la vista única integrada del portal.
3. Si la confirmación visual de Robert es positiva, proceder al deploy a KVM4.

---

## 🖥️ Estado del sistema al cerrar (2026-08-04, sexta parte)

- **Repo**: Cambios aplicados en `main`. `git status` pendiente de commit/review.
- **Tests**: 383/383 verdes.
