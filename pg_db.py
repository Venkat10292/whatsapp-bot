import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")

def connect():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS authorized_users (
            mobile TEXT PRIMARY KEY,
            email TEXT,
            longname TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_user(mobile, email, longname):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO authorized_users (mobile, email, longname)
        VALUES (%s, %s, %s)
        ON CONFLICT (mobile) DO NOTHING
    """, (mobile, email, longname))
    conn.commit()
    conn.close()

def is_user_authorized(mobile):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM authorized_users WHERE mobile = %s", (mobile,))
    result = cursor.fetchone()
    conn.close()
    return result is not None
