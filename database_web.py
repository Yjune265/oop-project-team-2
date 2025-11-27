# models/database.py
# Flask 호환성 및 기존 로직 지원을 위한 통합 DB 모듈

import sqlite3
import os
from pathlib import Path

# =============================
# 1. 경로 및 기본 설정 (준서님 코드 반영)
# =============================
# 현재 파일(models/database.py)의 부모 폴더를 기준으로 DB 파일 경로 설정
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "supplements_final.db"

print(f"[DB Info] 데이터베이스 경로: {DB_PATH}")

def get_connection():
    """
    Flask 스타일의 함수형 DB 연결 팩토리.
    새로운 연결 객체를 생성하여 반환합니다.
    """
    conn = sqlite3.connect(DB_PATH)
    # 딕셔너리 형태로 결과를 받기 위한 설정 (필수)
    conn.row_factory = sqlite3.Row
    # 외래 키 제약 조건 활성화 (데이터 무결성 보장)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# =============================
# 2. [핵심 수정] 기존 코드 호환용 Context Manager 부활
# =============================
class DatabaseManager:
    """
    app_logic.py와 admin_logic.py에서 사용하는 'with' 문법을 지원하기 위한 래퍼(Wrapper) 클래스입니다.
    내부적으로는 위에서 정의한 get_connection() 함수를 사용합니다.
    """
    def __init__(self):
        self.conn = None
        self.cursor = None

    def __enter__(self):
        # 준서님이 만든 연결 함수를 사용하여 연결을 엽니다.
        self.conn = get_connection()
        self.cursor = self.conn.cursor()
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        # with 블록을 빠져나갈 때 트랜잭션 처리 및 연결 종료
        if self.conn:
            if exc_type:
                self.conn.rollback()
                print(f"[DB Error] 롤백되었습니다: {exc_type}")
            else:
                self.conn.commit()
            # 중요: Flask 메인 로직 외에서 실행될 경우를 대비해 여기서 닫아줍니다.
            self.conn.close()


# =============================
# 3. Flask용 헬퍼 함수 (준서님 코드 유지)
# =============================
def fetch_all(query, params=None):
    """여러 행 조회용 헬퍼"""
    # 이 함수들은 DatabaseManager를 거치지 않고 직접 연결을 열고 닫습니다.
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(query, params or [])
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        # try-finally 블록으로 안전하게 연결 종료 보장
        conn.close()

def fetch_one(query, params=None):
    """단일 행 조회용 헬퍼"""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(query, params or [])
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# =============================
# 4. 예시 함수 수정 (저의 스키마 반영)
# =============================
# 준서님 예시 코드의 테이블명(supplements)을 실제 우리 테이블명(T_PRODUCT)으로 수정
def search_supplement_by_name_example(keyword: str):
    query = """
        SELECT product_id, product_name, company_name 
        FROM T_PRODUCT
        WHERE product_name LIKE ?
        LIMIT 20
    """
    return fetch_all(query, [f"%{keyword}%"])

# 테스트 실행
if __name__ == "__main__":
    # 경로가 맞는지 확인하기 위한 간단한 테스트
    if not DB_PATH.exists():
        print(f"❌ 오류: DB 파일을 찾을 수 없습니다. 경로를 확인하세요: {DB_PATH}")
        # 팁: 데이터 수집 스크립트(database.py)를 먼저 실행해야 합니다.
    else:
        print("✅ DB 파일이 정상적으로 존재합니다.")
        # DatabaseManager 호환성 테스트
        try:
            with DatabaseManager() as cursor:
                cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table';")
                cnt = cursor.fetchone()[0]
                print(f"✅ 연결 테스트 성공! 현재 테이블 개수: {cnt}개")
        except Exception as e:
            print(f"❌ 연결 테스트 실패: {e}")