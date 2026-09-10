"""test_rescue_429.py — lógica pura de scripts/rescue_429.py (reconciliación
de cuentas mass-killed por scripts/update_429.py, ver docs/ERRORS.md).

Solo se testea la lógica determinista: clasificación del LoginResult, decisión
resurrect/keep_dead y el circuit breaker. El I/O (gentle_login, UPDATE en BD) no
se testea aquí — mismo criterio que scratchpad/probe_rlp.py.
"""
import importlib.util
import pathlib

_SPEC = importlib.util.spec_from_file_location(
    "rescue_429",
    pathlib.Path(__file__).resolve().parent.parent / "scripts" / "rescue_429.py",
)
rescue = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rescue)


class _R:
    def __init__(self, ok=False, jwt=None, code="", error="", account_dead=False):
        self.ok = ok
        self.jwt = jwt
        self.code = code
        self.error = error
        self.account_dead = account_dead


def test_classify_live_limpio():
    assert rescue.classify(_R(ok=True, jwt="jwt_abc")) == "LIVE_LIMPIO"


def test_classify_ok_sin_jwt_no_es_limpio():
    # ok=True pero sin jwt no sirve para operar — no se resucita
    assert rescue.classify(_R(ok=True, jwt=None)) != "LIVE_LIMPIO"


def test_classify_still_429_desde_code():
    assert rescue.classify(_R(code="RATE_LIMITED")) == "STILL_429"


def test_classify_still_429_desde_texto_error():
    assert rescue.classify(_R(error="HTTP 429 Too Many Requests")) == "STILL_429"


def test_classify_dead_real():
    assert rescue.classify(_R(account_dead=True, code="LOGIN_DENIED")) == "DEAD_REAL"


def test_classify_autoexclusion_no_es_resurrectable():
    v = rescue.classify(_R(code="AUTOEXCLUSION", error="cuenta en autoexclusión"))
    assert v != "LIVE_LIMPIO"
    assert rescue.decide_action(v) == "keep_dead"


def test_decide_action_solo_resucita_limpias():
    assert rescue.decide_action("LIVE_LIMPIO") == "resurrect"
    assert rescue.decide_action("STILL_429") == "keep_dead"
    assert rescue.decide_action("DEAD_REAL") == "keep_dead"
    assert rescue.decide_action("OTRO") == "keep_dead"


def test_circuit_breaker_corta_tras_n_429_consecutivos():
    cb = rescue.CircuitBreaker(threshold=3)
    cb.record("STILL_429")
    cb.record("STILL_429")
    assert not cb.tripped
    cb.record("STILL_429")
    assert cb.tripped


def test_circuit_breaker_se_resetea_con_login_limpio():
    cb = rescue.CircuitBreaker(threshold=3)
    cb.record("STILL_429")
    cb.record("STILL_429")
    cb.record("LIVE_LIMPIO")
    cb.record("STILL_429")
    cb.record("STILL_429")
    assert not cb.tripped


def test_cohort_where_429_usa_like_con_param():
    sql, params = rescue.cohort_where("cuarentena")
    assert "dead_reason LIKE ?" in sql
    assert params == (rescue.COHORTS["cuarentena"],)


def test_cohort_where_sin_reason_es_is_null_sin_param():
    # las 85 DEAD sin dead_reason NI dead_at — no matchean ningún LIKE
    sql, params = rescue.cohort_where("sin_reason")
    assert "LIKE" not in sql
    assert "dead_reason IS NULL" in sql
    assert "dead_at IS NULL" in sql
    assert params == ()


def test_cohort_sin_reason_registrada():
    assert "sin_reason" in rescue.COHORTS
