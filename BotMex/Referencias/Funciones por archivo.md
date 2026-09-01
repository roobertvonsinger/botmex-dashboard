# Referencias — Funciones por Archivo

| Archivo | Función Clave | Línea aprox. | Propósito |
|---|---|---|---|
| `auto_deposit.py` | `run_auto_mission` | L77 | Orquestador principal de misión `/bet` |
| `auto_deposit.py` | `select_accounts_for_auto` | L120 | Matchmaker con cuotas Tier 40/40/20 |
| `auto_deposit.py` | `classify_deposit_status` | L920 | Clasificador de respuestas bancarias/API |
| `deposits.py` | `_run_deposit_with_phases` | L140 | Ejecución HTTP por fases con proxy failover |
| `account_refresh.py` | `refresh_account_task` | L210 | Actualización de balance con JWT vigente |
| `jwt_keeper.py` | `keep_jwt_alive_loop` | L85 | Renovación proactiva de tokens |
| `proxy_pool.py` | `call_with_proxy_failover` | L95 | Request resiliente con rotación de IPs |
| `withdrawals.py` | `execute_stp_withdrawal` | L110 | Dispersión SPEI / STP con CURP |
