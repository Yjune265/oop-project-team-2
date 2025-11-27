# app/services/admin_logic.py (위치는 프로젝트 구조에 따라 다를 수 있음)
# 관리자(Admin) 전용 비즈니스 로직을 처리하는 계층입니다.
# 통계 조회, 사용자 데이터 삭제, 시스템 백업 등을 수행합니다.

import sqlite3
import shutil
import os
from datetime import datetime
from pathlib import Path

# ✅ 우리가 만든 하이브리드 DB 모듈에서 필요한 기능들을 가져옵니다.
# DatabaseManager: 트랜잭션(삭제 등)이 필요한 복잡한 작업용
# fetch_one, fetch_all: 간단한 조회 작업용
# DB_PATH: 백업 기능을 위해 DB 파일의 절대 경로가 필요함
from app.models.database import DatabaseManager, fetch_one, fetch_all, DB_PATH

# 백업 파일 저장 경로 설정 (DB 파일이 있는 폴더 옆에 'db_backups' 폴더 생성)
BACKUP_DIR = DB_PATH.parent / 'db_backups'


class AdminManager:
    """
    NutriGuide 관리자 기능 서비스 계층
    - 대시보드용 요약 통계 (총 사용자, 추천 현황)
    - 사용자 관리 (최근 목록 조회, 특정인 삭제, 전체 청소)
    - 시스템 관리 (DB 백업)
    """
    
    def __init__(self):
        # 실제 서비스에서는 여기서 관리자 권한 인증(Authentication) 체크 필요
        pass

    # ==========================================================================
    # A. 통계 및 현황 조회 (Dashboard Stats)
    # ==========================================================================

    def get_total_users_count(self):
        """[현황] 현재 총 누적 사용자(비회원 프로필) 수 조회"""
        # 간단한 조회이므로 fetch_one 헬퍼 함수 사용
        query = "SELECT COUNT(*) as count FROM T_USER_PROFILE"
        result = fetch_one(query)
        # 결과가 없으면 0 반환, 있으면 count 값 반환
        return result['count'] if result else 0

    def view_recommendation_stats(self, top_n=5):
        """[통계] 가장 많이 추천된 성분 Top N 조회"""
        # 복잡한 쿼리지만 조회만 하므로 fetch_all 헬퍼 함수 사용 가능
        query = """
            SELECT i.name_kor, COUNT(rr.recommended_ingredient_id) as rec_count, AVG(rr.score) as avg_score
            FROM T_REC_RESULT rr
            JOIN T_INGREDIENT i ON rr.recommended_ingredient_id = i.ingredient_id
            GROUP BY rr.recommended_ingredient_id
            ORDER BY rec_count DESC
            LIMIT ?
        """
        # fetch_all은 결과가 없으면 빈 리스트 []를 반환하므로 안전함
        return fetch_all(query, [top_n])


    # ==========================================================================
    # B. 사용자 관리 (Manage Users)
    # ==========================================================================

    def get_recent_users(self, limit=10):
        """[조회] 최근 생성된 사용자 프로필 목록 조회"""
        # 우리의 스키마(T_USER_PROFILE) 기준으로 조회
        query = """
            SELECT user_id, gender, age, stress_level, sleep_quality, created_at 
            FROM T_USER_PROFILE 
            ORDER BY created_at DESC LIMIT ?
        """
        return fetch_all(query, [limit])

    def delete_single_user(self, user_id: int):
        """
        [삭제] 특정 사용자 1명의 모든 데이터(선택정보, 추천기록, 프로필)를 삭제합니다.
        ⚠️ 여러 테이블에 걸친 삭제이므로 트랜잭션 관리가 필수입니다.
        """
        try:
            # ✅ 트랜잭션 안전성을 위해 우리가 만든 DatabaseManagerContext 사용
            with DatabaseManager() as cursor:
                # 1. 자식 테이블부터 삭제 (외래키 제약조건 고려)
                cursor.execute("DELETE FROM T_USER_CHOICES WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM T_REC_RESULT WHERE user_id = ?", (user_id,))
                
                # 2. 부모 테이블 삭제
                cursor.execute("DELETE FROM T_USER_PROFILE WHERE user_id = ?", (user_id,))
                
                if cursor.rowcount > 0:
                    # commit은 DatabaseManager가 exit 할 때 자동으로 해줌
                    return True, f"사용자 ID {user_id} 관련 모든 데이터가 삭제되었습니다."
                else:
                    return False, f"사용자 ID {user_id}를 찾을 수 없습니다."
                    
        except Exception as e:
            # error 발생 시 rollback은 DatabaseManager가 자동으로 해줌
            return False, f"삭제 중 오류 발생: {str(e)}"

    def delete_all_test_users(self):
        """
        [위험/개발용] DB에 쌓인 모든 사용자 관련 데이터를 초기화(청소)합니다.
        """
        # 실제 웹 환경에서는 이 함수를 호출하기 전에 별도의 비밀번호 확인 등 안전장치가 필요합니다.
        try:
            with DatabaseManager() as cursor:
                cursor.execute("DELETE FROM T_USER_CHOICES")
                cursor.execute("DELETE FROM T_REC_RESULT")
                cursor.execute("DELETE FROM T_USER_PROFILE")
                # SQLite 공간 반환을 위한 VACUUM (선택사항)
                # cursor.execute("VACUUM;")
                return True, "모든 테스트 사용자 데이터가 초기화되었습니다."
        except Exception as e:
            return False, f"전체 초기화 중 오류 발생: {str(e)}"


    # ==========================================================================
    # C. 시스템 관리 (System Admin)
    # ==========================================================================

    def backup_database(self):
        """[안전] 현재 DB 파일을 백업 폴더로 복사합니다."""
        if not DB_PATH.exists():
             return False, "원본 DB 파일을 찾을 수 없습니다."

        try:
            # 백업 폴더가 없으면 생성 (parents=True는 상위 폴더도 같이 생성)
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"backup_{timestamp}_{DB_PATH.name}"
            backup_path = BACKUP_DIR / backup_filename

            # 파일 복사 실행
            shutil.copy2(DB_PATH, backup_path)
            return True, f"백업 완료: {backup_path.name}"
            
        except Exception as e:
            return False, f"백업 실패: {str(e)}"

# ==============================================================================
# (참고) 영양제 수동 관리 기능(add/delete_supplement)은 
# 현재 API 자동 동기화 정책에 따라 구현하지 않습니다.
# 필요시 추후 구현 예정.
# ==============================================================================