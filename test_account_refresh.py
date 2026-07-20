"""Tests de account_refresh.select_refresh_candidates_healthy — lógica pura.

Es la pieza crítica: si selecciona una cuenta CON JWT expirado, el ciclo pega
un fetch con un token muerto (401 silencioso, gasto sin retorno) en vez de
dejar esa cuenta a jwt_keeper (que sí re-loguea). Por eso se prueba sin BD ni
deps del bot, igual que test_jwt_keeper.py.
"""
from account_refresh import select_refresh_candidates_healthy, DEFAULT_GRADES

NOW = 1_800_000_000
H = 3600


def _acc(email, *, status="LIVE", grade="B", jwt_exp=None, locked_by=None,
         published=1, last_checked_at=None):
    return {
        "email": email, "status": status, "grade": grade,
        "jwt_expires_at": jwt_exp, "locked_by": locked_by,
        "published_to_pool": published, "last_checked_at": last_checked_at,
    }


def _run(rows, *, batch_max=40, grades=DEFAULT_GRADES):
    return select_refresh_candidates_healthy(
        rows, NOW, batch_max=batch_max, grades=grades)


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
