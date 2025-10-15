# activity_db.py
import sqlite3

DATABASE = 'mindfulme.db'

def init_db():
    """Initializes the SQLite database and creates the activity log and habits tables."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Table to store user-logged activities (what they completed)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            category TEXT,
            status TEXT
        )
    ''')

    # Table to store user-defined recurring habits (what they intend to do)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            frequency TEXT NOT NULL -- e.g., 'daily'
        )
    ''')

    conn.commit()
    conn.close()
    print(f"Database '{DATABASE}' initialized with 'activities' and 'habits' tables.")

if __name__ == '__main__':
    init_db()