"""Tests de account_refresh.select_refresh_candidates_healthy — lógica pura.

Es la pieza crítica: si selecciona una cuenta CON JWT expirado, el ciclo pega
un fetch con un token muerto (401 silencioso, gasto sin retorno) en vez de
dejar esa cuenta a jwt_keeper (que sí re-loguea). Por eso se prueba sin BD ni
deps del bot, igual que test_jwt_keeper.py.
"""
from account_refresh import (
    select_refresh_candidates_healthy, is_hot_account, DEFAULT_GRADES,
)

NOW = 1_800_000_000
H = 3600
NOW_ISO = "2026-08-04T12:00:00+00:00"


def _acc(email, *, status="LIVE", grade="B", jwt_exp=None, locked_by=None,
         published=1, last_checked_at=None, hot=False):
    return {
        "email": email, "status": status, "grade": grade,
        "jwt_expires_at": jwt_exp, "locked_by": locked_by,
        "published_to_pool": published, "last_checked_at": last_checked_at,
        "hot": hot,
    }


def _run(rows, *, batch_max=40, grades=DEFAULT_GRADES, sa_tokens=None):
    sa_tokens = sa_tokens if sa_tokens is not None else ["robertvs", "1341812706"]
    return select_refresh_candidates_healthy(
        rows, NOW, batch_max=batch_max, grades=grades, sa_tokens=sa_tokens)


def test_jwt_vigente_es_candidata():
    got = _run([_acc("a@x.com", grade="A+", jwt_exp=NOW + H)])
    assert [r["email"] for r in got] == ["a@x.com"]


def test_jwt_expirado_no_es_candidata():
    got = _run([_acc("a@x.com", jwt_exp=NOW - H)])
    assert got == []


def test_jwt_nulo_no_es_candidata():
    got = _run([_acc("a@x.com", jwt_exp=None)])
    assert got == []


def test_jwt_vence_ahora_mismo_no_es_candidata():
    got = _run([_acc("a@x.com", jwt_exp=NOW)])
    assert got == []


def test_lockeada_por_operador_se_excluye():
    got = _run([_acc("a@x.com", jwt_exp=NOW + H, locked_by=555)])
    assert got == []


def test_grade_no_util_se_excluye():
    got = _run([_acc("d@x.com", grade="D", jwt_exp=NOW + H),
                _acc("c@x.com", grade="C", jwt_exp=NOW + H)])
    assert got == []


def test_no_live_se_excluye():
    got = _run([_acc("a@x.com", status="DEAD", jwt_exp=NOW + H)])
    assert got == []


def test_no_publicada_se_excluye():
    got = _run([_acc("a@x.com", jwt_exp=NOW + H, published=0)])
    assert got == []


def test_orden_por_last_checked_ascendente():
    rows = [
        _acc("reciente@x.com", jwt_exp=NOW + H, last_checked_at="2026-07-19 10:00:00"),
        _acc("vieja@x.com", jwt_exp=NOW + H, last_checked_at="2026-07-18 08:00:00"),
        _acc("nunca@x.com", jwt_exp=NOW + H, last_checked_at=None),
    ]
    got = [r["email"] for r in _run(rows)]
    # None ("") ordena primero, luego la más antigua, luego la reciente
    assert got == ["nunca@x.com", "vieja@x.com", "reciente@x.com"]


def test_batch_max_limita():
    rows = [_acc(f"{i}@x.com", grade="B", jwt_exp=NOW + H) for i in range(30)]
    got = _run(rows, batch_max=12)
    assert len(got) == 12


def test_grades_configurable():
    rows = [_acc("c@x.com", grade="C", jwt_exp=NOW + H)]
    got = _run(rows, grades={"C"})
    assert len(got) == 1


def test_reservada_sa_con_jwt_vigente_es_candidata():
    """Cuenta RESERVADA_SA (published=0, locked_by=SA) con JWT vivo
    DEBE ser candidata — el refresh automático la alcanza."""
    got = _run([_acc("espinoza@x.com", jwt_exp=NOW + H, published=0,
                     locked_by="1341812706")])
    assert len(got) == 1
    assert got[0]["email"] == "espinoza@x.com"


def test_reservada_sa_locked_by_username_es_candidata():
    """Cuenta con locked_by='RobertVS' (formato username, como lo manda el
    frontend bulkLock) DEBE ser candidata también — cubre el caso real de
    prod (espinoza id 1497)."""
    got = _run([_acc("espinoza@x.com", jwt_exp=NOW + H, published=0,
                     locked_by="RobertVS")])
    assert len(got) == 1
    assert got[0]["email"] == "espinoza@x.com"


def test_reservada_no_sa_no_es_candidata():
    """Cuenta publicada=0 pero lockeada por operador (no SA) sigue fuera."""
    got = _run([_acc("op@x.com", jwt_exp=NOW + H, published=0,
                     locked_by="555")])
    assert got == []


def test_no_publicada_no_lockeada_no_es_candidata():
    """Cuenta pool=0 sin lock explícito → fuera."""
    got = _run([_acc("floater@x.com", jwt_exp=NOW + H, published=0)])
    assert got == []


# ── Cuentas "calientes" (Robert, 2026-08-04): balance>$50, depósito reciente
# sin asentar (ventana locked_until activa), o retiro en curso hasta liberar
# — deben refrescarse SIEMPRE, sin importar lock/grade/pool/batch_max. Hoy el
# loop las EXCLUYE si están lockeadas por un operador (bug real: una cuenta
# con depósito o retiro en curso normalmente está lockeada). ──────────────

def test_hot_lockeada_por_operador_no_sa_es_candidata():
    """A diferencia de una cuenta normal lockeada, una HOT sí entra pese al lock."""
    got = _run([_acc("hot@x.com", jwt_exp=NOW + H, locked_by=555, hot=True)])
    assert [r["email"] for r in got] == ["hot@x.com"]


def test_hot_grade_no_util_es_candidata():
    got = _run([_acc("hot@x.com", grade="D", jwt_exp=NOW + H, hot=True)])
    assert [r["email"] for r in got] == ["hot@x.com"]


def test_hot_no_publicada_es_candidata():
    got = _run([_acc("hot@x.com", jwt_exp=NOW + H, published=0, hot=True)])
    assert [r["email"] for r in got] == ["hot@x.com"]


def test_hot_sin_jwt_vigente_no_es_candidata():
    """Sin JWT vivo no hay forma de refrescar — ni hot la salva."""
    got = _run([_acc("hot@x.com", jwt_exp=NOW - H, hot=True)])
    assert got == []


def test_hot_no_live_no_es_candidata():
    got = _run([_acc("hot@x.com", status="DEAD", jwt_exp=NOW + H, hot=True)])
    assert got == []


def test_hot_ignora_batch_max():
    """Las hot van SIEMPRE, no cuentan contra el batch_max de las normales."""
    normales = [_acc(f"n{i}@x.com", jwt_exp=NOW + H) for i in range(12)]
    hots = [_acc(f"h{i}@x.com", jwt_exp=NOW + H, locked_by=1, hot=True) for i in range(3)]
    got = _run(normales + hots, batch_max=12)
    assert len(got) == 15
    assert {r["email"] for r in got if r["email"].startswith("h")} == {f"h{i}@x.com" for i in range(3)}


def test_hot_va_primero_en_el_resultado():
    normal = _acc("normal@x.com", jwt_exp=NOW + H, last_checked_at="2026-01-01")
    hot = _acc("hot@x.com", jwt_exp=NOW + H, locked_by=1, hot=True, last_checked_at="2026-06-01")
    got = _run([normal, hot])
    assert [r["email"] for r in got] == ["hot@x.com", "normal@x.com"]


# ── is_hot_account: lógica pura de qué hace a una cuenta "caliente" ───────

def _row(*, balance_real=0, locked_until=None, has_pending_withdrawal=False):
    return {
        "balance_real": balance_real,
        "locked_until": locked_until,
        "has_pending_withdrawal": has_pending_withdrawal,
    }


def test_hot_por_balance_alto():
    assert is_hot_account(_row(balance_real=50.01), NOW_ISO) is True


def test_no_hot_balance_50_exacto():
    assert is_hot_account(_row(balance_real=50.0), NOW_ISO) is False


def test_no_hot_balance_bajo_sin_lock_sin_retiro():
    assert is_hot_account(_row(balance_real=10.0), NOW_ISO) is False


def test_hot_por_ventana_de_autolock_activa():
    assert is_hot_account(_row(locked_until="2026-08-04T13:00:00+00:00"), NOW_ISO) is True


def test_no_hot_ventana_de_autolock_vencida():
    assert is_hot_account(_row(locked_until="2026-08-04T11:00:00+00:00"), NOW_ISO) is False


def test_hot_por_retiro_pendiente():
    assert is_hot_account(_row(has_pending_withdrawal=True), NOW_ISO) is True


def test_no_hot_sin_ninguna_señal():
    assert is_hot_account(_row(), NOW_ISO) is False
