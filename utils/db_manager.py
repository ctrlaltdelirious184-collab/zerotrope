import sqlite3
from datetime import datetime
import os

DB_PATH = os.path.join(os.getcwd(), "knowledge", "leads.db")

class LeadDatabase:
    def __init__(self):
        # Ensure knowledge dir exists
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP,
                business_input TEXT,
                unique_angle TEXT,
                status TEXT
            )
        """)
        conn.commit()
        conn.close()

    def save_lead(self, job_id, business_input, unique_angle):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO leads (id, created_at, business_input, unique_angle, status)
            VALUES (?, ?, ?, ?, ?)
        """, (job_id, datetime.now(), business_input, unique_angle, "completed"))
        conn.commit()
        conn.close()

    def get_all_leads(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads ORDER BY created_at DESC")
        leads = cursor.fetchall()
        conn.close()
        return leads
