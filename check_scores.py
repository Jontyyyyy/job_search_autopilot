import sqlite3

conn = sqlite3.connect('data/job_autopilot.db')
conn.row_factory = sqlite3.Row
rows = conn.execute(
    'SELECT title, company_name, match_score FROM jobs '
    'WHERE match_score IS NOT NULL ORDER BY match_score DESC LIMIT 10'
).fetchall()
for r in rows:
    print(f"{r['match_score']:.0f}  {r['title'][:50]:50}  {r['company_name']}")