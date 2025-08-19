import mysql.connector
from mysql.connector import Error
from datetime import timedelta
from dotenv import load_dotenv
import os
from typing import Optional, Dict, Any

load_dotenv()  # يبحث عن .env في مجلد المشروع الحالي

# =========================
# Environment / Config
# =========================
db_name = os.getenv("DB_NAME")
db_host = os.getenv("DB_HOST")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_port = os.getenv("DB_PORT")
RESULTS_TABLE = "wpl3_media_plan_result"

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password,
            port=db_port
        )
        if connection.is_connected():
            print("✅ Connected!")
            return connection
    except Error as e:
        print("❌ Failed.")
        print(f"Error connecting to MySQL: {e}")
        return None

def save_result(request_id: int, user_id: int, result_text: str) -> None:
    # Assuming the 'edited_result' can be empty initially and should not be NULL
    edited_result = ""  # or some default value for 'edited_result'
    sql = f"""
    INSERT INTO `{RESULTS_TABLE}` (`request_id`, `user_id`, `result`, `edited_result`)
    VALUES (%s, %s, %s, %s)
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (request_id, user_id, result_text, edited_result))
            conn.commit()
    finally:
        conn.close()

def fetch_latest_result(request_id: int) -> Optional[Dict[str, Any]]:
    """
    Return the most recent result for a given request_id, or None.
    """
    sql = f"""
    SELECT request_id, user_id, result, edited_result, date
    FROM `{RESULTS_TABLE}`
    WHERE request_id = %s
    ORDER BY date DESC, id DESC
    LIMIT 1
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (request_id,))
            row = cur.fetchone()  # Fetch the first row
            cur.fetchall()  # Consume any remaining results
            return row
    finally:
        conn.close()  # Close the connection after fetching results

