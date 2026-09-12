import json
import sqlite3
import sys

def restore():
    report_path = '/app/data/mass_sweep_report_fix.json'
    db_path = '/app/betmexico_accounts.db'
    
    try:
        with open(report_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading report: {e}")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    count_restored = 0

    for res in data.get('results', []):
        email = res.get('email')
        verdict = res.get('verdict')
        status_pre = res.get('status_pre')

        # Si era LIVE antes del barrido...
        if status_pre == "LIVE":
            # Y la matamos por culpa de un 429 u otro error que NO ES ban real de credenciales
            if verdict not in ("LOGIN_DENIED", "AUTOEXCLUSION", "LIVE_FULL", "LIVE_NO_KYC"):
                cur.execute('''
                    UPDATE accounts 
                    SET status = 'LIVE'
                    WHERE LOWER(email) = LOWER(?)
                ''', (email,))
                count_restored += 1
                print(f"Restaurada a LIVE: {email} (Murió por {verdict})")

    conn.commit()
    conn.close()
    print(f"\nSe han restaurado {count_restored} cuentas a LIVE que fueron asesinadas injustamente.")

if __name__ == '__main__':
    restore()
