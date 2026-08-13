"""scripts/update_proxy001_list.py — Carga la lista fresca de Proxy001 desde Downloads hacia proxy_pool.py.
"""
import re

with open(r"C:\Users\rober\Downloads\Proxy001_stripe_ok.txt", "r", encoding="utf-8") as f:
    lines = [line.strip() for line in f if line.strip()]

proxy_list = []
for line in lines:
    parts = line.split(":")
    if len(parts) == 4:
        server = f"{parts[0]}:{parts[1]}"
        user = parts[2]
        pw = parts[3]
        proxy_list.append({"server": server, "username": user, "password": pw})

with open("proxy_pool.py", "r", encoding="utf-8") as f:
    content = f.read()

# Actualizar la lista PROXY001_PROXIES
formatted = "PROXY001_PROXIES: List[Dict[str, str]] = [\n"
for p in proxy_list:
    formatted += f'    {{"server": "{p["server"]}", "username": "{p["username"]}", "password": "{p["password"]}"}},\n'
formatted += "]"

content = re.sub(r"PROXY001_PROXIES: List\[Dict\[str, str\]\] = \[.*?\]", formatted, content, flags=re.DOTALL)

# Quitar proxy001 e iproyal de _EXCLUDED_PROXY_HOSTS
content = content.replace('_EXCLUDED_PROXY_HOSTS: tuple = ("litport", "iproyal", "proxy001")', '_EXCLUDED_PROXY_HOSTS: tuple = ("litport",)')
content = content.replace('_EXCLUDED_PROXY_HOSTS: tuple = ("litport", "iproyal")', '_EXCLUDED_PROXY_HOSTS: tuple = ("litport",)')

with open("proxy_pool.py", "w", encoding="utf-8") as f:
    f.write(content)

print(f"✅ proxy_pool.py actualizado con {len(proxy_list)} proxies de Proxy001_stripe_ok.txt")
