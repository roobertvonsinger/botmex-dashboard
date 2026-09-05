#!/usr/bin/env python3
"""
scripts/kvm4_local_backup.py — Snapshot atómico local cada 12h en KVM4.
Capa de redundancia local del servidor BetMexico.
"""
import glob
import os
import sqlite3
import sys
import time
from datetime import datetime

DB_PATH = "/opt/kvm4/apps/betmexico/data/betmexico_accounts.db"
BACKUPS_DIR = "/opt/kvm4/apps/betmexico/data/backups"
LOG_FILE = "/opt/kvm4/apps/betmexico/data/logs/backup.log"
RETENTION_COUNT = 14

os.makedirs(BACKUPS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)


def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def main():
    if not os.path.exists(DB_PATH):
        log(f"ERROR: No existe {DB_PATH}")
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst_path = f"{BACKUPS_DIR}/betmexico_snap_{ts}.db"
    tmp_path = f"{dst_path}.tmp"

    log(f"Iniciando snapshot local KVM4 -> {os.path.basename(dst_path)}...")
    t0 = time.time()
    try:
        src = sqlite3.connect(DB_PATH, timeout=30.0)
        dst = sqlite3.connect(tmp_path)
        src.backup(dst)
        dst.close()
        src.close()

        os.rename(tmp_path, dst_path)
        elapsed = time.time() - t0
        size_mb = os.path.getsize(dst_path) / (1024 * 1024)
        log(f"[OK] Snapshot creado exitosamente ({size_mb:.2f} MB en {elapsed:.2f}s)")

        # Poda de retención
        files = sorted(glob.glob(f"{BACKUPS_DIR}/betmexico_snap_*.db"), key=os.path.getmtime, reverse=True)
        if len(files) > RETENTION_COUNT:
            for old in files[RETENTION_COUNT:]:
                try:
                    os.remove(old)
                    log(f"Poda snapshot antiguo: {os.path.basename(old)}")
                except Exception as e:
                    log(f"Error eliminando {old}: {e}")

    except Exception as e:
        log(f"CRITICAL ERROR en snapshot: {e}")
        if os.path.exists(tmp_path):
            try: os.remove(tmp_path)
            except: pass
        sys.exit(1)


if __name__ == "__main__":
    main()
