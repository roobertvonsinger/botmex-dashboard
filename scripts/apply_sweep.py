import json
import sqlite3
import sys

def apply_report():
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

    count_live = 0
    count_dead = 0
    count_skipped = 0

    for res in data.get('results', []):
        email = res.get('email')
        verdict = res.get('verdict')
        kyc = 1 if res.get('kyc') else 0
        bal = float(res.get('bal_real', 0.0))
        jwt_token = res.get('jwt_token')
        jwt_expires = res.get('jwt_expires_at')

        jwt_sql = ""
        jwt_params = ()
        if jwt_token:
            jwt_sql = ", jwt_token = ?, jwt_expires_at = ?"
            jwt_params = (jwt_token, jwt_expires)

        if verdict == "LIVE_FULL":
            sql = f"""
                UPDATE accounts 
                SET status = 'LIVE',
                    kyc_verified = ?, balance_real = ?
                    {jwt_sql}
                WHERE LOWER(email) = LOWER(?)
            """
            cur.execute(sql, (kyc, bal, *jwt_params, email))
            count_live += 1
            
        elif verdict == "LIVE_NO_KYC":
            sql = f"""
                UPDATE accounts 
                SET status = 'DEAD',
                    kyc_verified = 0, balance_real = ?
                    {jwt_sql}
                WHERE LOWER(email) = LOWER(?)
            """
            cur.execute(sql, (bal, *jwt_params, email))
            count_dead += 1
            
        elif verdict in ("LOGIN_DENIED", "AUTOEXCLUSION", "RATE_LIMITED"):
            cur.execute('''
                UPDATE accounts 
                SET status = 'DEAD'
                WHERE LOWER(email) = LOWER(?)
            ''', (email,))
            count_dead += 1
            
        else:
            # EXCEPTION / LOGIN_FAILED (fallos reales de proxy o timeouts puros)
            count_skipped += 1

    conn.commit()
    conn.close()
    print(f"Applied {count_live} LIVE, {count_dead} DEAD to DB. Skipped {count_skipped} exceptions/timeouts.")

if __name__ == '__main__':
    apply_report()
