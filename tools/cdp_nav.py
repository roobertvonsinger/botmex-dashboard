#!/usr/bin/env python3
"""Navega el tab via CDP para disparar tráfico y validar la captura."""
import sys, json, asyncio, httpx
import websockets

CDP_HTTP = "http://localhost:9222"
URL = sys.argv[1] if len(sys.argv) > 1 else "https://betmexico.mx/login"

def pick_page():
    r = httpx.get(f"{CDP_HTTP}/json", timeout=5); r.raise_for_status()
    for t in r.json():
        if t.get("type") == "page" and "betmexico" in t.get("url", ""):
            return t
    raise RuntimeError("no page")

async def main():
    tgt = pick_page()
    ws_url = tgt["webSocketDebuggerUrl"]
    async with websockets.connect(ws_url, max_size=64*1024*1024) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Page.navigate",
                                  "params": {"url": URL}}))
        print(f"[nav] -> {URL}", file=sys.stderr)
        # esperar a que cargue
        await asyncio.sleep(6)
        print("[nav] done", file=sys.stderr)

asyncio.run(main())
