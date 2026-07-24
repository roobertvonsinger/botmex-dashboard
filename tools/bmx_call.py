#!/usr/bin/env python3
"""Calleo autorizado de endpoints BetMexico con JWT cacheado de la BD + proxy del pool.
Corre DENTRO del contenedor betmexico-web (tiene acceso a BD + proxy_pool + JWTs).

Uso (vía docker exec):
  python bmx_call.py <email> <method> <path> [--body '{"k":"v"}'] [--json-out]
  path = path absoluto desde paymentsapi.betmexico.mx (ej: /api/User/BankAccounts)
         o '/api/Users/' para betmexico.mx (pasar --host betmexico)

NUNCA imprime el JWT. Solo el status + body de respuesta.

Ejemplos:
  python bmx_call.py msaidrzz@gmail.com GET /api/User/BankAccounts
  python bmx_call.py msaidrzz@gmail.com GET /api/Wallet/Total/Amount/ByAccountType
  python bmx_call.py msaidrzz@gmail.com POST /api/stp/BeginDeposit
  python bmx_call.py msaidrzz@gmail.com GET /api/Users/ --host betmexico
"""
import sys, os, json, argparse, sqlite3
import httpx

PAYMENTS = "https://paymentsapi.betmexico.mx"
BETMEXICO = "https://betmexico.mx"
DB = "/data/betmexico_accounts.db"


def load_jwt(email):
    db = sqlite3.connect(DB)
    r = db.execute("SELECT jwt_token, jwt_expires_at, status FROM accounts WHERE email LIKE ?",
                   (email.split("@")[0] + "%",)).fetchone()
    db.close()
    if not r:
        return None, "no existe cuenta con ese email"
    jwt, exp, status = r
    if not jwt:
        return None, f"cuenta sin jwt_token (status={status})"
    import time
    if exp and exp < int(time.time()):
        return None, f"jwt EXPIRADO (exp={exp}, status={status})"
    return jwt, f"ok status={status} exp={exp}"


def get_proxy():
    """Pide un proxy del pool (nunca proxyless en prod). Usa el helper canónico."""
    try:
        import proxy_pool as pp
        url = pp.build_admin_proxy_url()
        if not url:
            return None, "pool seco"
        host = pp._proxy_host(url)
        return url, f"proxy {host}"
    except Exception as e:
        return None, f"proxy_pool error: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("email")
    ap.add_argument("method", choices=["GET", "POST", "PUT", "PATCH"])
    ap.add_argument("path", help="path desde la raíz, ej /api/User/BankAccounts")
    ap.add_argument("--body", default=None, help="JSON body para POST/PUT")
    ap.add_argument("--host", default="paymentsapi", choices=["paymentsapi", "betmexico"])
    ap.add_argument("--no-proxy", action="store_true", help="SOLO debug local, NUNCA en prod")
    args = ap.parse_args()

    jwt, info = load_jwt(args.email)
    if not jwt:
        print(f"[jwt] FAIL: {info}"); sys.exit(1)
    print(f"[jwt] {info}", file=sys.stderr)

    base = PAYMENTS if args.host == "paymentsapi" else BETMEXICO
    url = base + args.path

    proxy = None
    if not args.no_proxy:
        proxy, pinfo = get_proxy()
        print(f"[proxy] {pinfo}", file=sys.stderr)
        if not proxy:
            print(f"[proxy] FAIL: {pinfo}"); sys.exit(2)
    else:
        print("[proxy] DESACTIVADO (--no-proxy)", file=sys.stderr)

    headers = {"Authorization": f"Bearer {jwt}",
               "Accept": "application/json",
               "Content-Type": "application/json",
               "Origin": "https://betmexico.mx",
               "Referer": "https://betmexico.mx/"}

    body = json.loads(args.body) if args.body else None
    print(f"[req] {args.method} {url} body={'sí' if body else 'no'}", file=sys.stderr)

    try:
        with httpx.Client(timeout=30.0, verify=False, proxy=proxy) as c:
            r = c.request(args.method, url, headers=headers, json=body)
    except Exception as e:
        print(f"[err] {type(e).__name__}: {e}"); sys.exit(3)

    print(f"[resp] {r.status_code}")
    txt = r.text
    try:
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
    except Exception:
        print(txt[:3000])


if __name__ == "__main__":
    main()
