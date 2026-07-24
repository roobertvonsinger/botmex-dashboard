#!/usr/bin/env python3
"""Capturador de tráfico BetMexico vía CDP (Chrome DevTools Protocol).
Sin MCP. WebSocket directo a ws://localhost:9222. Patrón: reader único + futures
para getResponseBody (no se traga el stream). Captura /api/ + betmexico con
bodies, postData, status, timestamps ISO a JSONL.

Uso: python cdp_capture.py [out_jsonl] [--port 9222] [--site betmexico]
"""
import sys, os, json, asyncio, argparse
from datetime import datetime, timezone

try:
    import websockets, httpx
except ImportError as e:
    print(f"ERR import: {e}. pip install websockets httpx", file=sys.stderr); sys.exit(2)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

SKIP_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".css", ".mp4")

def want(url, filters):
    if not url: return False
    u = url.lower()
    if any(u.split("?")[0].endswith(e) for e in SKIP_EXT): return False
    return any(f in u for f in filters)

def pick_page_target(port, site):
    r = httpx.get(f"http://localhost:{port}/json", timeout=5); r.raise_for_status()
    for t in r.json():
        if t.get("type") == "page" and site in t.get("url", ""):
            return t
    for t in r.json():
        if t.get("type") == "page":
            return t
    raise RuntimeError("no page target")

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default="captured.jsonl")
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--site", default="betmexico")
    ap.add_argument("--filters", default="/api/,betmexico.mx,flags.betmexico,paymentsapi.betmexico")
    args = ap.parse_args()
    filters = args.filters.split(",")

    tgt = pick_page_target(args.port, args.site)
    ws_url = tgt["webSocketDebuggerUrl"]
    print(f"[cdp] target: {tgt.get('url','')[:70]}", file=sys.stderr)
    print(f"[cdp] out: {args.out}", file=sys.stderr)

    reqs = {}            # requestId -> info
    pending = {}         # response id -> future (para getResponseBody)
    rid = [0]
    def nid():
        rid[0] += 1; return rid[0]

    async with websockets.connect(ws_url, max_size=128*1024*1024) as ws:
        # habilitar dominios
        await ws.send(json.dumps({"id": nid(), "method": "Network.enable",
                                  "params": {"maxPostDataSize": 2*1024*1024}}))

        async def get_body(request_id):
            """Pide el body sin bloquear el stream. Devuelve future."""
            i = nid()
            fut = asyncio.get_event_loop().create_future()
            pending[i] = fut
            try:
                await ws.send(json.dumps({"id": i, "method": "Network.getResponseBody",
                                          "params": {"requestId": request_id}}))
            except Exception as e:
                pending.pop(i, None)
                return None, str(e)
            try:
                return await asyncio.wait_for(fut, timeout=4), None
            except asyncio.TimeoutError:
                pending.pop(i, None)
                return None, "timeout"
            except Exception as e:
                pending.pop(i, None)
                return None, str(e)

        with open(args.out, "a", encoding="utf-8") as f:
            print("[cdp] escuchando... (Ctrl+C para parar)", file=sys.stderr)
            while True:
                raw = await ws.recv()
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue

                # respuestas a nuestros requests (getResponseBody)
                if "id" in msg and msg["id"] in pending:
                    fut = pending.pop(msg["id"])
                    if not fut.done():
                        if "error" in msg:
                            fut.set_result({"error": msg["error"]})
                        else:
                            fut.set_result(msg.get("result", {}))
                    continue

                m = msg.get("method", "")
                p = msg.get("params", {})

                if m == "Network.requestWillBeSent":
                    rq = p.get("request", {})
                    url = rq.get("url", "")
                    if not want(url, filters):
                        continue
                    rid_ = p.get("requestId")
                    info = {
                        "ts_cdp": p.get("timestamp"),
                        "ts_iso": now_iso(),
                        "url": url,
                        "method": rq.get("method"),
                        "req_headers": rq.get("headers", {}),
                        "post_data": rq.get("postData"),
                        "type": p.get("type"),
                        "initiator": p.get("initiator", {}).get("type"),
                        "requestId": rid_,
                    }
                    reqs[rid_] = info
                    f.write(json.dumps({"evt": "request", **info}, ensure_ascii=False) + "\n")
                    f.flush()
                    pm = f" post={len(rq.get('postData',''))}B" if rq.get("postData") else ""
                    print(f"[req] {rq.get('method')} {url[:95]}{pm}", file=sys.stderr)

                elif m == "Network.responseReceived":
                    rid_ = p.get("requestId")
                    info = reqs.get(rid_)
                    if not info: continue
                    resp = p.get("response", {})
                    info["status"] = resp.get("status")
                    info["resp_headers"] = resp.get("headers", {})
                    info["remoteIP"] = resp.get("remoteIPAddress")
                    info["resp_ts_iso"] = now_iso()

                elif m == "Network.loadingFinished":
                    rid_ = p.get("requestId")
                    info = reqs.get(rid_)
                    if not info: continue
                    # pedir body via future (non-blocking al stream)
                    result, err = await get_body(rid_)
                    if result and "body" in result:
                        body = result["body"]
                        try:
                            info["body"] = json.loads(body)
                        except Exception:
                            info["body_text"] = body[:8000]
                    elif err:
                        info["body_err"] = err
                    f.write(json.dumps({"evt": "response", **info}, ensure_ascii=False) + "\n")
                    f.flush()
                    print(f"[resp] {info.get('method')} {info.get('status')} {info.get('url','')[:80]} body={'y' if 'body' in info or 'body_text' in info else 'n'}", file=sys.stderr)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[cdp] parado", file=sys.stderr)
