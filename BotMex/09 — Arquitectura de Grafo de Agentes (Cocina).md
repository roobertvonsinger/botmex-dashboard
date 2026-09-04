# 09 — Arquitectura de Grafo de Agentes (El Modelo de la Cocina)

> **Inspiración:** *"What they are and how to organize an AI agent system in 2026"* (Video ID: `ww0-SKM6uRE`).
> **Canvas Asociado:** [[09 — Arquitectura de Grafo de Agentes (Cocina).canvas]]
> **Propósito:** Eliminar la confusión mental de Robert transformando procesos complejos en estaciones de trabajo visuales, independientes y auto-sanables en Obsidian Canvas.

---

## 🍳 1. La Metáfora Central: La Cocina de Restaurante vs El Monolito

### El Error Común (El "Mesero Todólogo" o Script Monolítico)
Intentar que un solo modelo, script de 2,000 líneas o prompt gigante haga todo a la vez:
1. Recibe la orden del cliente.
2. Va a la bodega a buscar ingredientes.
3. Corta cebollas, prende la estufa, asa la carne.
4. Cobra la cuenta en la caja.
5. Si se le quema una papa, **tira toda la cena a la basura, quema el restaurante y cancela el servicio**.

> **En BetMexico sucedía esto:** Si el captcha fallaba con 406 o la pasarela daba 429 transitorio, el script mataba la cuenta a `DEAD`, descartaba el lote y congelaba la misión. ¡Un desastre innecesario!

### La Solución 2026 (El Grafo de Agentes / Estaciones de Cocina)
Una cocina profesional de alta gama divide el trabajo en **estaciones de trabajo especializadas (Nodos)** coordinadas por un flujo continuo:

```
[📋 Maitre d' / Router] ──► [🥗 Prep Station] ──► [🔥 Cook Station] ──► [👨‍🍳 Taste Tester / Checker] ──► [🍽️ Plating / Delivery]
                                                                                   │ (¿Quemado?)
                                                                                   ▼
                                                                  [🩹 Local Self-Healing / Recuperación]
                                                                        (Repite solo esa estación)
```

---

## 🧩 2. Los 6 Tipos de Nodos (Tu Caja de Herramientas Mental)

Cuando vayas a crear o analizar cualquier flujo en Obsidian Canvas, nunca pongas cajas al azar. Todo nodo en tu mente debe pertenecer a uno de estos 6 roles:

| Tipo de Nodo | Rol en la Cocina | Rol en BetMexico / Ecosistema | Color Canvas |
|---|---|---|---|
| **1. Router / Ingesta** | **Maitre d' / Mesero** | Recibe `/bet`, valida sintaxis de pipes, decide si es misión manual, batch o programada. | **Cyan ("5")** |
| **2. Prep / Normalizer** | **Estación de Picado** | Sanitiza datos, consulta BIN Intelligence, revisa liveness en Ruthopia Bridge sin tocar saldo. | **Morado ("6")** |
| **3. Cook / Worker** | **Línea de Fuego** | Ejecuta la acción pesada (`deposits.py`, rotación con `call_with_proxy_failover`, resuelve captcha). | **Morado ("6")** |
| **4. Checker / Evaluador** | **Chef de Calidad (Taste Tester)** | Audita la salida sin asumir éxito: `classify_deposit_status`, algoritmo V10, detecta 3DS. | **Amarillo ("3")** |
| **5. Self-Healing / Router de Error** | **Cesto de Descarte & Sustitución** | **LA CLAVE DEL VIDEO:** Si la papa se quema (`BANK_REJECTED`), la cuenta NO muere. Se jubila la tarjeta y se pide otra. Si hay 429, entra a cooldown 24h. | **Naranja ("2") / Rojo ("1")** |
| **6. Delivery / Terminal** | **Emplatado y Servicio** | Persiste en SQLite WAL, asocia tarjeta casada 1:1, emite evento SSE y entrega ficha SPEI en Telegram. | **Verde ("4")** |

---

## 💡 3. El Secreto del Auto-Healing Local ("Burned Potatoes")

El principio más potente del video es la **Preservación del Estado Global**:

1. **Fallo Aislado:** Si un nodo falla, la culpa es del *ingrediente* o del *intento local*, jamás del ecosistema completo.
2. **Re-Ruta Quirúrgica:**
   - ¿Tarjeta declinada por banco? → Nodo de Jubilación de Tarjeta. La cuenta de casino se mantiene limpia en pool.
   - ¿Proxy sin saldo (HTTP 402)? → Nodo de Failover de Proxy. Conmuta de host en <1s sin despertar al operador.
   - ¿HTTP 429 o 406 en Captcha? → Nodo de Gentle Backoff. No matar la cuenta; dejarla descansar en cuarentena.
3. **Cero Sobre-Ingeniería:** Cada nodo tiene una sola entrada clara (JSON/Dict) y una sola salida validada.

---

## 🎨 4. Convención Estética Soberana para Obsidian Canvas

Para evitar la sobrecarga cognitiva y el desorden visual:
1. **Flujo de Izquierda a Derecha (`LR`):** El tiempo y los datos fluyen de izquierda a derecha; las ramas de error bajan en vertical.
2. **Grupos Visuales Claros:** Encapsula fases relacionadas (ej. "FASE 1: PREPARACIÓN", "FASE 2: EJECUCIÓN", "FASE 3: RECUPERACIÓN").
3. **Anatomía de Cada Nodo de Texto:**
   - **Título con Icono:** `### 🍳 Estación: Nombre`
   - **Input:** Qué datos o estado recibe.
   - **Lógica / Guardrail:** La regla dura que no se puede romper.
   - **Output Exitoso:** A dónde va si todo sale bien.
   - **Ruta de Fallo:** A qué nodo de recuperación se desvía si falla.
4. **Semántica de Color Inmutable:**
   - `5` (Cyan): Entradas humanas, Telegram, Web UI, SSE.
   - `6` (Morado): Motores, orquestadores, ejecuciones de fondo.
   - `3` (Amarillo): Inspecciones, Checkers de calidad, decisiones.
   - `4` (Verde): Éxitos terminales, dinero asegurado, sesiones activas.
   - `2` (Naranja): Reintentos transitorios, advertencias, cooldowns.
   - `1` (Rojo): Tarjetas quemadas, guardrails inmutables, 403 Forbidden.
