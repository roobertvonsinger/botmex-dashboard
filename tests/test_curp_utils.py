#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from curp_utils import compute_curp, generate_curp_candidates, _detect_state_code

class TestCurpUtils(unittest.TestCase):
    def test_compute_curp_basic(self):
        # Juan Pérez López, 1990-05-15, Jalisco
        curp = compute_curp("JUAN PEREZ LOPEZ", "1990-05-15", "GUADALAJARA JAL")
        self.assertIsNotNone(curp)
        self.assertEqual(len(curp), 18)
        self.assertEqual(curp[11:13], "JC")  # Jalisco = JC

    def test_state_override(self):
        # Forzar estado a Veracruz (VZ)
        curp = compute_curp("JUAN PEREZ LOPEZ", "1990-05-15", "GUADALAJARA JAL", state_code_override="VZ")
        self.assertIsNotNone(curp)
        self.assertEqual(curp[11:13], "VZ")

    def test_generate_candidates(self):
        candidates = generate_curp_candidates("MARIA DEL CARMEN SILVA GARCIA", "1995-10-20", "CAPIZAHUATL TLAX.")
        self.assertEqual(len(candidates), 32)
        # El primero debe ser el detectado (Tlaxcala = TL)
        self.assertTrue(candidates[0]["is_detected"])
        self.assertEqual(candidates[0]["code"], "TL")

if __name__ == "__main__":
    unittest.main()
