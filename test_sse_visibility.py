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
