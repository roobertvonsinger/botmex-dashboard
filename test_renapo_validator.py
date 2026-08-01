#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch, MagicMock
from renapo_validator import validate_renapo_curp, _check_curp_with_proxy

class TestRenapoValidator(unittest.TestCase):

    @patch("renapo_validator.pp.call_with_proxy_failover")
    def test_validate_renapo_curp_success(self, mock_failover):
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

        res = validate_renapo_curp("MARIA DEL CARMEN SILVA GARCIA", "1995-10-20", "CAPIZAHUATL TLAX.")
        self.assertEqual(res, "SIGC951020MTLLRR00")
        self.assertTrue(mock_failover.called)

    @patch("httpx.Client")
    def test_check_curp_with_proxy_mock_httpx(self, mock_httpx_cls):
        mock_client = MagicMock()
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
        mock_client.get.return_value = mock_resp
        mock_httpx_cls.return_value.__enter__.return_value = mock_client

        res = _check_curp_with_proxy("http://proxy.test:8080", "SILG951020HTLVRR08", "MARIA DEL CARMEN SILVA GARCIA")
        self.assertIsNotNone(res)
        self.assertTrue(res["valid"])
        self.assertEqual(res["curp"], "SILG951020HTLVRR08")

if __name__ == "__main__":
    unittest.main()
