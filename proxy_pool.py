"""Pool de proxies admin local del dashboard + failover real.

Combina los proxies del bot (`betmexico_config.ADMIN_PROXIES`) con extras
definidos acÃ¡. Permite agregar/quitar proxies sin tocar el monorepo del bot â€”
el dashboard vive en repo aislado y debe gestionar su propio pool.

Dos APIs:
- `build_admin_proxy_url()` â€” random pick (compat). Usar solo donde no se
  pueda hacer failover (ej. healthchecks). NO usar para login real.
- `call_with_proxy_failover(fn, ...)` â€” RECOMENDADO. Llama `fn(*args, proxy=URL,
  **kwargs)` rotando por el pool si la llamada falla con timeout/connection
  error de proxy. Retorna `(result, proxy_url_used)`: el caller puede reusar
  `proxy_url_used` en steps subsecuentes (ej. ApiChecker post-login) para
  mantener afinidad de proxy validado.
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("dashboard.proxy_pool")

# Proxies extra que NO viven en betmexico_config.py del bot.
# Mismo formato: {server, username, password}. El sufijo `_country-mx` o
# `-country-mx` en username fuerza ruteo por IP MÃ©xico.
EXTRA_ADMIN_PROXIES: List[Dict[str, str]] = [
    # IPRoyal (Premium MX residencial, ROTATIVO nacional) â€” corregido 2026-05-29.
    # Antes estaba con `city-ciudadobregon` (puerto 11200) = IP PEGADA a una ciudad
    # â†’ se quemaba y daba 406 masivo. Robert dio el correcto: puerto 11201 +
    # `_country-mx_streaming-1` (sin city) â†’ rota IPs por todo MX = IP fresca por
    # intento, mucho mejor contra el antifraude de BetMexico. Compartido con
    # Ruthopia (telcel gate) â€” vigilar consumo.
    {
        "server": "geo.iproyal.com:11201",
        "username": "sH3PhyrRotHpRxYY2sEiS",
        "password": "u7JSejn6ZTSHfbpR_country-mx_streaming-1",
    },
    # NodeMaven (Premium MX) â€” agregado 2026-05-21.
    # âš ï¸ DEGRADADO: 504 Gateway Timeout intermitente (~22% medido 2026-06-24) +
    # 406 crÃ³nico (IP quemada). Se mantiene SOLO como fallback de OTRO proveedor
    # (diversidad ante caÃ­da de Data Impulse); su peso real es ~2/52. Ver Data
    # Impulse abajo, que pasa a ser el proxy primario.
    {
        "server": "gate.nodemaven.com:8080",
        "username": "andregutti97_gmail_com-country-mx",
        "password": "5qpn3scda5",
    },
]

# Data Impulse (Premium MX residencial) â€” PRIMARIO. Host/user/pass FIJOS; el PUERTO
# define el modo:
#   - 10000..10049 (lote viejo, credenciales `edb0501e...`) = 50 sesiones STICKY.
#     Se QUEMARON con el uso (logins + un health check que las machacaba 150k
#     veces/sem contra ipinfo) â†’ 406/429 masivo desde ~26-jun.
#   - 823 (mismo lote viejo) = ROTATORIO nacional MX, adoptado 2026-06-28 como fix.
#     Sano en uptime (12/12â†’200, 0% 504) pero un benchmark independiente (Proxyway
#     2026, ver research proveedores 2026-07-01) midiÃ³ el PEOR fraud/risk score del
#     mercado (3.9) para el pool base de DataImpulse sin el toggle "IP quality" â€”
#     coincide con la degradaciÃ³n medida en prod la semana del 2026-06-24 (tasa de
#     login exitoso cayendo de ~50%/intento a ~30%/intento).
#   - 10000..10699 (LOTE NUEVO 2026-07-01/07-11, credenciales `506e02a6...`, dado
#     por Robert) = 700 sesiones STICKY, cada una rota de IP sola cada 3 MIN (TTL
#     del plan, no algo que controlemos por cÃ³digo). Reemplaza el pool 823 como
#     PRIMARIO. Objetivo: recuperar el pâ‰ˆ50%/intento que sÃ­ se midiÃ³ viable en
#     mayo con sticky fresca (vs. rotativo genÃ©rico degradado).
#     âš ï¸ DiagnÃ³stico 2026-07-11 (forense "masacre de IPs", Robert): con solo 100
#     puertos (10000-10099) y ~900 cuentas activas, cada IP terminaba autenticando
#     decenas de emails distintos â€” patrÃ³n que el antifraude de BetMexico marca
#     independientemente de concurrencia/cooldown (conecta con el bucle de quema
#     del jwt_keeper, ver docs/ERRORS.md). Ampliar a 700 puertos baja mucho la
#     razÃ³n cuentas-por-IP; el TTL de 3min ademÃ¡s da rotaciÃ³n natural: dos cuentas
#     que caen en el mismo puerto separadas por >3min (tÃ­pico â€” el keeper espacÃ­a
#     20-45s entre 8 cuentas, ciclo completo 3-6min) casi siempre pegan IP fÃ­sica
#     distinta. Si el 406/429 vuelve a subir pese a esto, ya no es el pool â€” ver
#     docs/plans/login-orchestration-rework.md Â§6 (StickySessionManager).
# El sufijo `__cr.mx` en el username fuerza paÃ­s MÃ©xico.
# Data Impulse â€” EXCLUIDO por fallo masivo de gateway (`502 NO_HOST_CONNECTION`).
# Excluido agregando "dataimpulse" a _EXCLUDED_PROXY_HOSTS.

# Proxy001 (500 proxies residenciales MX)
PROXY001_PROXIES: List[Dict[str, str]] = [
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_31476555_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_89351192_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_26526394_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_51271222_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_79171264_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_38476684_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_61367356_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_81293992_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_19913762_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_39777566_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_52423869_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_42535467_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_32413233_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_43374656_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_71776957_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_69272435_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_78824427_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_75131376_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_64377819_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_95177216_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_65636563_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_49562668_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_23221123_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_49576392_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_75282774_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_29519791_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_26943314_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_49862375_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_77142558_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_11937481_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_57173769_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_79635365_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_35656771_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_44776444_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_58757526_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_28649385_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_89953673_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_88149376_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_54555151_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_88598224_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_16413934_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_81218749_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_53389578_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_91363526_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_89296676_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_31999283_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_29489766_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_92959977_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_59146662_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_69463461_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_67514735_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_54116845_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_34147187_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_68357763_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_37767814_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_19329389_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_83742732_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_93633838_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_23658339_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_94984647_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_77351359_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_38439981_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_87377566_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_36333417_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_88149238_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_35343686_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_84915629_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_56427768_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_22518731_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_27668949_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_76929657_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_11159947_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_22439644_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_16935987_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_55572442_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_78172852_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_65396987_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_78265939_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_52626791_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_74784782_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_87148868_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_32742545_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_17711576_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_98157415_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_75536633_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_39476134_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_87368757_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_55513399_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_22539261_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_36693797_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_57668441_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_71229278_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_21622758_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_15138486_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_43967335_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_79933331_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_89943728_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_57796642_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_53334472_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_77716672_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_36243812_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_13924632_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_63478129_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_78863184_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_69648475_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_42984561_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_61411517_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_98924823_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_58841388_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_58775987_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_25953512_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_35146442_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_45793143_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_95314855_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_62325333_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_24594127_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_18971124_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_41237229_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_89444851_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_68122753_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_65826232_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_15746249_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_74948973_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_83955584_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_71181336_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_67272923_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_22969465_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_13996181_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_56919781_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_33811675_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_44823923_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_73643281_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_29816736_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_87714694_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_25277533_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_27111346_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_17919578_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_67152234_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_47349215_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_38715123_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_32269225_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_17953674_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_23444549_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_44583416_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_85584228_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_52798193_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_42986615_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_72556976_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_97164986_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_67125614_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_12772473_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_59859523_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_22564729_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_49618766_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_55112981_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_62247756_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_44889675_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_93288676_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_43447591_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_96488678_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_86762689_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_69439352_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_28593942_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_42491642_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_77778193_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_43983649_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_57825251_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_64327441_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_97624592_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_86226196_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_18782269_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_99629828_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_93137754_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_51276664_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_63766636_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_54877576_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_95876853_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_45574886_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_91125236_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_93831848_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_71782173_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_33699986_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_84845889_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_45899666_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_77671679_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_92169169_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_47441242_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_36221648_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_65446812_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_11684378_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_51729913_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_93693319_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_25162277_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_72459828_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_19129761_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_97353385_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_78117369_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_69192114_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_39888468_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_97244377_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_16585517_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_83587396_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_41158386_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_36789718_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_39743829_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_14762127_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_35214581_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_57483818_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_99276165_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_99978553_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_45752135_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_54126919_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_16481298_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_93321873_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_22578996_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_37891252_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_71846693_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_91998854_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_87319818_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_83518136_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_66471791_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_82762583_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_68343786_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_72243386_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_65124554_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_21331119_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_93957575_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_67613136_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_56147561_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_33718686_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_73312353_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_15213284_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_11138629_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_33746218_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_43723399_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_65172615_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_61413159_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_47874778_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_31176561_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_88528448_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_46679499_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_97863824_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_49514619_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_57265235_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_17161197_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_68547521_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_39612889_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_34833652_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_81315887_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_19937513_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_95696852_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_61576657_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_11999673_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_41479676_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_66247356_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_83451266_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_49221986_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_62552311_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_88433868_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_48375817_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_43372428_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_86229414_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_15496912_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_64744637_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_43787113_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_28221622_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_73225928_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_98297514_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_21177649_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_97671453_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_59633487_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_68144691_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_84521553_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_28399845_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_86987292_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_61673989_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_39189431_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_22769757_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_59587923_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_64146844_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_64543583_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_52614199_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_87347333_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_38267412_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_32151646_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_46973915_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_59169489_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_82948562_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_45294685_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_78786912_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_38961663_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_61421591_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_22929486_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_27269829_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_71899357_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_66529686_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_51653463_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_97354136_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_62213447_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_72441783_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_41227926_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_49463974_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_75787495_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_81796598_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_22871566_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_11944585_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_64251752_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_62849122_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_62919572_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_82323294_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_89132512_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_34794982_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_12163398_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_49911378_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_89119251_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_14898745_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_51522242_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_34626411_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_83452235_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_72882322_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_66551434_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_35679389_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_18919614_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_43836654_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_77371544_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_29566748_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_12539791_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_98977622_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_37618268_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_31647241_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_31458474_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_64466878_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_11821227_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_84814276_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_83757922_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_68287974_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_13159515_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_12966175_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_84818288_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_15881187_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_92936813_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_74338841_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_18889634_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_45687661_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_36758972_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_35991962_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_22639512_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_28199239_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_93541994_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_92764836_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_39562934_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_84579399_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_96492296_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_36394386_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_42188756_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_35557737_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_77394531_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_76312253_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_76422939_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_28515449_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_11198642_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_83585349_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_74389383_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_55968259_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_69955584_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_73399247_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_55743324_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_59517187_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_35524876_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_13415557_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_51756667_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_76713643_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_23635537_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_11389125_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_12777836_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_51184786_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_26262124_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_12872194_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_43471299_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_85453383_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_14844479_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_28742414_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_28139168_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_95948148_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_82559344_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_29977377_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_99316363_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_69326184_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_84185828_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_79235418_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_23897678_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_13586523_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_24321985_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_93218736_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_58831349_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_87675214_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_54465749_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_86183445_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_26327875_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_27574268_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_66999494_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_24674527_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_23119479_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_14573765_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_61597186_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_98758188_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_15951193_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_54178896_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_72183367_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_27651844_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_43767555_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_77379531_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_85149836_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_23343652_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_84467739_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_73628291_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_73135866_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_53179853_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_54179542_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_55399769_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_85479486_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_34298153_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_58737588_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_69884946_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_51393128_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_18932838_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_13434849_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_36927356_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_26136786_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_88552747_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_49557833_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_49467237_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_92697415_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_87338515_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_79324488_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_43821153_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_69966368_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_76878981_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_11119854_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_42786542_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_83893767_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_92476437_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_95521174_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_51674564_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_99828929_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_27964621_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_82229632_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_93222323_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_49999943_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_44297154_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_34962849_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_44189267_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_96957887_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_67891164_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_34196659_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_96733977_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_16527757_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_32212228_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_67535366_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_98385285_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_24636918_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_16263896_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_17292671_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_22217949_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_93879211_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_78115142_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_82648758_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_26431229_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_51644414_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_26177152_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_14416831_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_19147879_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_74753174_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_19275823_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_39738891_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_61586893_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_91724548_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_58671828_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_34935287_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_98638541_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_75778878_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_92818527_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_87238574_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_11611466_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_81686366_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_34343732_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_62562862_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_36517871_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_91145695_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_65913311_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_57321188_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_56364342_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_82579662_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_48389869_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_17627618_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_15712946_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_51455646_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_75512361_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_32945697_time_2", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_68779417_time_2", "password": "pwd639719"}
]


_DATAIMPULSE_HOST = "gw.dataimpulse.com"
_DATAIMPULSE_USER = "506e02a6444effce62de__cr.mx"
_DATAIMPULSE_PASS = "59bd44415b7b9c7c"
_DATAIMPULSE_STICKY_PORT_START = 10000
_DATAIMPULSE_STICKY_PORT_END = 10999

DATAIMPULSE_PROXIES: List[Dict[str, str]] = [
    {
        "server": f"{_DATAIMPULSE_HOST}:{port}",
        "username": _DATAIMPULSE_USER,
        "password": _DATAIMPULSE_PASS,
    }
    for port in range(_DATAIMPULSE_STICKY_PORT_START, _DATAIMPULSE_STICKY_PORT_END + 1)
]

# Hosts excluidos del pool â€” proxies con reputaciÃ³n quemada o caÃ­dos.
# - litport: US IP / quemado.
# - iproyal: 402 Payment Required.
# - dataimpulse: 502 NO_HOST_CONNECTION (gateway caÃ­do). Excluido 2026-08-12.
_EXCLUDED_PROXY_HOSTS: tuple = ("litport", "iproyal", "dataimpulse")


def _bot_proxies() -> List[Dict[str, str]]:
    """Lista de proxies del bot (si estÃ¡ disponible)."""
    try:
        from betmexico_config import ADMIN_PROXIES  # type: ignore
        return list(ADMIN_PROXIES or [])
    except Exception:
        return []


def all_proxies() -> List[Dict[str, str]]:
    """Lista completa: bot + extras locales, excluyendo hosts quemados
    (`_EXCLUDED_PROXY_HOSTS`). El filtro se aplica acÃ¡ para que TODO el
    pool (failover, random pick, shuffled) herede la exclusiÃ³n.

    Dedup por (server, username) â€” el bot (monorepo, `betmexico_config.
    ADMIN_PROXIES`) y este archivo pueden listar el MISMO puerto DataImpulse
    dos veces (detectado 2026-07-11: 200 entradas reportadas, 100 servers
    Ãºnicos). Sin dedup, `random.choice`/`shuffled_proxy_urls` pesan doble
    a los puertos duplicados â€” sesga la rotaciÃ³n en vez de repartir parejo
    entre las sesiones sticky reales."""
    combined = _bot_proxies() + EXTRA_ADMIN_PROXIES + PROXY001_PROXIES + DATAIMPULSE_PROXIES
    seen: set = set()
    deduped: List[Dict[str, str]] = []
    for p in combined:
        key = (p.get("server", ""), p.get("username", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    return [
        p for p in deduped
        if not any(bad in p.get("server", "").lower() for bad in _EXCLUDED_PROXY_HOSTS)
    ]


def _to_url(p: Optional[Dict[str, str]]) -> Optional[str]:
    if not p:
        return None
    srv = p.get("server", "")
    u = p.get("username", "")
    pw = p.get("password", "")
    if not srv:
        return None
    if u and pw:
        return f"http://{u}:{pw}@{srv}"
    return f"http://{srv}"


def get_admin_proxy() -> Optional[Dict[str, str]]:
    """Random pick del pool combinado. Returns None si no hay ninguno."""
    pool = all_proxies()
    if not pool:
        return None
    return random.choice(pool)


def build_admin_proxy_url() -> Optional[str]:
    """Random pick â†’ URL `http://user:pass@server`. Compat / single-shot.
    Para login real preferir `call_with_proxy_failover`."""
    return _to_url(get_admin_proxy())


def shuffled_proxy_urls() -> List[str]:
    """Lista de proxy URLs del pool en orden aleatorio (para failover).
    Lista vacÃ­a si el pool estÃ¡ vacÃ­o."""
    pool = all_proxies()
    if not pool:
        return []
    shuffled = list(pool)
    random.shuffle(shuffled)
    return [u for u in (_to_url(p) for p in shuffled) if u]


# â”€â”€ Failover â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_PROXY_RETRY_EXCEPTIONS: tuple = ()


def _retry_exceptions() -> tuple:
    """Lazy: ensambla las excepciones por las que vale la pena rotar de proxy.
    Incluye fallos de conexiÃ³n, timeouts y errores de proxy. NO incluye errores
    HTTP del lado de BetMexico (401, 403, 500) â€” esos significan que el proxy
    funcionÃ³, el problema es la cuenta."""
    global _PROXY_RETRY_EXCEPTIONS
    if _PROXY_RETRY_EXCEPTIONS:
        return _PROXY_RETRY_EXCEPTIONS
    excs: List[type] = [asyncio.TimeoutError, OSError]
    try:
        import httpx
        excs.extend([
            httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout,
            httpx.ConnectError, httpx.ProxyError, httpx.RemoteProtocolError,
        ])
    except Exception:
        pass
    try:
        import httpcore
        excs.extend([
            httpcore.ConnectTimeout, httpcore.ReadTimeout, httpcore.WriteTimeout,
            httpcore.ConnectError, httpcore.ProxyError,
        ])
    except Exception:
        pass
    _PROXY_RETRY_EXCEPTIONS = tuple(excs)
    return _PROXY_RETRY_EXCEPTIONS


def _proxy_host(url: str) -> str:
    """`gate.nodemaven.com:8080` desde `http://user:pass@gate.nodemaven.com:8080`."""
    if "@" in url:
        return url.split("@", 1)[1]
    return url.replace("http://", "").replace("https://", "")


async def call_with_proxy_failover(
    fn: Callable[..., Awaitable[Any]],
    *args: Any,
    proxy: Optional[str] = None,
    proxy_kwarg: str = "proxy",
    captcha_retries: int = 5,
    **kwargs: Any,
) -> Tuple[Any, Optional[str]]:
    """Llama `fn(*args, proxy=URL, **kwargs)` con failover + retry de captcha.

    - Si `proxy` estÃ¡ dado explÃ­cito â†’ lo usa SIN failover (caller manda).
    - Si `proxy` es None â†’ cicla el pool reconectando (cada intento = IP nueva,
      los proxies son rotativos), reintentando cuando:
        a) la llamada lanza excepciÃ³n de conexiÃ³n/timeout, O
        b) devuelve un resultado de fallo de proxy, O
        c) devuelve un resultado de fallo de captcha (406 FAILURE_IN_CAPTCHA â†’
           status RETRY_CAPTCHA). Esto es la clave: el 406 NO es error de la
           cuenta sino de la REPUTACIÃ“N de la IP del proxy (loterÃ­a ~70% con
           IPRoyal). Rotar IP y reintentar convierte ~70%/intento en ~99.x%.
      Total de intentos = max(len(pool), captcha_retries).
    - Si el pool estÃ¡ vacÃ­o â†’ llama una vez con proxy=None.

    Nota: pasar `max_retries=1` a get_jwt como kwarg para que NO queme 3 captchas
    en la MISMA IP (inÃºtil si estÃ¡ quemada) â€” el retry de IP lo maneja acÃ¡.

    Returns:
        (resultado, proxy_url_usado). El caller puede reusar `proxy_url_usado`
        en steps siguientes (ej. ApiChecker despuÃ©s de get_jwt) para mantener
        afinidad de proxy validado.

    Raises:
        La Ãºltima excepciÃ³n si TODOS los intentos fallaron por conexiÃ³n.
        Cualquier excepciÃ³n no-proxy (ej. 401 de BetMexico) se re-lanza
        inmediatamente sin reintentar.
    """
    if proxy:
        result = await fn(*args, **{proxy_kwarg: proxy, **kwargs})
        return result, proxy

    urls = shuffled_proxy_urls()
    if not urls:
        result = await fn(*args, **{proxy_kwarg: None, **kwargs})
        return result, None

    retry_excs = _retry_exceptions()
    last_err: Optional[BaseException] = None
    last_result: Any = None
    # Cicla el pool hasta cubrir captcha_retries â€” cada vuelta reconecta al
    # proxy (rotativo) dando una IP fresca, que es lo que rescata del 406.
    n_attempts = max(len(urls), captcha_retries)
    for i in range(n_attempts):
        url = urls[i % len(urls)]
        try:
            result = await fn(*args, **{proxy_kwarg: url, **kwargs})
            # Algunas funciones (get_jwt) atrapan ProxyError adentro y devuelven
            # un tuple `(None, {"status": "ERROR", "error": "...ProxyError..."})`
            # en vez de propagar. Detectarlo y reintentar con otra IP.
            if _looks_like_proxy_failure_result(result):
                logger.warning(
                    f"[proxy_pool] {_proxy_host(url)} proxy-failure result "
                    f"â€” try {i+1}/{n_attempts}"
                )
                last_result = result
                continue
            # 406 FAILURE_IN_CAPTCHA â†’ IP quemada. Rotar IP y reintentar.
            if _looks_like_captcha_failure_result(result):
                logger.warning(
                    f"[proxy_pool] {_proxy_host(url)} captcha 406 (IP quemada) "
                    f"â€” rotando IP, try {i+1}/{n_attempts}"
                )
                last_result = result
                continue
            if i > 0:
                logger.info(
                    f"[proxy_pool] ok via {_proxy_host(url)} (intento {i+1})"
                )
            return result, url
        except retry_excs as e:  # type: ignore[misc]
            logger.warning(
                f"[proxy_pool] {_proxy_host(url)} fail "
                f"({type(e).__name__}: {str(e)[:120]}) â€” try {i+1}/{n_attempts}"
            )
            last_err = e
            continue
    # Agotados los intentos: si hubo result-style failure (proxy o captcha),
    # devolvemos el Ãºltimo resultado (el caller verÃ¡ RETRY_CAPTCHA â†’ LOGIN_FAILED);
    # si solo hubo excepciones de conexiÃ³n, raise.
    if last_result is not None:
        return last_result, urls[-1]
    if last_err is not None:
        raise last_err
    return last_result, urls[-1] if urls else None


_PROXY_FAILURE_TOKENS = (
    "ProxyError", "504 Gateway Timeout", "502 Bad Gateway",
    "ConnectError", "ReadTimeout", "ConnectTimeout", "RemoteProtocolError",
)


def _looks_like_proxy_failure_result(result: Any) -> bool:
    """Detecta resultados que indican fallo de proxy aunque NO se haya lanzado
    excepciÃ³n (porque la funciÃ³n interna los atrapÃ³). HeurÃ­stica:
    - Es un tuple (a, b) con `a is None` y `b` es dict con status ERROR
      y `error` contiene tokens tÃ­picos de proxy/timeout.
    """
    try:
        if not isinstance(result, tuple) or len(result) < 2:
            return False
        primary, meta = result[0], result[1]
        if primary is not None:
            return False
        if not isinstance(meta, dict):
            return False
        if meta.get("status") not in ("ERROR", "PROXY_ERROR", "TIMEOUT"):
            return False
        err_str = str(meta.get("error", ""))
        return any(tok in err_str for tok in _PROXY_FAILURE_TOKENS)
    except Exception:
        return False


def _looks_like_captcha_failure_result(result: Any) -> bool:
    """Detecta el fallo de captcha de get_jwt: tuple (None, {status: ...}) con
    status RETRY_CAPTCHA (BetMexico devolviÃ³ 406 FAILURE_IN_CAPTCHA) o
    CAPTCHA_TIMEOUT (pool sin tokens). En ambos casos vale rotar IP y reintentar:
    el 406 depende de la reputaciÃ³n de la IP del proxy, no de la cuenta."""
    try:
        if not isinstance(result, tuple) or len(result) < 2:
            return False
        primary, meta = result[0], result[1]
        if primary is not None:
            return False
        if not isinstance(meta, dict):
            return False
        return meta.get("status") in ("RETRY_CAPTCHA", "CAPTCHA_TIMEOUT")
    except Exception:
        return False
