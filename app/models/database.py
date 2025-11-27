# models/database.py
# Flask와 호환되도록 리팩토링한 SQLite DB 모듈

import sqlite3
import os
from pathlib import Path

# DB 파일 경로 설정 (현재 models 폴더에 위치)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "supplements_final.db"


# =============================
# DB 연결 생성 함수
# =============================
def get_connection():
    """
    Flask에서 import하여 DB 연결을 가져오는 함수.
    매 요청마다 새로운 connection을 반환.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # dict 형태로 row 반환
    return conn


# =============================
# 기본 SELECT 함수 (공용)
# =============================
def fetch_all(query, params=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params or [])
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def fetch_one(query, params=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params or [])
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# =============================
# 예: supplement 검색 기능
# =============================
def search_supplement_by_name(keyword: str):
    query = """
        SELECT * FROM supplements
        WHERE product_name LIKE ?
        LIMIT 20
    """
    return fetch_all(query, [f"%{keyword}%"])
