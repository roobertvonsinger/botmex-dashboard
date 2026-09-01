"""Regresión: el semáforo global de misiones (`_mission_sem`) NO debe leakearse
cuando el cliente aborta el stream del matchmaker tempranamente.

Bug 2026-07-17 (confirmado en prod): `_mission_sem.acquire()` estaba en la 1ª
línea de `gen()`, FUERA del `try/finally` que lo libera. Si la conexión SSE se
aborta durante el `yield 'start'` (cerrar pestaña / red / doble-submit del
front), salta `GeneratorExit` antes de entrar al `try` → el permiso NUNCA se
devuelve. Con `MISSION_MAX_CONCURRENT=2`, dos abortos así saturan el semáforo y
TODO matchmaker rebota con 429 "Ya hay 2 misiones activas" hasta el próximo
restart. El operador (admin) queda bloqueado; el SA no lo nota porque su
depósito single (`execute-stream`) no toca este semáforo.
"""
import asyncio
import importlib

import deposits


class _FakePool:
    """Pool de captcha fake — no se llega a usar (abortamos en 'start'), pero
    `_load_deps` debe devolver algo no-None para no cortar con 503."""
    async def start_factory(self):
        return None

    async def prefetch(self, n):
        return None

    async def stop(self):
        return None


class _Req:
    """Request mínimo: multi_stream solo hace `await request.json()`."""
    def __init__(self, payload):
        self._p = payload

    async def json(self):
        return self._p


def test_mission_semaphore_released_on_early_client_abort(seed_db, monkeypatch):
    import app as app_mod
    importlib.reload(app_mod)  # corre _migrate() sobre la BD seed (agrega cooldown_until)
    monkeypatch.setattr(deposits, "_load_deps", lambda: (lambda *a, **k: _FakePool()))

    # SA para saltar el lock por-cuenta y aislar el comportamiento del semáforo.
    user = {"role": "superadmin", "telegram_id": 1341812706, "username": "robertvs"}
    req = _Req({"account_ids": [2], "cards": ["4222222222222222|12|30|321"], "amount": 50})

    async def scenario():
        deposits._mission_sem = asyncio.Semaphore(deposits.MISSION_MAX_CONCURRENT)
        start_val = deposits._mission_sem._value
        resp = await deposits.multi_stream(req, user)
        agen = resp.body_iterator
        async for chunk in agen:
            text = chunk.decode() if isinstance(chunk, (bytes, bytearray)) else chunk
            if '"start"' in text:
                break
        acquired_val = deposits._mission_sem._value
        await agen.aclose()          # simula el aborto de la conexión SSE del cliente
        await asyncio.sleep(0)        # deja correr GeneratorExit → finally
        released_val = deposits._mission_sem._value
        return start_val, acquired_val, released_val

    start_val, acquired_val, released_val = asyncio.run(scenario())
    assert acquired_val == start_val - 1, "el generator debe adquirir 1 permiso al arrancar"
    assert released_val == start_val, (
        f"semáforo leakeado tras abort temprano: quedó en {released_val}, "
        f"esperado {start_val} (acquire fuera del try/finally)"
    )


def test_mission_semaphore_released_on_normal_completion(seed_db, monkeypatch):
    """Happy path: cuando la misión termina normal (evento 'done'), el semáforo
    también debe liberarse. Cuenta en cooldown → 0 pares → 'done' inmediato."""
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(deposits, "_load_deps", lambda: (lambda *a, **k: _FakePool()))
    deposits._set_account_cooldown("b@test.com", minutes=60)  # fuerza 0 pares → 'done'

    user = {"role": "superadmin", "telegram_id": 1341812706, "username": "robertvs"}
    req = _Req({"account_ids": [2], "cards": ["4222222222222222|12|30|321"], "amount": 50})

    async def scenario():
        deposits._mission_sem = asyncio.Semaphore(deposits.MISSION_MAX_CONCURRENT)
        start_val = deposits._mission_sem._value
        resp = await deposits.multi_stream(req, user)
        saw_terminal = False
        async for chunk in resp.body_iterator:  # consume completo (sin abortar)
            text = chunk.decode() if isinstance(chunk, (bytes, bytearray)) else chunk
            if '"done"' in text or '"fatal"' in text:
                saw_terminal = True
        return start_val, deposits._mission_sem._value, saw_terminal

    start_val, final_val, saw_terminal = asyncio.run(scenario())
    assert saw_terminal, "la misión debe emitir un evento terminal (done/fatal)"
    assert final_val == start_val, "semáforo debe liberarse tras terminación normal"
