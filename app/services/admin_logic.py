# admin_logic.py
# 관리자(Admin) 전용 기능을 제공하는 파일입니다.
# 통계 조회, 사용자 데이터 관리(삭제), 시스템 백업 등을 수행합니다.
# ⚠️ 주의: 이 파일의 기능은 신중하게 사용해야 합니다.

import sqlite3
import shutil
import os
from datetime import datetime

# === 설정 ===
# 관리 대상 데이터베이스 파일 (app_logic.py와 동일한 파일)
DB_FILE = 'supplements_final.db'
# 백업 파일 저장 경로
BACKUP_DIR = 'db_backups'

# ==============================================================================
# 1. 데이터베이스 관리자 클래스 (app_logic.py와 동일한 클래스 재사용)
# ==============================================================================
class DatabaseManager:
    """DB 연결 컨텍스트 매니저"""
    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self.conn = None; self.cursor = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_file)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        # 외래 키 제약 조건 활성화 (데이터 무결성 보장)
        self.cursor.execute("PRAGMA foreign_keys = ON;")
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type: self.conn.rollback(); print(f"[DB Error] 롤백: {exc_type}")
            else: self.conn.commit()
            self.conn.close()


# ==============================================================================
# 2. 관리자 기능 매니저 클래스 (핵심 로직)
# ==============================================================================
class AdminManager:
    """
    관리자 전용 기능을 제공하는 클래스입니다.
    통계 조회, 사용자 관리, DB 백업, 추천 규칙 수정 등을 수행합니다.
    """
    
    def __init__(self):
        # 실제 서비스에서는 여기서 관리자 권한 인증(Authentication)을 수행해야 합니다.
        print("[AdminManager] 관리자 모드 도구 로드됨.")

    # ---------- A. 통계 및 현황 조회 (View Statistics) ----------
    
    def view_recommendation_stats(self, top_n=5):
        """[통계] 가장 많이 추천된 성분 Top N 조회 (T_REC_RESULT 분석)"""
        print(f"\n📊 --- [관리자 통계] 최다 추천 성분 Top {top_n} ---")
        with DatabaseManager() as cursor:
            cursor.execute(f'''
                SELECT i.name_kor, COUNT(rr.recommended_ingredient_id) as rec_count, AVG(rr.score) as avg_score
                FROM T_REC_RESULT rr
                JOIN T_INGREDIENT i ON rr.recommended_ingredient_id = i.ingredient_id
                GROUP BY rr.recommended_ingredient_id
                ORDER BY rec_count DESC
                LIMIT ?
            ''', (top_n,))
            
            rows = cursor.fetchall()
            if not rows:
                print("아직 추천 기록이 없습니다.")
                return []

            results = []
            for i, row in enumerate(rows, 1):
                print(f"{i}. {row['name_kor']} (총 {row['rec_count']}회 추천, 평균 {row['avg_score']:.1f}점)")
                results.append(dict(row))
            return results

    def get_total_users_count(self):
        """[현황] 현재 총 누적 사용자(비회원 프로필) 수 조회"""
        with DatabaseManager() as cursor:
            cursor.execute("SELECT COUNT(*) FROM T_USER_PROFILE")
            count = cursor.fetchone()[0]
            print(f"👥 현재 총 누적 사용자 프로필 수: {count}명")
            return count


    # ---------- B. 사용자 관리 (Manage Users) ----------

    def get_recent_users(self, limit=10):
        """최근 생성된 사용자 프로필 목록 조회"""
        print(f"\n📋 --- [관리자] 최근 사용자 목록 (최대 {limit}명) ---")
        with DatabaseManager() as cursor:
            cursor.execute(f'''
                SELECT user_id, gender, age, stress_level, sleep_quality, created_at 
                FROM T_USER_PROFILE 
                ORDER BY created_at DESC LIMIT ?
            ''', (limit,))
            rows = [dict(row) for row in cursor.fetchall()]
            for row in rows: print(row)
            return rows

    def delete_single_user(self, user_id):
        """[위험] 특정 사용자 1명의 모든 데이터를 삭제합니다."""
        print(f"\n🗑️ --- [관리자] 사용자 ID {user_id} 데이터 삭제 시도 ---")
        try:
            with DatabaseManager() as cursor:
                cursor.execute("DELETE FROM T_USER_CHOICES WHERE user_id = ?", (user_id,))
                choices_deleted = cursor.rowcount
                cursor.execute("DELETE FROM T_REC_RESULT WHERE user_id = ?", (user_id,))
                results_deleted = cursor.rowcount
                cursor.execute("DELETE FROM T_USER_PROFILE WHERE user_id = ?", (user_id,))
                profile_deleted = cursor.rowcount

                if profile_deleted > 0:
                    print(f"✅ 사용자 ID {user_id} 삭제 완료 (프로필:1, 선택:{choices_deleted}, 기록:{results_deleted})")
                    return True
                else:
                    print(f"⚠️ 사용자 ID {user_id}를 찾을 수 없습니다.")
                    return False
        except Exception as e:
            print(f"❌ 삭제 중 오류 발생: {e}")
            return False

    # ✅ [신규 추가] 모든 테스트 사용자 데이터 삭제 기능
    def delete_all_test_users(self):
        """
        [매우 위험] DB에 쌓인 모든 사용자 관련 데이터(프로필, 선택, 추천기록)를 삭제합니다.
        개발 및 테스트 단계에서 쌓인 더미 데이터를 초기화할 때 사용합니다.
        API로 수집한 원료, 제품 정보는 안전합니다.
        """
        print(f"\n🧨 --- [관리자] 모든 사용자 데이터 초기화(청소) 시작 ---")
        print("⚠️ 경고: 이 작업은 되돌릴 수 없습니다. T_USER_PROFILE, T_USER_CHOICES, T_REC_RESULT 테이블이 모두 비워집니다.")
        
        # 안전을 위한 재확인 절차
        confirm = input("정말로 모든 사용자 데이터를 삭제하시겠습니까? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("작업이 취소되었습니다.")
            return False

        try:
            with DatabaseManager() as cursor:
                # 삭제 순서 중요 (자식 테이블 -> 부모 테이블)
                print("1. 사용자 선택 정보(T_USER_CHOICES) 삭제 중...")
                cursor.execute("DELETE FROM T_USER_CHOICES")
                rows_choices = cursor.rowcount
                
                print("2. 추천 결과 로그(T_REC_RESULT) 삭제 중...")
                cursor.execute("DELETE FROM T_REC_RESULT")
                rows_result = cursor.rowcount
                
                print("3. 사용자 프로필(T_USER_PROFILE) 삭제 중...")
                cursor.execute("DELETE FROM T_USER_PROFILE")
                rows_profile = cursor.rowcount

                print(f"\n✨ 청소 완료! 총 삭제된 행: 선택({rows_choices}), 결과({rows_result}), 프로필({rows_profile})")
                # VACUUM 명령어로 DB 파일 크기 최적화 (선택 사항)
                # cursor.execute("VACUUM;") 
                # print("DB 파일 최적화 완료.")
                return True

        except Exception as e:
            print(f"❌ 전체 삭제 중 오류 발생: {e}")
            return False


    # ---------- C. 시스템 관리 및 백업 (System & Backup) ----------

    def backup_database(self):
        """[안전] 현재 데이터베이스 파일을 백업 폴더로 복사합니다."""
        print("\n💾 --- [관리자] DB 백업 시작 ---")
        if not os.path.exists(DB_FILE):
            print(f"❌ 오류: 원본 DB 파일({DB_FILE})이 없습니다.")
            return False

        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
            print(f"백업 폴더({BACKUP_DIR})를 생성했습니다.")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}_{DB_FILE}"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)

        try:
            shutil.copy2(DB_FILE, backup_path)
            print(f"✅ 백업 성공! 저장 위치: {backup_path}")
            return True
        except Exception as e:
            print(f"❌ 백업 실패: {e}")
            return False


    # ---------- D. 추천 기준 관리 (Manage Criteria) ----------
    
    def _get_id_by_name(self, cursor, table, column, name):
        """이름으로 ID를 찾는 내부 헬퍼 함수"""
        cursor.execute(f"SELECT {table}_id FROM {table} WHERE {column} = ?", (name,))
        row = cursor.fetchone()
        return row[0] if row else None

    def manage_recommendation_mapping(self, action, selection_name, ingredient_name):
        """[고급] 추천 매핑 규칙 추가/삭제 (기존 코드와 동일)"""
        print(f"\n🔧 --- [관리자] 매핑 규칙 {action.upper()}: '{selection_name}' <-> '{ingredient_name}' ---")
        # ... (지면 관계상 기존 구현 내용 생략, 기능은 유지됨) ...
        # 필요시 이전 admin_logic.py의 이 부분을 복사해서 사용하세요.
        print("⚠️ (이 기능은 현재 코드에서 생략되었습니다. 이전 코드를 참고하세요.)")
        return False


# ==============================================================================
# 실행 테스트 (관리자 기능 테스트용)
# ==============================================================================
if __name__ == "__main__":
    admin = AdminManager()

    # 1. 현재 사용자 수 확인
    admin.get_total_users_count()

    # ✅ 2. 테스트 데이터 전체 삭제 실행
    # 이 함수를 실행하면 터미널에서 'yes'를 입력해야 삭제가 진행됩니다.
    admin.delete_all_test_users()

    # 3. 삭제 후 사용자 수 재확인 (0명이 나와야 정상)
    admin.get_total_users_count()