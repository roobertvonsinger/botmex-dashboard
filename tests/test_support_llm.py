# test_support_llm.py — cliente del 9router (OpenAI-compatible).
#
# Tres cosas que rompen en producción si no se cubren:
#   1. Los tool_calls llegan FRAGMENTADOS entre chunks: el nombre en uno, los
#      argumentos partidos en cinco. Hay que acumularlos por índice.
#   2. El fallback solo es válido ANTES de emitir texto. Si ya le mandamos media
#      frase a Robert y reintentamos con otro modelo, ve dos respuestas pegadas.
#   3. El router devuelve 502 con cuerpo JSON de error, no una excepción.

import json

import httpx
import pytest

import support_llm as sl


def sse(*chunks: str) -> bytes:
    return "".join(f"data: {c}\n\n" for c in chunks).encode()


def delta(txt):
    return json.dumps({"choices": [{"delta": {"content": txt}}]})


def tool_delta(index, *, call_id=None, name=None, args=None):
    fn = {}
    if name is not None:
        fn["name"] = name
    if args is not None:
        fn["arguments"] = args
    tc = {"index": index, "function": fn}
    if call_id:
        tc["id"] = call_id
    return json.dumps({"choices": [{"delta": {"tool_calls": [tc]}}]})


def cliente(handler, chain=("modelo-a", "modelo-b", "modelo-c")):
    return sl.LLMClient(base_url="http://router:20128", chain=list(chain),
                        transport=httpx.MockTransport(handler))


async def drenar(client):
    return [ev async for ev in client.stream_chat([{"role": "user", "content": "hola"}], tools=[])]


# ------------------------------------------------------------------ texto simple

@pytest.mark.asyncio
async def test_acumula_texto_y_reporta_modelo():
    def h(_):
        return httpx.Response(200, content=sse(delta("Hola "), delta("Robert"), "[DONE]"))

    evs = await drenar(cliente(h))
    assert "".join(e["text"] for e in evs if e["type"] == "delta") == "Hola Robert"
    fin = [e for e in evs if e["type"] == "done"][0]
    assert fin["model"] == "modelo-a"


# --------------------------------------------------------- tool_calls fragmentados

@pytest.mark.asyncio
async def test_reensambla_tool_call_partido_en_varios_chunks():
    def h(_):
        return httpx.Response(200, content=sse(
            tool_delta(0, call_id="call_1", name="consultar_bd", args='{"sq'),
            tool_delta(0, args='l": "SELECT '),
            tool_delta(0, args='1"}'),
            "[DONE]",
        ))

    evs = await drenar(cliente(h))
    calls = [e for e in evs if e["type"] == "tool_calls"][0]["calls"]
    assert len(calls) == 1
    assert calls[0]["name"] == "consultar_bd"
    assert json.loads(calls[0]["arguments"]) == {"sql": "SELECT 1"}


@pytest.mark.asyncio
async def test_soporta_dos_tool_calls_en_paralelo():
    def h(_):
        return httpx.Response(200, content=sse(
            tool_delta(0, call_id="c1", name="estado_sistema", args="{}"),
            tool_delta(1, call_id="c2", name="leer_logs", args='{"fuente":"dashboard"}'),
            "[DONE]",
        ))

    calls = [e for e in await drenar(cliente(h)) if e["type"] == "tool_calls"][0]["calls"]
    assert {c["name"] for c in calls} == {"estado_sistema", "leer_logs"}


@pytest.mark.asyncio
async def test_argumentos_vacios_quedan_como_objeto_valido():
    def h(_):
        return httpx.Response(200, content=sse(
            tool_delta(0, call_id="c1", name="reanudar_sistema"), "[DONE]"))

    calls = [e for e in await drenar(cliente(h)) if e["type"] == "tool_calls"][0]["calls"]
    assert json.loads(calls[0]["arguments"]) == {}


# ------------------------------------------------------------------------ fallback

@pytest.mark.asyncio
async def test_cae_al_siguiente_modelo_ante_502():
    vistos = []

    def h(req):
        m = json.loads(req.content)["model"]
        vistos.append(m)
        if m == "modelo-a":
            return httpx.Response(502, json={"error": {"message": "EAI_AGAIN"}})
        return httpx.Response(200, content=sse(delta("ok"), "[DONE]"))

    evs = await drenar(cliente(h))
    assert vistos == ["modelo-a", "modelo-b"]
    assert [e for e in evs if e["type"] == "done"][0]["model"] == "modelo-b"


@pytest.mark.asyncio
async def test_cae_al_siguiente_ante_error_de_red():
    def h(req):
        if json.loads(req.content)["model"] == "modelo-a":
            raise httpx.ConnectError("sin ruta")
        return httpx.Response(200, content=sse(delta("ok"), "[DONE]"))

    assert [e for e in await drenar(cliente(h)) if e["type"] == "done"][0]["model"] == "modelo-b"


@pytest.mark.asyncio
async def test_si_todos_fallan_emite_error_no_excepcion():
    def h(_):
        return httpx.Response(502, json={"error": {"message": "caido"}})

    evs = await drenar(cliente(h))
    assert [e for e in evs if e["type"] == "error"]
    assert not [e for e in evs if e["type"] == "done"]


@pytest.mark.asyncio
async def test_no_hace_fallback_despues_de_emitir_texto():
    """Si ya se envió texto a Robert, reintentar con otro modelo produciría dos
    respuestas concatenadas. Mejor cortar con error.

    El stream se rompe DE VERDAD a media lectura (no una línea basura, que el
    parser simplemente ignoraría) para ejercitar el camino de excepción.
    """
    intentos = []

    async def stream_que_se_corta():
        yield f"data: {delta('mitad de la ')}\n\n".encode()
        raise httpx.ReadError("conexión perdida a media respuesta")

    def h(req):
        intentos.append(json.loads(req.content)["model"])
        return httpx.Response(200, content=stream_que_se_corta())

    evs = await drenar(cliente(h))
    assert intentos == ["modelo-a"], "no debe reintentar tras haber emitido texto"
    assert any(e["type"] == "delta" for e in evs)
    assert [e for e in evs if e["type"] == "error"], "debe reportar el corte"
    assert not [e for e in evs if e["type"] == "done"]


# ------------------------------------------------------------------ robustez varia

@pytest.mark.asyncio
async def test_ignora_lineas_basura_y_keepalives():
    def h(_):
        return httpx.Response(200, content=(
            b": keepalive\n\n" + sse(delta("a")) + b"data: {no-es-json}\n\n" +
            sse(delta("b"), "[DONE]")))

    evs = await drenar(cliente(h))
    assert "".join(e["text"] for e in evs if e["type"] == "delta") == "ab"


@pytest.mark.asyncio
async def test_reporta_uso_de_tokens_si_el_router_lo_manda():
    def h(_):
        return httpx.Response(200, content=sse(
            delta("hola"),
            json.dumps({"choices": [{"delta": {}}],
                        "usage": {"prompt_tokens": 120, "completion_tokens": 8}}),
            "[DONE]"))

    fin = [e for e in await drenar(cliente(h)) if e["type"] == "done"][0]
    assert fin["tokens_in"] == 120
    assert fin["tokens_out"] == 8
