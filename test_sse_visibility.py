# test_sse_visibility.py
# Task 1: predicado puro _event_visible_to — sin acceso a BD.
# `import app` al nivel de módulo dispara _migrate() que necesita BETMEX_DB;
# para evitar fallo en colección usamos el fixture seed_db (igual que test_a21_visibilidad.py).

SA = {"role": "superadmin", "telegram_id": 1341812706, "display": "RobertVS"}
OP = {"role": "user", "telegram_id": 555, "display": "Lau"}


def test_sa_sees_everything(seed_db):
    import app
    assert app._event_visible_to({"kind": "deposit", "who_id": 555}, SA) is True
    assert app._event_visible_to({"kind": "lock", "who": "Otro"}, SA) is True


def test_operator_sees_own_by_who_id(seed_db):
    import app
    assert app._event_visible_to({"kind": "deposit", "who_id": 555}, OP) is True
    assert app._event_visible_to({"kind": "deposit", "who_id": 1341812706}, OP) is False


def test_operator_sees_own_by_display_fallback(seed_db):
    import app
    assert app._event_visible_to({"kind": "lock", "who": "Lau"}, OP) is True
    assert app._event_visible_to({"kind": "lock", "who": "RobertVS"}, OP) is False


def test_operator_hidden_from_robert_actions(seed_db):
    # Bug conocido: admin/op NO debe ver actividad del SA.
    import app
    assert app._event_visible_to({"kind": "deposit", "who_id": 1341812706}, OP) is False


def test_service_event_addressed_to_operator(seed_db):
    import app
    assert app._event_visible_to({"type": "window_expired", "operator_id": 555}, OP) is True
    assert app._event_visible_to({"type": "window_expired", "operator_id": 1341812706}, OP) is False


def test_actorless_service_event_hidden_from_operator(seed_db):
    # CapMonster bajo, proxy_down sin destinatario -> solo SA.
    import app
    assert app._event_visible_to({"type": "alert", "kind": "capmonster_low"}, OP) is False
    assert app._event_visible_to({"type": "alert", "kind": "capmonster_low"}, SA) is True


def test_who_fallback_requires_display(seed_db):
    # operador con display None y sin who_id: NO debe ver el evento (no se puede igualar)
    import app
    op_no_disp = {"role": "user", "telegram_id": 555, "display": None}
    assert app._event_visible_to({"kind": "lock", "who": "Lau"}, op_no_disp) is False


# ── Task 2: _broadcast filtrado + _resolve_who con who_id ──────────────────────

import queue as _q


def test_broadcast_only_enqueues_visible(seed_db):
    # Inyecta 2 colas con ctx distintos y verifica filtrado.
    import app
    sa_q, op_q = _q.SimpleQueue(), _q.SimpleQueue()
    app._sse_queues[:] = [(sa_q, SA), (op_q, OP)]
    try:
        app._broadcast({"type": "activity", "kind": "deposit", "who_id": 1341812706, "amount": 50})
        assert not sa_q.empty()      # SA recibe
        assert op_q.empty()          # operador NO recibe acción ajena (de Robert)
    finally:
        app._sse_queues.clear()


def test_resolve_who_carries_who_id(seed_db):
    import app
    out = app._resolve_who(1341812706)
    assert out["who_id"] == 1341812706
    assert "who" in out and "who_color" in out


def test_broadcast_operator_receives_own(seed_db):
    import app, queue as _q
    sa_q, op_q = _q.SimpleQueue(), _q.SimpleQueue()
    app._sse_queues[:] = [(sa_q, SA), (op_q, OP)]
    try:
        app._broadcast({"type": "activity", "kind": "deposit", "who_id": 555, "amount": 50})
        assert not sa_q.empty()   # SA recibe todo
        assert not op_q.empty()   # el operador recibe SU propia accion
    finally:
        app._sse_queues.clear()
