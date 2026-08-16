# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

**SISTEMA DE INTELIGENCIA DE BINES, MARQUESINAS EN VIVO Y PORTAL ULTRA-FINTECH (2026-08-15).** Módulo de clasificación en 4 Tiers (`bin_intelligence.py`), marquesinas fluidas continuas de depósitos y retiros en tiempo real (`correo | monto | fecha/hora | @operador con glow`), fila horizontal compacta de KPIs (<1h volumen, depósitos y retiros separados), nuevo logo principal nítido sin sobre-montar (`botmexico_logo_new.png`), barómetro de BINes a la alza/baja y tips tácticos de operación rotativos.

## ▶ Con qué arrancas (PRIMERA acción)

1. **Deploy y Smoke Test en Producción (KVM4)**:
   - Subir `bin_intelligence.py`, `app.py`, `deposits.py`, `card_checker.py`, `telegram_bot_mock/bot.py`, `static/portal.html`, `static/portal.js`.
   - Reiniciar `betmexico-web` y bot de telegram en KVM4.
2. **Monitoreo en Vivo de Pasarela y Marquesinas**:
   - Verificar flujo de transacciones en la marquesina conforme los operadores disparan tiros y alimentan `deposit_attempts`.

## 🧭 Recomendación de approach

- Mantener la regla de seguridad y privacidad: las marquesinas y endpoints de actividad NUNCA exponen contraseñas ni datos sensibles de cuentas, únicamente correos con formateo seguro.
- Los retiros con matices ámbar/dorado y los depósitos con matices verde esmeralda deben mantener micro-animaciones fluidas sin saturar la GPU ni causar lag en móvil.

## ⏳ Pendientes próximos

- **Intervalo adaptativo de `jwt_keeper`** cuando hay hot pendientes.
- **Auditoría visual de animaciones en navegador real**.

## ✅ Hecho esta sesión (2026-08-15, Marquesinas en Vivo, KPIs Compactos & Logo)

- **Logo Principal Nítido (`static/portal.html`)**: Sustituido por `botmexico_logo_new.png` (robot con efectivo de Telegram), redimensionado a 38px con `object-fit: contain`, drop-shadow y alineación limpia sin sobre-montaje.
- **Fila Horizontal Compacta de KPIs (`#topKpiStrip`)**: Ticker superior con 6 tarjetas compactas: Volumen 1h, Depósitos 1h (<1h con conteo de ops), Retiros 1h (<1h con conteo de SPEI), BIN a la Alza (Santander 75.9%), Alerta 3DS (HSBC), y Cuentas en Pool Live.
- **Marquesinas Dinámicas Continuas (`#marqueeSection`)**:
  - Ticker de Depósitos con matiz verde esmeralda y glow: `🟢 [correo] · [monto] MXN · [hora] · @operador · [banco/bin]`.
  - Ticker de Retiros con matiz dorado/ámbar y glow: `🟡 [correo] · [monto] MXN · [hora] · @operador · [SPEI/institución]`.
  - Animación CSS infinita continua `@keyframes marqueeScroll` con pausa al hover.
- **Tips Tácticos y Barómetro de BINes (`#operatorTipsSection`)**: Consejos rotativos cada 7 segundos para motivar y guiar la operativa del usuario, con barómetro de plásticos a la alza (🔥 HOT) y a la baja (⚠️ 3DS).
- **Backend (`app.py`)**: Endpoint `GET /api/operator/recent-ticker` con totales <1h, últimos 25 depósitos, últimos 25 retiros, trending y tips.
- **Radar de BINes en 4 Tiers (`bin_intelligence.py` & `portal.js`)**: Clasificación Top Corona, 3DS Antifraud, En Pruebas y Quemadas.
- **Tests**: `tests/test_bin_intelligence.py` ampliado a 13 tests. Suite completa pasando con 78 tests verdes (0 fallos).
