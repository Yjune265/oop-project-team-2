# 관리자 기능 (MVP 버전): 사용자 조회, 사용자 삭제, 영양제 DB 관리(추가, 삭제)

from app.models.database import fetch_all, fetch_one, get_connection


class AdminManager:
    """
    NutriGuide 관리자 기능 서비스 계층 (MVP 버전)
    - 사용자 목록 조회
    - 사용자 정보 삭제
    - 영양제 DB( supplements 테이블 ) 관리
    """

    # ================================
    # 1) 전체 사용자 목록 조회
    # ================================
    def list_all_users(self):
        query = "SELECT id, email, created_at FROM users ORDER BY id DESC"
        return fetch_all(query)

    # ================================
    # 2) 특정 사용자 조회
    # ================================
    def get_user(self, user_id: int):
        query = "SELECT * FROM users WHERE id = ?"
        return fetch_one(query, [user_id])

    # ================================
    # 3) 특정 사용자 삭제
    # ================================
    def delete_single_user(self, user_id: int):
        conn = get_connection()
        cur = conn.cursor()

        # 존재 확인
        user = fetch_one("SELECT * FROM users WHERE id = ?", [user_id])
        if not user:
            return False

        cur.execute("DELETE FROM users WHERE id = ?", [user_id])
        conn.commit()
        conn.close()
        return True

    # ================================
    # 4) 영양제 추가 (관리자)
    # ================================
    def add_supplement(self, product_name: str, company: str, ingredients: str):
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO supplements (product_name, company, ingredients)
            VALUES (?, ?, ?)
            """,
            [product_name, company, ingredients]
        )

        conn.commit()
        conn.close()
        return True

    # ================================
    # 5) 영양제 삭제 (관리자)
    # ================================
    def delete_supplement(self, supplement_id: int):
        conn = get_connection()
        cur = conn.cursor()

        exists = fetch_one("SELECT * FROM supplements WHERE id = ?", [supplement_id])
        if not exists:
            return False

        cur.execute("DELETE FROM supplements WHERE id = ?", [supplement_id])
        conn.commit()
        conn.close()
        return True
