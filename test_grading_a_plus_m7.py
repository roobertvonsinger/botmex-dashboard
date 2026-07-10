"""
Tests del rebalanceo de grading 2026-07-09 (Robert):

  M7  — masacre reciente ya NO es B: una cuenta con sesión machine-gun (3+ fails)
        o ≥5 fails totales cae en C aunque el último fail sea de hace 15-89 días
        (antes caía en el `else` → B "reparándose", falso positivo de confianza).

  A+  — ciclo de vida del override 3DS: 3DS→A+; 2 rechazos REALES de banco
        CONSECUTIVOS → B; un aprobado resetea el contador (2 deben ser seguidas);
        el ruido no-banco (rate-limit/infra/3DS) ni cuenta ni resetea.

El analyzer no tenía NINGÚN test (es el corazón de la inteligencia del dashboard,
ver memoria project_inteligencia_medible) — estos fijan el comportamiento nuevo.
"""
import importlib.util
import os
import sqlite3
from datetime import datetime, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bpa = _load(os.path.join("shared", "betmexico_payment_analyzer.py"), "bpa_test")
wg = _load("web_grading.py", "web_grading_test")

S = bpa.TXN_STATUS_SUCCESS   # 6
F = bpa.TXN_STATUS_FAILED    # -4


def _txn(days_ago, status, minutes_offset=0):
    """Depósito con tarjeta (txn_type=1, gateway=1) hace `days_ago` días."""
    dt = datetime.now() - timedelta(days=days_ago, minutes=minutes_offset)
    return {
        "txn_date": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "txn_type": 1, "gateway": 1, "status": status, "amount": 50.0,
    }


def _grade(items):
    sc = bpa.score_payment_readiness(
        {"transactions": {"fetched": True, "items": items, "total_rows": len(items)}}
    )
    return sc["grade"]


# ─────────────────────────── M7 (analyzer) ───────────────────────────

def test_masacre_reciente_es_C_no_B():
    # 3 fails en la MISMA sesión (mismos minutos) hace 30 días → masacre.
    # Antes: else → B. Ahora: C (RECIENTE, 14-89d).
    items = [_txn(30, F, 0), _txn(30, F, 1), _txn(30, F, 2)]
    assert _grade(items) == "C"


def test_masacre_descansada_sigue_C():
    # Misma masacre pero hace 100 días → C (DESCANSADA, ≥90d) — sin regresión.
    items = [_txn(100, F, 0), _txn(100, F, 1), _txn(100, F, 2)]
    assert _grade(items) == "C"


def test_cinco_fails_aislados_reciente_es_C():
    # 5 fails en sesiones separadas (por días, sin masacre), último hace 30d → C.
    items = [_txn(30, F), _txn(40, F), _txn(55, F), _txn(70, F), _txn(85, F)]
    assert _grade(items) == "C"


def test_pocos_fails_aislados_es_B():
    # 2 fails aislados, último hace 30d: ni masacre ni ≥5 → B (reparándose).
    items = [_txn(30, F), _txn(50, F)]
    assert _grade(items) == "B"


def test_fail_reciente_es_D_aunque_sea_masacre():
    # Masacre pero hace 5 días → D-recent gana primero (no C).
    items = [_txn(5, F, 0), _txn(5, F, 1), _txn(5, F, 2)]
    assert _grade(items) == "D"


def test_sin_fails_es_A():
    items = [_txn(10, S), _txn(40, S)]
    assert _grade(items) == "A"


# ─────────────────────── A+ lifecycle (web_grading) ───────────────────────

def _mk_db(tmp_path, grade="A+", streak=0):
    p = str(tmp_path / "acc.db")
    c = sqlite3.connect(p)
    c.execute(
        "CREATE TABLE accounts (id INTEGER PRIMARY KEY, email TEXT, grade TEXT, "
        "grade_score INTEGER, a_plus_decline_streak INTEGER DEFAULT 0)"
    )
    c.execute(
        "INSERT INTO accounts (email, grade, grade_score, a_plus_decline_streak) "
        "VALUES ('x@y.com', ?, 95, ?)",
        (grade, streak),
    )
    c.commit()
    c.close()
    return p


def _get(p):
    c = sqlite3.connect(p)
    c.row_factory = sqlite3.Row
    r = c.execute(
        "SELECT grade, a_plus_decline_streak AS s FROM accounts WHERE email='x@y.com'"
    ).fetchone()
    c.close()
    return r["grade"], r["s"]


def test_aplus_una_decline_sigue_aplus(tmp_path):
    p = _mk_db(tmp_path)
    wg.note_a_plus_outcome("x@y.com", "rejected", db_path=p)
    assert _get(p) == ("A+", 1)


def test_aplus_dos_declines_seguidas_baja_a_B(tmp_path):
    p = _mk_db(tmp_path, streak=1)
    wg.note_a_plus_outcome("x@y.com", "rejected", db_path=p)
    grade, streak = _get(p)
    assert grade == "B" and streak == 0


def test_aprobado_resetea_streak(tmp_path):
    p = _mk_db(tmp_path, streak=1)
    wg.note_a_plus_outcome("x@y.com", "approved", db_path=p)
    assert _get(p) == ("A+", 0)


def test_decline_aprobado_decline_NO_baja(tmp_path):
    # Regla de Robert: deben ser 2 SEGUIDAS. Un aprobado en medio perdona.
    p = _mk_db(tmp_path)
    wg.note_a_plus_outcome("x@y.com", "rejected", db_path=p)   # streak 1
    wg.note_a_plus_outcome("x@y.com", "approved", db_path=p)   # reset 0
    wg.note_a_plus_outcome("x@y.com", "rejected", db_path=p)   # streak 1
    assert _get(p) == ("A+", 1)


def test_ruido_no_banco_no_toca_streak(tmp_path):
    p = _mk_db(tmp_path, streak=1)
    for st in ("rate_limited", "threeds", "login_lost", "timeout", "incomplete"):
        wg.note_a_plus_outcome("x@y.com", st, db_path=p)
    assert _get(p) == ("A+", 1)


def test_cuenta_no_aplus_es_noop(tmp_path):
    p = _mk_db(tmp_path, grade="C", streak=0)
    wg.note_a_plus_outcome("x@y.com", "rejected", db_path=p)
    assert _get(p) == ("C", 0)
