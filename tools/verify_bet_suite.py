#!/usr/bin/env python3
"""Runner Canónico de Auditoría para /bet (BotMexico)
=====================================================
Ejecuta la suite de pruebas canónica de `/bet` para garantizar que ningún
cambio rompa las 9 invariantes de selección, scoring, afinidad, 3 strikes y tiempos.

Uso:
    python tools/verify_bet_suite.py
"""
import sys
import subprocess
from pathlib import Path

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    root_dir = Path(__file__).resolve().parent.parent
    cmd = [sys.executable, "-m", "pytest", "tests/test_bet_canonical_suite.py", "-v"]
    print("=" * 60)
    print("🇲🇽 EJECUTANDO SUITE CANÓNICA DE PRUEBAS FUNCIONALES PARA /bet")
    print(f"Directorio: {root_dir}")
    print("Comando: " + " ".join(cmd))
    print("=" * 60)

    res = subprocess.run(cmd, cwd=str(root_dir))
    if res.returncode == 0:
        print("\n✅ TODAS LAS 9 INVARIANTES CANÓNICAS DE /bet ESTÁN 100% OPERATIVAS Y VERIFICADAS.")
        sys.exit(0)
    else:
        print("\n❌ FALLO CRÍTICO: La suite canónica de /bet ha detectado una regresión operativa.")
        sys.exit(res.returncode)

if __name__ == "__main__":
    main()
