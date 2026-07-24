#!/usr/bin/env python3
"""Lee el JWT de localStorage via CDP y devuelve SOLO un prefijo (fingerprint).
NO imprime el token completo — para identificación por prefijo en la BD.
Uso: python cdp_jwt_fingerprint.py [--port 9222] [--len 40]
"""
import sys, json, asyncio, argparse
import httpx, websockets

CDP_HTTP = "http://localhost:9222"


def pick_page(port):
    r = httpx.get(f"http://localhost:{port}/json", timeout=5); r.raise_for_status()
    for t in r.json():
        if t.get("type") == "page" and "betmexico" in t.get("url", ""):
            return t
    raise RuntimeError("no betmexico page target")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--len", type=int, default=40, help="longitud del prefijo a imprimir")
    args = ap.parse_args()
    tgt = pick_page(args.port)
    ws_url = tgt["webSocketDebuggerUrl"]

    js = ("(function(){var keys=['bet4:token','betmexico:token','token','jwt','auth_token'];"
          "for(var i=0;i<keys.length;i++){var v=localStorage.getItem(keys[i]);"
          "if(v) return keys[i]+'|'+v;}return 'none';})()")

    async with websockets.connect(ws_url, max_size=8 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                  "params": {"expression": js, "returnByValue": True}}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == 1:
                val = msg.get("result", {}).get("result", {}).get("value")
                if not val or val == "none":
                    print("NO_TOKEN")
                    break
                key, tok = val.split("|", 1)
                # fingerprint: key + prefijo (suficiente para LIKE en BD) + longitud total
                print(f"key={key} total_len={len(tok)} prefix={tok[:args.len]}")
                break


if __name__ == "__main__":
    asyncio.run(main())
