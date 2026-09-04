# 05 — Validación de Tarjetas, BIN Intelligence & Liveness

> **Ubicación:** `card_checker.py`, `bin_intelligence.py`, `shared/betmexico_payment_analyzer.py`.
> **Canvas Detallado:** [[05 — Validación de Tarjetas.canvas]]
> **Modelo Mental:** [[09 — Arquitectura de Grafo de Agentes (Cocina)]] (Estación de Picado y Control de Calidad de Ingredientes).

---

## 🔍 Ficha Técnica y Ciclo de Vida de Tarjetas

### 1. Canales de Ingesta
- **Ingesta Manual:** Comando `/check` en Telegram con pipes de tarjetas.
- **Cosecha Autónoma:** Ingesta continua desde Ruthopia Bridge hacia la base central `data/vault_cards.db`.

### 2. BIN Intelligence & Algoritmo V10
- Clasifica el BIN (primeros 6 a 8 dígitos) determinando:
  - Banco emisor y país.
  - Tipo: Débito o Crédito.
  - Afinidad histórica de pasarela y tasa de conversión.
  - Nivel de fricción de 3D-Secure (3DS).

### 3. Pre-check de Liveness (Ruthopia Bridge `:8787`)
- Consulta el servicio de liveness sin impactar pasarelas de pago ni generar cobros reales.
- **Clasificación de Liveness (`liveness_kind`):**
  - `live`: Tarjeta viva comprobada.
  - `tol_bin`: BIN tolerante a reintentos (ej. 416916, 557908).
  - `dead`: Tarjeta sin fondos o cancelada; se descarta antes de entrar al matchmaker.

### 4. Máquina de Estados de la Tarjeta
| Estado | Descripción | Transición |
|---|---|---|
| `available` | Tarjeta verificada y lista en el pool | Pasa a `in_use` al entrar a una misión `/bet`. |
| `married` | Aprobada y vinculada 1:1 de forma permanente | Inmutable (`is_married = 1`); solo puede recargar su cuenta vinculada. |
| `burned` | Declinada por banco emisor o tras 3 intentos fallidos | Se retira definitivamente del pool. |
| `locked` | Bloqueada en otra cuenta de casino ajena | Jubilada de inmediato sin reintentos. |
