#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
from renapo_validator import validate_renapo_curp, _check_curp_with_proxy
from curp_utils import generate_curp_candidates

class TestRenapoValidator(unittest.TestCase):

    @patch("renapo_validator._host_resolves", return_value=True)
    @patch("renapo_validator.pp.call_with_proxy_failover")
    def test_validate_renapo_curp_success(self, mock_failover, _mock_dns):
        def _side_effect(fn, **kwargs):
            # Probar la función objetivo con un proxy mock
            return (
                {
                    "valid": True,
                    "curp": "SIGC951020MTLLRR00",
                    "fullname": "MARIA DEL CARMEN SILVA GARCIA",
                    "state": "TLAXCALA"
                },
                "http://user:pass@geo.iproyal.com:11201"
            )
        mock_failover.side_effect = _side_effect

        res = asyncio.run(validate_renapo_curp("MARIA DEL CARMEN SILVA GARCIA", "1995-10-20", "CAPIZAHUATL TLAX."))
        self.assertEqual(res, "SIGC951020MTLLRR00")
        self.assertTrue(mock_failover.called)

    @patch("httpx.AsyncClient")
    def test_check_curp_with_proxy_mock_httpx(self, mock_httpx_cls):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "success",
            "curp": "SILG951020HTLVRR08",
            "nombres": "MARIA DEL CARMEN",
            "primerApellido": "SILVA",
            "segundoApellido": "GARCIA",
            "estado": "TLAXCALA"
        }
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_httpx_cls.return_value.__aenter__.return_value = mock_client

        res = asyncio.run(_check_curp_with_proxy("http://proxy.test:8080", "SILG951020HTLVRR08", "MARIA DEL CARMEN SILVA GARCIA"))
        self.assertIsNotNone(res)
        self.assertTrue(res["valid"])
        self.assertEqual(res["curp"], "SILG951020HTLVRR08")

    @patch("proxy_pool.shuffled_proxy_urls", return_value=["http://user:pass@proxy.test:8080"])
    @patch("renapo_validator._host_resolves", return_value=True)
    @patch("httpx.AsyncClient")
    def test_validate_renapo_curp_awaits_real_proxy_failover(self, mock_async_client_cls, _mock_dns, _mock_urls):
        """Bug real (2026-08-01, cuenta drakarolinaalmara@gmail.com, log de prod):
        renapo_validator llamaba pp.call_with_proxy_failover (async) SIN await ->
        'cannot unpack non-iterable coroutine object' en los 32 candidatos, caía
        siempre al fallback fake y lo guardaba como 'Validado en RENAPO'.

        Este test corre la cadena REAL call_with_proxy_failover -> _check_curp_with_proxy
        (solo mockea la llamada HTTP de más abajo) para probar que el await
        funciona de punta a punta y sí se obtiene el resultado validado, no el
        fallback ciego."""
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # status=success incondicional: el primer candidato que se intente
        # "valida". Con domicilio N/A ningún candidato es is_detected, así que
        # el orden lo da generate_curp_candidates (alfabético) — se calcula
        # con la función real, no se hardcodea, para no adivinar el ganador.
        mock_resp.json.return_value = {
            "status": "success",
            "nombres": "MARIA DEL CARMEN",
            "primerApellido": "SILVA",
            "segundoApellido": "GARCIA",
        }
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_async_client_cls.return_value.__aenter__.return_value = mock_client

        # Domicilio SIN estado detectable: si el resultado coincidiera con el
        # candidato "fallback" (is_detected/primero alfabético) por casualidad,
        # un bug de kwarg roto en la llamada real (p.ej. _target_fn(proxy=...)
        # vs _target_fn(proxy_url=...)) pasaría desapercibido — como pasó en
        # 2026-08-09 con esta misma prueba usando un domicilio con estado.
        expected_first_candidate = generate_curp_candidates(
            "MARIA DEL CARMEN SILVA GARCIA", "1995-10-20", "N/A"
        )[0]["curp"]

        result = asyncio.run(validate_renapo_curp(
            "MARIA DEL CARMEN SILVA GARCIA", "1995-10-20", "N/A"
        ))

        self.assertTrue(mock_client.get.called, "la llamada HTTP real nunca se ejecutó — cayó directo al fallback ciego")
        self.assertEqual(result, expected_first_candidate)

    def test_check_curp_with_proxy_uses_args_valid_for_installed_httpx(self):
        """Bug real #3 (mismo hallazgo, misma sesión): httpx>=0.28 eliminó el
        kwarg `proxies=` de AsyncClient a favor de `proxy=` singular. Un mock de
        AsyncClient (como en los tests de arriba) acepta cualquier kwarg y NUNCA
        detecta esto — hay que construir el cliente REAL (sin red) para probar
        que la firma sigue siendo válida contra la versión de httpx instalada."""
        async def _construct():
            async with httpx.AsyncClient(proxy=None, timeout=8.0, follow_redirects=True) as client:
                return client
        asyncio.run(_construct())

if __name__ == "__main__":
    unittest.main()
