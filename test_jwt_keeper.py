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
         locked_by=None, published=1, password="pw", hot=False):
    return {
        "email": email, "password": password, "status": status, "grade": grade,
        "jwt_expires_at": jwt_exp, "cooldown_until": cooldown,
        "locked_by": locked_by, "published_to_pool": published,
        "hot": hot,
    }


def _run(rows, *, batch_max=12, ahead=AHEAD, grades=DEFAULT_GRADES, sa_tokens=None):
    sa_tokens = sa_tokens if sa_tokens is not None else ["robertvs", "1341812706"]
    return select_refresh_candidates(
        rows, NOW, batch_max=batch_max, refresh_ahead_sec=ahead, grades=grades,
        sa_tokens=sa_tokens)


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


def test_reservada_sa_jwt_expirado_es_candidata():
    """RESERVADA_SA (pool=0, locked_by=SA) con JWT expirado DEBE ser
    candidata — sin esto, su JWT muerto nunca se renueva y el refresh
    siempre recibe default del server. Caso real: espinoza id 1497."""
    got = _run([_acc("espinoza@x.com", grade="A", jwt_exp=NOW - H,
                     published=0, locked_by="1341812706")])
    assert len(got) == 1
    assert got[0]["email"] == "espinoza@x.com"


def test_reservada_sa_locked_by_username_es_candidata():
    """Formato username ('RobertVS' como lo manda bulkLock) también cuenta."""
    got = _run([_acc("espinoza@x.com", grade="A", jwt_exp=NOW - H,
                     published=0, locked_by="RobertVS")])
    assert len(got) == 1


def test_reservada_sa_jwt_vigente_no_es_candidata():
    """RESERVADA_SA con JWT todavía con margen → no re-loguear (igual que pool)."""
    got = _run([_acc("espinoza@x.com", grade="A", jwt_exp=NOW + 48 * H,
                     published=0, locked_by="RobertVS")])
    assert got == []


def test_reservada_no_sa_no_es_candidata():
    """pool=0 locked_by operador (no SA) → sigue fuera."""
    got = _run([_acc("op@x.com", grade="A", jwt_exp=NOW - H,
                     published=0, locked_by="555")])
    assert got == []


# ── Priorización de cuentas HOT (handoff 2026-08-05 §2.2) ──────────────────
# Una cuenta "hot" (depósito/retiro en curso, balance_real>$50, o retiro
# pendiente) con JWT expirado debe ir PRIMERO en el lote de re-login — ANTES
# que una cuenta fría de mejor grade. Sin esto, una cuenta en proceso activo
# puede quedarse fuera del batch de 8 y no ser re-logueada hasta el próximo
# ciclo (1h de lag). Las hot no cuentan contra batch_max (espejo de
# account_refresh.select_refresh_candidates_healthy).

def test_hot_va_antes_que_normal_aun_con_grade_menor():
    """Hot con grade B debe ir ANTES que normal con grade A+ (que hoy iría
    primero por orden de grade). Sin el fix, A+ iría primero y hot podría
    no entrar al batch de 8."""
    rows = [
        _acc("normal_aplus@x.com", grade="A+", jwt_exp=NOW - H),
        _acc("hot_b@x.com", grade="B", jwt_exp=NOW - H, hot=True),
    ]
    got = [r["email"] for r in _run(rows)]
    assert got == ["hot_b@x.com", "normal_aplus@x.com"]


def test_hot_no_cuenta_contra_batch_max():
    """Las hot van SIEMPRE, no ocupan cupo del batch de normales."""
    normales = [_acc(f"n{i}@x.com", grade="B", jwt_exp=NOW - H) for i in range(8)]
    hots = [_acc(f"h{i}@x.com", grade="B", jwt_exp=NOW - H, hot=True) for i in range(3)]
    got = _run(normales + hots, batch_max=8)
    assert len(got) == 11
    assert {r["email"] for r in got if r["email"].startswith("h")} == {f"h{i}@x.com" for i in range(3)}


def test_hot_dentro_de_grupo_se_ordena_por_grade():
    """Entre hot, mejor grade primero (mismo criterio que normales)."""
    rows = [
        _acc("hot_b@x.com", grade="B", jwt_exp=NOW - H, hot=True),
        _acc("hot_aplus@x.com", grade="A+", jwt_exp=NOW - H, hot=True),
        _acc("hot_a@x.com", grade="A", jwt_exp=NOW - H, hot=True),
    ]
    got = [r["email"] for r in _run(rows)]
    assert got == ["hot_aplus@x.com", "hot_a@x.com", "hot_b@x.com"]


def test_hot_excluye_si_no_es_candidata_normal():
    """Hot respeta los filtros duros: cooldown activo la excluye igual que
    a una normal. Hot no es pase-libre para re-loguear cuentas quemadas."""
    got = _run([_acc("hot@x.com", grade="B", jwt_exp=NOW - H,
                     cooldown=NOW + 10 * 60, hot=True)])
    assert got == []


def test_hot_grade_no_util_sigue_siendo_candidata_si_hot_y_publicada():
    """Hot bypassea el filtro de grade (igual que en account_refresh) — una
    cuenta con retiro en curso y grade D sigue siendo hot y necesita JWT
    vivo para que el ciclo de refresh reciba datos reales."""
    got = _run([_acc("hot_d@x.com", grade="D", jwt_exp=NOW - H, hot=True)],
               grades={"A+", "A", "B"})
    assert [r["email"] for r in got] == ["hot_d@x.com"]


def test_hot_no_publicada_es_candidata():
    """Hot bypassea published_to_pool (igual que account_refresh)."""
    got = _run([_acc("hot@x.com", grade="B", jwt_exp=NOW - H,
                     published=0, hot=True)])
    assert [r["email"] for r in got] == ["hot@x.com"]
