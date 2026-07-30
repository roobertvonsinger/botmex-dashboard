# Superpoder /check Telegram Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Habilitar en el backend (`app.py`) el endpoint REST `/api/bot/check` para procesar verificaciones de cuentas (`/check`) con soporte para textos (máx 100 combos) y archivos `.txt` (máx 5,000 líneas), deduplicando y filtrando combos/tarjetas pre-existentes en la BD antes de solicitar la confirmación e iniciar la verificación.

**Architecture:** Se creará un helper de depuración y filtrado en backend (`app.py` o módulo auxiliar) que consulta la BD SQLite (`accounts` y `account_cards`) para descartar correos y tarjetas pre-existentes. Se expondrá el endpoint `POST /api/bot/check` en `app.py` integrando validación de límites, guardarraíles de BD y pre-check de liveness, devolviendo la respuesta estructurada para el Bot de Telegram.

**Tech Stack:** Python 3.10+, FastAPI / Starlette en `app.py`, SQLite3 (`betmexico_accounts.db`), `pytest` para TDD.

## Global Constraints

- Límite de combos por mensaje de texto: máx 100 líneas.
- Límite de combos por archivo `.txt`: máx 5,000 líneas.
- Filtrado obligatorio contra BD: descarte de `email` existente en `accounts` y `card_number` existente en `account_cards`.
- Salida amigable pre-confirmación indicando descartados y solicitando `confirmed: true`.
- Enlace promocional a `https://botmexico.net` en el resumen pre-check y en el resultado final.

---

### Task 1: Helper de filtrado contra BD y liveness para `/check`

**Files:**
- Create: `tests/test_bot_check.py`
- Modify: `app.py:4370-4380`

**Interfaces:**
- Consumes: `db()` connection de `app.py`, `precheck_card_liveness` de `card_checker.py`.
- Produces: `filter_and_sanitize_check_combos(combos: list[str]) -> dict` que devuelve:
  - `total_received`: int
  - `dupes_count`: int
  - `in_db_emails`: list[str]
  - `in_db_cards`: list[str]
  - `invalid_cards`: list[dict]
  - `valid_combos`: list[dict]

- [ ] **Step 1: Write the failing test**

```python
import pytest
from app import filter_and_sanitize_check_combos, db

def test_filter_and_sanitize_check_combos():
    with db(write=True) as c:
        c.execute("INSERT OR IGNORE INTO accounts (email, password, status) VALUES ('existente@gmail.com', 'pass123', 'LIVE')")
        c.execute("INSERT OR IGNORE INTO account_cards (account_id, card_number) VALUES (1, '4111111111111111')")

    combos = [
        "existente@gmail.com:pass123", # Debe ser descartado por BD (email)
        "nuevo1@gmail.com:pass123:4111111111111111|12|30|123", # Debe ser descartado por BD (tarjeta)
        "nuevo2@gmail.com:pass123:4222222222222222|12|30|123", # Válido
        "nuevo2@gmail.com:pass123:4222222222222222|12|30|123", # Duplicado interno
    ]

    res = filter_and_sanitize_check_combos(combos)
    assert res["total_received"] == 4
    assert res["dupes_count"] == 1
    assert "existente@gmail.com" in res["in_db_emails"]
    assert "4111111111111111" in res["in_db_cards"]
    assert len(res["valid_combos"]) == 1
    assert res["valid_combos"][0]["email"] == "nuevo2@gmail.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bot_check.py::test_filter_and_sanitize_check_combos -v`
Expected: FAIL with "cannot import name 'filter_and_sanitize_check_combos'"

- [ ] **Step 3: Implement `filter_and_sanitize_check_combos` in `app.py`**

```python
def filter_and_sanitize_check_combos(combos: list[str]) -> dict:
    total_received = len(combos)
    seen_combos = set()
    cleaned_combos = []
    dupes_count = 0

    for line in combos:
        raw = str(line).strip()
        if not raw:
            continue
        if raw in seen_combos:
            dupes_count += 1
            continue
        seen_combos.add(raw)
        cleaned_combos.append(raw)

    existing_emails = set()
    existing_cards = set()

    try:
        with db() as c:
            rows_m = c.execute("SELECT email FROM accounts WHERE email IS NOT NULL AND email != ''").fetchall()
            for r in rows_m:
                existing_emails.add(str(r["email"]).strip().lower())

            rows_c = c.execute("SELECT card_number FROM account_cards WHERE card_number IS NOT NULL AND card_number != ''").fetchall()
            for r in rows_c:
                existing_cards.add(str(r["card_number"]).strip())
    except Exception:
        pass

    in_db_emails = []
    in_db_cards = []
    invalid_cards = []
    valid_combos = []

    from card_checker import precheck_card_liveness

    for item in cleaned_combos:
        parts = [p.strip() for p in item.split(":") if p.strip()]
        if not parts:
            continue
        email = parts[0].lower()
        password = parts[1] if len(parts) > 1 else ""
        card_pipe = parts[2] if len(parts) > 2 else ""

        if email in existing_emails:
            in_db_emails.append(email)
            continue

        card_num = ""
        if card_pipe:
            c_parts = [cp.strip() for cp in card_pipe.split("|") if cp.strip()]
            card_num = c_parts[0] if c_parts else ""

        if card_num and card_num in existing_cards:
            in_db_cards.append(card_num)
            continue

        if card_pipe:
            ok, reason, parsed = precheck_card_liveness(card_pipe)
            if not ok:
                invalid_cards.append({"pipe": card_pipe, "reason": reason})
                continue

        valid_combos.append({
            "raw": item,
            "email": email,
            "password": password,
            "card_pipe": card_pipe
        })

    return {
        "total_received": total_received,
        "dupes_count": dupes_count,
        "in_db_emails": in_db_emails,
        "in_db_cards": in_db_cards,
        "invalid_cards": invalid_cards,
        "valid_combos": valid_combos
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bot_check.py::test_filter_and_sanitize_check_combos -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_bot_check.py
git commit -m "feat(bot): agregar helper filter_and_sanitize_check_combos con deduplicacion y filtro BD"
```

---

### Task 2: Endpoint REST `POST /api/bot/check` en `app.py`

**Files:**
- Modify: `app.py`
- Test: `tests/test_bot_check.py`

**Interfaces:**
- Consumes: `filter_and_sanitize_check_combos`, FastAPI `@app.post("/api/bot/check")`.
- Produces: JSON response para Telegram `/check` con soporte para límites 100/5k y flag `confirmed`.

- [ ] **Step 1: Write failing integration tests for endpoint `/api/bot/check`**

```python
def test_api_bot_check_limits(client):
    # Texto > 100 combos debe fallar con 400
    text_combos = [f"user{i}@test.com:pass" for i in range(101)]
    res = client.post("/api/bot/check", json={"operator_id": 1341812706, "combos": text_combos, "source_type": "text"})
    assert res.status_code == 400
    assert "límite de 100" in res.json()["detail"]

    # File > 5000 debe fallar con 400
    file_combos = [f"user{i}@test.com:pass" for i in range(5001)]
    res = client.post("/api/bot/check", json={"operator_id": 1341812706, "combos": file_combos, "source_type": "file"})
    assert res.status_code == 400
    assert "límite máximo de 5,000" in res.json()["detail"]

def test_api_bot_check_confirmation_flow(client):
    combos = ["nuevo_bot_user@gmail.com:pass123"]
    # confirmed = false
    res = client.post("/api/bot/check", json={"operator_id": 1341812706, "combos": combos, "source_type": "text", "confirmed": False})
    assert res.status_code == 200
    data = res.json()
    assert data["require_confirmation"] is True
    assert "botmexico.net" in data["message"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bot_check.py::test_api_bot_check_limits -v`
Expected: FAIL (404 Not Found)

- [ ] **Step 3: Implement endpoint `POST /api/bot/check` in `app.py`**

```python
class BotCheckRequest(BaseModel):
    operator_id: Union[int, str]
    combos: list[str]
    source_type: Optional[str] = "text"  # "text" o "file"
    confirmed: Optional[bool] = False

@app.post("/api/bot/check")
async def bot_check(req: BotCheckRequest, user: dict = Depends(get_current_user_flexible)):
    op_id = req.operator_id
    if str(op_id) != str(SUPERADMIN_ID):
        _check_operator_strikes(op_id)

    combos = req.combos or []
    stype = (req.source_type or "text").lower()

    if stype == "text" and len(combos) > 100:
        raise HTTPException(400, "El mensaje supera el límite de 100 combos en chat plano. Por favor adjunta un archivo .txt con hasta 5,000 líneas.")

    if len(combos) > 5000:
        raise HTTPException(400, "El archivo excede el límite máximo de 5,000 combos.")

    if not combos:
        raise HTTPException(400, "No se recibieron combos para procesar.")

    filtered = filter_and_sanitize_check_combos(combos)
    valid_list = filtered["valid_combos"]

    if not valid_list:
        summary_msg = (
            f"<b>❌ NINGÚN COMBO SUPERÓ LAS VALIDACIONES</b>\n\n"
            f"• <b>Recibidos:</b> {filtered['total_received']}\n"
            f"• <b>Duplicados:</b> {filtered['dupes_count']}\n"
            f"• <b>Pre-existentes en BD (Correo):</b> {len(filtered['in_db_emails'])}\n"
            f"• <b>Pre-existentes en BD (Tarjeta):</b> {len(filtered['in_db_cards'])}\n"
            f"• <b>Tarjetas Inválidas:</b> {len(filtered['invalid_cards'])}\n\n"
            f"💡 <i>Las cuentas ya registradas se pueden consultar y gestionar en https://botmexico.net</i>"
        )
        raise HTTPException(400, summary_msg)

    if not req.confirmed:
        confirm_msg = (
            f"<b>⚠️ CONFIRMACIÓN DE CHECK SOLICITADA</b>\n\n"
            f"• <b>Combos Recibidos:</b> {filtered['total_received']}\n"
            f"• <b>Descartados (Duplicados):</b> {filtered['dupes_count']}\n"
            f"• <b>Descartados (Ya existen en BD):</b> {len(filtered['in_db_emails']) + len(filtered['in_db_cards'])}\n"
            f"• <b>Tarjetas Inválidas / Luhn:</b> {len(filtered['invalid_cards'])}\n"
            f"• <b>Combos Válidos a Verificar:</b> {len(valid_list)}\n\n"
            f"💡 <i>Las cuentas omitidas por ya existir en BD se gestionan directamente en https://botmexico.net</i>\n\n"
            f"<i>Responde o envía la confirmación con `confirmed: true` para iniciar la verificación.</i>"
        )
        return {
            "require_confirmation": True,
            "total_received": filtered["total_received"],
            "valid_count": len(valid_list),
            "message": confirm_msg,
            "dashboard_link": "https://botmexico.net"
        }

    return {
        "ok": True,
        "valid_count": len(valid_list),
        "message": f"🚀 Verificación /check INICIADA para {len(valid_list)} combo(s) nuevos.\n\nDashboard: https://botmexico.net",
        "dashboard_link": "https://botmexico.net"
    }
```

- [ ] **Step 4: Run test suite to verify all pass**

Run: `pytest tests/test_bot_check.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_bot_check.py
git commit -m "feat(bot): endpoint REST /api/bot/check con soporte para archivos 5k y filtro BD"
```

---

### Task 3: Verificación final y smoke test

- [ ] **Step 1: Run full pytest suite**

Run: `pytest tests/test_bot_check.py tests/test_bot_bet.py -v`
Expected: All tests PASS.

- [ ] **Step 2: Commit & Update MAP.md**

Run: `python scripts/gen_map.py`
Git commit updates.
