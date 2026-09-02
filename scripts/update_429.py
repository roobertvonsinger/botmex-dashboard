import sqlite3

con = sqlite3.connect('/data/betmexico_accounts.db')
cur = con.cursor()
rows = cur.execute('SELECT email, status, dead_reason FROM accounts WHERE dead_reason LIKE ? AND status = ?', ('%429%', 'LIVE')).fetchall()
print('Accounts with 429 still LIVE:', rows)
if rows:
    cur.execute('UPDATE accounts SET status=?, published_to_pool=0, dead_at=datetime("now") WHERE dead_reason LIKE ? AND status = ?', ('DEAD', '%429%', 'LIVE'))
    con.commit()
    print('Updated to DEAD successfully!')
con.close()
