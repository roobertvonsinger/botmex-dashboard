"""support_llm.py — cliente del 9router para el agente de soporte.

VENDORED de la rama `feat/support-agent` (commit aislado, Fase 3 del refactor
`/bet` — 2026-09-08). Copia FIEL a propósito: `bet_advisor.py` lo reusa como
transporte LLM. No mergear `feat/support-agent`; si esa rama evoluciona, re-diff
`git show feat/support-agent:support_llm.py` contra este archivo a mano.

El 9router (`decolua/9router`, KVM4 :20128) expone una API OpenAI-compatible,
así que aquí no hay SDK: httpx crudo, que ya viene en la imagen. Eso evita
tocar el Dockerfile y volver a resolver dependencias sin pinear.

Tres cosas que este módulo resuelve y que son la fuente habitual de bugs:

  * **tool_calls fragmentados.** El nombre llega en un chunk y los argumentos
    partidos entre varios. Se acumulan por `index` hasta el final del stream.
  * **Fallback acotado.** Si un modelo falla se pasa al siguiente de la cadena,
    pero SOLO mientras no se haya emitido texto. Reintentar a medias le
    mostraría a Robert dos respuestas pegadas.
  * **Errores que no son excepciones.** El router devuelve 502 con cuerpo JSON
    cuando el upstream se cae (que es justo lo que pasó con Antigravity).
"""

from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator

import httpx

BASE_URL = os.environ.get("NINEROUTER_URL", "http://openclaw-ruth-ninerouter-1:20128")

# Cadena por defecto: primario y respaldos, todos gratuitos en el router.
# Se sobreescribe con SUPPORT_MODEL_CHAIN="a,b,c" sin tocar código, que es como
# se fija tras probar tool-calling contra el router vivo.
DEFAULT_CHAIN = [
    "ag/gemini-pro-agent",
    "ag/claude-sonnet-4-6",
    "ag/gemini-3-flash",
    "mistral/mistral-large-latest",
]


def chain_from_env() -> list[str]:
    raw = os.environ.get("SUPPORT_MODEL_CHAIN", "").strip()
    if raw:
        return [m.strip() for m in raw.split(",") if m.strip()]
    return list(DEFAULT_CHAIN)


class LLMClient:
    def __init__(self, base_url: str | None = None, chain: list[str] | None = None,
                 timeout: float = 120.0, transport: Any = None):
        self.base_url = (base_url or BASE_URL).rstrip("/")
        self.chain = chain or chain_from_env()
        self.timeout = timeout
        self._transport = transport

    # ---------------------------------------------------------------- interno

    def _payload(self, model, messages, tools, max_tokens):
        p: dict = {"model": model, "messages": messages, "stream": True,
                   "max_tokens": max_tokens}
        if tools:
            p["tools"] = tools
            p["tool_choice"] = "auto"
        return p

    @staticmethod
    def _merge_tool_deltas(acc: dict, deltas: list) -> None:
        """Acumula fragmentos de tool_calls indexados."""
        for tc in deltas or []:
            i = tc.get("index", 0)
            slot = acc.setdefault(i, {"id": None, "name": None, "arguments": ""})
            if tc.get("id"):
                slot["id"] = tc["id"]
            fn = tc.get("function") or {}
            if fn.get("name"):
                slot["name"] = fn["name"]
            if fn.get("arguments"):
                slot["arguments"] += fn["arguments"]

    @staticmethod
    def _finalize_calls(acc: dict) -> list[dict]:
        out = []
        for i in sorted(acc):
            c = acc[i]
            if not c.get("name"):
                continue
            args = c.get("arguments") or "{}"
            try:
                json.loads(args)
            except Exception:
                args = "{}"          # el modelo mandó JSON roto: que reintente
            out.append({"id": c.get("id") or f"call_{i}", "name": c["name"],
                        "arguments": args})
        return out

    # ---------------------------------------------------------------- público

    async def stream_chat(self, messages: list, tools: list | None = None,
                          max_tokens: int = 2048) -> AsyncIterator[dict]:
        """Emite eventos: delta / tool_calls / done / error."""
        ultimo_error = "sin modelos en la cadena"

        for model in self.chain:
            emitido = False           # ¿ya le mandamos texto a Robert?
            tool_acc: dict = {}
            usage: dict = {}
            kw = {"timeout": self.timeout}
            if self._transport is not None:
                kw["transport"] = self._transport

            try:
                async with httpx.AsyncClient(**kw) as cli:
                    async with cli.stream(
                        "POST", f"{self.base_url}/v1/chat/completions",
                        json=self._payload(model, messages, tools, max_tokens),
                        headers={"content-type": "application/json"},
                    ) as resp:
                        if resp.status_code != 200:
                            cuerpo = (await resp.aread()).decode("utf-8", "replace")
                            ultimo_error = f"HTTP {resp.status_code} · {cuerpo[:200]}"
                            continue          # modelo caído → siguiente

                        async for linea in resp.aiter_lines():
                            if not linea or not linea.startswith("data:"):
                                continue      # keepalives y comentarios SSE
                            data = linea[5:].strip()
                            if data == "[DONE]":
                                break
                            try:
                                obj = json.loads(data)
                            except Exception:
                                continue      # basura suelta: no tira el stream

                            if obj.get("usage"):
                                usage = obj["usage"]
                            ch = (obj.get("choices") or [{}])[0]
                            d = ch.get("delta") or {}

                            if d.get("content"):
                                emitido = True
                                yield {"type": "delta", "text": d["content"]}
                            if d.get("tool_calls"):
                                self._merge_tool_deltas(tool_acc, d["tool_calls"])

                calls = self._finalize_calls(tool_acc)
                if calls:
                    yield {"type": "tool_calls", "calls": calls}
                yield {"type": "done", "model": model,
                       "tokens_in": usage.get("prompt_tokens"),
                       "tokens_out": usage.get("completion_tokens")}
                return

            except Exception as e:
                ultimo_error = f"{type(e).__name__}: {str(e)[:200]}"
                if emitido:
                    # Ya se envió media respuesta: reintentar duplicaría texto.
                    yield {"type": "error", "message": f"Stream cortado ({ultimo_error})"}
                    return
                continue

        yield {"type": "error",
               "message": f"Ningún modelo respondió. Último error: {ultimo_error}"}
