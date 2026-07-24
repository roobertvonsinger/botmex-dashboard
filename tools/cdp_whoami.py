#!/usr/bin/env python3
"""Lee el JWT de sesión de BetMexico en localStorage via CDP y decodifica claims.
NO imprime el token completo, solo claims legibles (email/name/exp/sid/status).
Uso: python cdp_whoami.py [--port 9222]
"""
import sys, json, asyncio, base64, argparse, io
import httpx, websockets

# Forzar UTF-8 en stdout (Windows cp1252 tronaba con ✓/⚠/á)
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

CDP_HTTP = "http://localhost:9222"


def pick_page(port):
    r = httpx.get(f"http://localhost:{port}/json", timeout=5); r.raise_for_status()
    for t in r.json():
        if t.get("type") == "page" and "betmexico" in t.get("url", ""):
            return t
    raise RuntimeError("no betmexico page target — ¿Chrome con --remote-debugging-port=9222?")


def b64url_decode(s):
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


def decode_jwt(token):
    parts = token.split(".")
    if len(parts) < 2:
        return {"_err": "no es JWT (sin 3 partes)"}
    try:
        return json.loads(b64url_decode(parts[1]))
    except Exception as e:
        return {"_err": f"decode fail: {e}"}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9222)
    args = ap.parse_args()

    tgt = pick_page(args.port)
    print(f"[cdp] target: {tgt.get('url','')[:90]}", file=sys.stderr)
    ws_url = tgt["webSocketDebuggerUrl"]

    async with websockets.connect(ws_url, max_size=16 * 1024 * 1024) as ws:
        # leer todos los keys posibles de token (varios nombres históricos)
        expr = (
            "(function(){var out={};var keys=['bet4:token','betmexico:token','token','jwt','auth_token'];"
            "for(var i=0;i<keys.length;i++){var v=localStorage.getItem(keys[i]);"
            "if(v){out[keys[i]]=v;}}return JSON.stringify(out);})()"
        )
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                  "params": {"expression": expr, "returnByValue": True}}))
        # también la URL actual y si hay 401/redirect a login
        await ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate",
                                  "params": {"expression": "location.href", "returnByValue": True}}))

        seen = {1: False, 2: False}
        while not all(seen.values()):
            msg = json.loads(await ws.recv())
            if "id" in msg and msg["id"] in seen:
                seen[msg["id"]] = True
                res = msg.get("result", {}).get("result", {}).get("value")
                if msg["id"] == 1:
                    if not res:
                        print("NO HAY JWT en localStorage — sesión NO logueada o en /login")
                        continue
                    bag = json.loads(res)
                    for k, v in bag.items():
                        claims = decode_jwt(v)
                        print(f"key: {k}")
                        if "_err" in claims:
                            print(f"  {claims['_err']} (token len={len(v)})")
                            continue
                        for c in ("email", "name", "sid", "sub", "role",
                                  "iss", "aud", "exp", "nbf", "given_name"):
                            if c in claims:
                                val = claims[c]
                                if c in ("exp", "nbf"):
                                    from datetime import datetime, timezone
                                    try:
                                        val = f"{val} ({datetime.fromtimestamp(val, timezone.utc).isoformat()})"
                                    except Exception:
                                        pass
                                print(f"  {c}: {val}")
                        # expirado?
                        if "exp" in claims:
                            import time
                            from datetime import datetime, timezone
                            now = int(time.time())
                            if claims["exp"] < now:
                                print(f"  ⚠️ EXPIRADO hace {(now-claims['exp'])//3600}h")
                            else:
                                print(f"  ✓ vigente {(claims['exp']-now)//3600}h más")
                elif msg["id"] == 2:
                    print(f"url actual: {res}")


if __name__ == "__main__":
    asyncio.run(main())
