# scripts/init_db.py
import sqlite3
import os

DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "shownotes.db")

# Ensure the directory exists
os.makedirs(DB_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Table: Overlap queries
c.execute('''
CREATE TABLE IF NOT EXISTS overlap_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    show1 TEXT,
    show2 TEXT,
    results_count INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

# Table: Character summaries (unified and final version)
c.execute('''
CREATE TABLE IF NOT EXISTS character_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_name TEXT,
    show_title TEXT,
    season_limit INTEGER,
    episode_limit INTEGER,
    raw_summary TEXT,
    parsed_traits TEXT,
    parsed_events TEXT,
    parsed_relationships TEXT,
    parsed_importance TEXT,
    parsed_quote TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

# Table: GPT chats or recaps
c.execute('''
CREATE TABLE IF NOT EXISTS gpt_chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input TEXT,
    response TEXT,
    context TEXT,
    type TEXT,
    user TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

conn.commit()
conn.close()
print("✅ Database initialized.")

import sqlite3
import os

os.makedirs("data", exist_ok=True)

conn = sqlite3.connect("data/shownotes.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS character_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character TEXT,
    show TEXT,
    season_limit INTEGER,
    episode_limit INTEGER,
    raw_summary TEXT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()
print("Database initialized.")