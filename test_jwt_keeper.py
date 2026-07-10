"""Tests de jwt_keeper.select_refresh_candidates — la lógica pura de selección.

Es la pieza crítica: si selecciona de más (o cuentas con JWT aún vigente), el cron
dispara logins innecesarios = el 429 que este keeper existe para evitar. Por eso se
prueba a fondo, sin BD ni deps del bot.
"""
import time

from jwt_keeper import select_refresh_candidates, DEFAULT_GRADES

NOW = 1_800_000_000
H = 3600
AHEAD = 24 * H  # refresh si expira en <=24h


def _acc(email, *, status="LIVE", grade="B", jwt_exp=None, cooldown=None,
         locked_by=None, published=1, password="pw"):
    return {
        "email": email, "password": password, "status": status, "grade": grade,
        "jwt_expires_at": jwt_exp, "cooldown_until": cooldown,
        "locked_by": locked_by, "published_to_pool": published,
    }


def _run(rows, *, batch_max=12, ahead=AHEAD, grades=DEFAULT_GRADES):
    return select_refresh_candidates(
        rows, NOW, batch_max=batch_max, refresh_ahead_sec=ahead, grades=grades)


def test_jwt_expirado_es_candidata():
    got = _run([_acc("a@x.com", grade="A+", jwt_exp=NOW - H)])
    assert [r["email"] for r in got] == ["a@x.com"]


def test_jwt_nulo_es_candidata():
    got = _run([_acc("a@x.com", jwt_exp=None)])
    assert len(got) == 1


def test_jwt_vigente_con_margen_no_es_candidata():
    # expira en 48h > 24h de ventana → todavía sirve, no re-loguear
    got = _run([_acc("a@x.com", jwt_exp=NOW + 48 * H)])
    assert got == []


def test_jwt_por_expirar_dentro_de_ventana_si_es_candidata():
    got = _run([_acc("a@x.com", jwt_exp=NOW + 1 * H)])
    assert len(got) == 1


def test_en_cooldown_se_excluye():
    got = _run([_acc("a@x.com", jwt_exp=NOW - H, cooldown=NOW + 10 * 60)])
    assert got == []


def test_cooldown_vencido_no_excluye():
    got = _run([_acc("a@x.com", jwt_exp=NOW - H, cooldown=NOW - 10)])
    assert len(got) == 1


def test_lockeada_por_operador_se_excluye():
    got = _run([_acc("a@x.com", jwt_exp=NOW - H, locked_by=555)])
    assert got == []


def test_grade_no_util_se_excluye():
    got = _run([_acc("d@x.com", grade="D", jwt_exp=NOW - H),
                _acc("c@x.com", grade="C", jwt_exp=NOW - H)])
    assert got == []


def test_no_live_se_excluye():
    got = _run([_acc("a@x.com", status="DEAD", jwt_exp=NOW - H)])
    assert got == []


def test_no_publicada_se_excluye():
    got = _run([_acc("a@x.com", jwt_exp=NOW - H, published=0)])
    assert got == []


def test_orden_por_grado_luego_urgencia():
    rows = [
        _acc("b_vieja@x.com", grade="B", jwt_exp=NOW - 5 * H),
        _acc("aplus@x.com", grade="A+", jwt_exp=NOW + H),
        _acc("a@x.com", grade="A", jwt_exp=NOW - H),
        _acc("b_expirada@x.com", grade="B", jwt_exp=NOW - 100 * H),
    ]
    got = [r["email"] for r in _run(rows)]
    # A+ primero, luego A, luego B (más urgente/expirada antes)
    assert got == ["aplus@x.com", "a@x.com", "b_expirada@x.com", "b_vieja@x.com"]


def test_batch_max_limita():
    rows = [_acc(f"{i}@x.com", grade="B", jwt_exp=NOW - H) for i in range(30)]
    got = _run(rows, batch_max=12)
    assert len(got) == 12


def test_grades_configurable():
    rows = [_acc("c@x.com", grade="C", jwt_exp=NOW - H)]
    got = _run(rows, grades={"C"})
    assert len(got) == 1
