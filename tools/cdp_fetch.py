#!/usr/bin/env python3
"""Fetch activo de endpoints BetMexico desde DENTRO de la página vía CDP.
La página ya tiene JWT en localStorage + cookies + CORS resuelto a paymentsapi.
No depende del reader frágil de Network.getResponseBody.

Uso: python cdp_fetch.py [url1 url2 ...] [--port 9222] [--raw]
  urlN: path o url absoluta. Si empieza con '/', se pega a https://betmexico.mx
        (los /api/user... que viven en paymentsapi.betmexico.mx hay que darlos completos).
  --raw: imprime body crudo sin truncar.
"""
import sys, json, asyncio, io, argparse
import httpx, websockets

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

CDP_HTTP = "http://localhost:9222"
BASE = "https://betmexico.mx"


def pick_page(port):
    r = httpx.get(f"http://localhost:{port}/json", timeout=5); r.raise_for_status()
    for t in r.json():
        if t.get("type") == "page" and "betmexico" in t.get("url", ""):
            return t
    raise RuntimeError("no betmexico page target")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+", help="paths o urls absolutas")
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--raw", action="store_true")
    args = ap.parse_args()

    tgt = pick_page(args.port)
    print(f"[cdp] target: {tgt.get('url','')[:90]}", file=sys.stderr)
    ws_url = tgt["webSocketDebuggerUrl"]

    # fetch con Authorization desde el propio token de la página; credentials:include para cookies
    # devuelve {status, url, body (parseado o texto), err}
    # URLs embebidas como JSON literal (CDP Runtime.evaluate no inyecta arguments)
    urls_json = json.dumps(args.urls)
    js_fetch = (
        "(async function(){"
        "function tok(){var keys=['bet4:token','betmexico:token','token','jwt','auth_token'];"
        "for(var i=0;i<keys.length;i++){var v=localStorage.getItem(keys[i]);if(v) return v;}return null;}"
        "var t=tok();var urls=" + urls_json + ";var out=[];"
        "for(var u of urls){"
        "try{var opt={method:'GET',credentials:'include',headers:{'Accept':'application/json'}};"
        "if(t)opt.headers['Authorization']='Bearer '+t;"
        "var r=await fetch(u,opt);var txt=await r.text();var body;"
        "try{body=JSON.parse(txt);}catch(e){body=txt;}"
        "out.push({url:u,status:r.status,body:body});"
        "}catch(e){out.push({url:u,err:String(e)});}}"
        "return JSON.stringify(out);})()"
    )

    async with websockets.connect(ws_url, max_size=64 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                  "params": {"expression": js_fetch,
                                             "awaitPromise": True,
                                             "returnByValue": True}}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == 1:
                res = msg.get("result", {}).get("result", {})
                if "exceptionDetails" in msg.get("result", {}):
                    print("JS EXC:", json.dumps(msg["result"]["exceptionDetails"], ensure_ascii=False)[:800])
                    break
                val = res.get("value")
                if not val:
                    print("sin value:", json.dumps(res, ensure_ascii=False)[:400])
                    break
                for item in json.loads(val):
                    print("=====", item.get("status"), item.get("url"), "=====")
                    if "err" in item:
                        print("  ERR:", item["err"])
                    elif isinstance(item.get("body"), (dict, list)):
                        s = json.dumps(item["body"], ensure_ascii=False, indent=2)
                        print(s if args.raw else s[:3000])
                    else:
                        print(item.get("body"))
                break


if __name__ == "__main__":
    asyncio.run(main())
