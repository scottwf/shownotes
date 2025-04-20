# app/db.py

import sqlite3
import os

DB_PATH = os.path.join("data", "shownotes.db")

def log_overlap_query(show1, show2, result_count):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO overlap_queries (show1, show2, results_count) VALUES (?, ?, ?)",
            (show1, show2, result_count)
        )
        conn.commit()
        conn.close()
        print(f"✅ Logged overlap query: {show1} vs {show2} ({result_count} matches)")
    except Exception as e:
        print(f"❌ Failed to log overlap query: {e}")