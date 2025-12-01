# app/services/app_logic.py (위치는 프로젝트 구조에 따라 다를 수 있음)
# 원래 app_logic_web.py
# 영양제 추천 서비스의 백엔드 핵심 비즈니스 로직을 담당하는 파일입니다.
# 사용자 프로필 관리, 맞춤 영양제 추천(이유 포함, 안전 필터링), 제품 검색 기능을 제공합니다.

import json
import re
from pathlib import Path

# ✅ 우리가 만든 하이브리드 DB 모듈에서 필요한 기능들을 가져옵니다.
# DatabaseManager: 트랜잭션이 필요한 복잡한 로직(설문 저장, 추천 실행)용
# fetch_one, fetch_all: 간단한 조회 작업용 (검색 엔진 등에서 활용 가능)
from app.models.database import DatabaseManager, fetch_one, fetch_all


# ==============================================================================
# 1. 사용자 프로필 관리자 클래스 (비회원 설문 데이터 저장 담당)
# ==============================================================================
class UserProfileManager:
    """
    프론트엔드에서 받은 설문 JSON 데이터를 분석하여
    DB의 T_USER_PROFILE과 T_USER_CHOICES 테이블에 저장하고 비회원 ID를 발급합니다.
    """
    
    def save_survey_data(self, survey_data: dict) -> int:
        """
        설문 데이터를 저장하고 새로 생성된 비회원 user_id를 반환합니다.
        팀원 코드의 단순한 구조 대신, 우리의 실제 데이터 구조를 처리합니다.
        """
        # JSON 데이터에서 각 영역별 정보 추출
        profile = survey_data.get('userProfile', {})
        concerns = survey_data.get('healthConcerns', [])
        medications = survey_data.get('medications', [])
        conditions = survey_data.get('specialConditions', [])

        # 트랜잭션 안전성을 위해 DatabaseManager 사용
        with DatabaseManager() as cursor:
            # --- A. 기본 프로필 정보 저장 (T_USER_PROFILE) ---
            # 식습관 배열(["lack_veggies", "greasy_food"])을 콤마 문자열("lack_veggies,greasy_food")로 변환
            diet_habits_str = ",".join(profile.get('dietHabits', []))
            
            # DB 스키마에 맞춰 데이터 입력
            cursor.execute('''
                INSERT INTO T_USER_PROFILE (age, gender, stress_level, sleep_quality, diet_habits)
                VALUES (?, ?, ?, ?, ?)
            ''', (profile.get('age'), profile.get('gender'), profile.get('stressLevel'), profile.get('sleepQuality'), diet_habits_str))
            
            # 방금 INSERT 하면서 생성된 오토인크리먼트 ID를 가져옵니다.
            user_id = cursor.lastrowid
            # print(f"[INFO] 비회원 프로필 생성 완료 (ID: {user_id})") # 디버깅용

            # --- B. 선택지 정보 저장 (T_USER_CHOICES) ---
            # 건강 고민, 약물, 특이사항을 모두 합쳐서 처리합니다.
            all_choices = concerns + medications + conditions
            
            for choice_name in all_choices:
                # '해당 없음'은 실제 선택 데이터로 저장하지 않습니다.
                if choice_name == '해당 없음' or not choice_name: continue

                # T_USER_SELECTION 테이블에서 해당 선택지의 ID를 찾습니다.
                cursor.execute("SELECT selection_id FROM T_USER_SELECTION WHERE name = ?", (choice_name,))
                row = cursor.fetchone()
                if row:
                    selection_id = row['selection_id']
                    # 사용자와 선택지를 연결하여 저장합니다.
                    cursor.execute("INSERT INTO T_USER_CHOICES (user_id, selection_id) VALUES (?, ?)", (user_id, selection_id))
                else:
                    pass # print(f"[Warning] 알 수 없는 선택지명: {choice_name}")

            # with 블록 종료 시 자동 커밋됨
            return user_id


# ==============================================================================
# 2. 추천 엔진 클래스 (핵심 로직 - 우리의 정교한 알고리즘 이식)
# ==============================================================================
class RecommendationEngine:
    """
    저장된 사용자 ID를 받아 맞춤 영양 성분과 제품을 추천하는 핵심 엔진입니다.
    점수 계산, 프로필 가중치, **안전 필터링**, 추천 이유 기록을 모두 수행합니다.
    팀원 코드의 단순 키워드 검색 방식과는 완전히 다른 고도화된 로직입니다.
    """
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        # 점수와 이유를 함께 저장하는 구조체
        # 형식: { ingredient_id: {'total_score': int, 'reasons': [str, str...]} }
        self.score_data = {} 
        self.filtered_ingredients = set() # 안전 문제로 제외될 성분 ID 집합
        self.user_profile = None # 사용자 프로필 정보 캐싱용

    # --- 헬퍼 함수들 ---
    def _add_score_with_reason(self, ingredient_id, points, reason_text):
        """특정 성분에 점수를 더하고, 그 이유를 기록합니다."""
        if not ingredient_id: return
        if ingredient_id not in self.score_data:
            self.score_data[ingredient_id] = {'total_score': 0, 'reasons': []}
        self.score_data[ingredient_id]['total_score'] += points
        full_reason = f"{reason_text} (+{points}점)"
        self.score_data[ingredient_id]['reasons'].append(full_reason)

    def _get_ingredient_id_by_name(self, cursor, name_kor):
        """성분 한글 이름으로 ID를 찾는 헬퍼 함수"""
        cursor.execute("SELECT ingredient_id FROM T_INGREDIENT WHERE name_kor = ?", (name_kor,))
        row = cursor.fetchone()
        return row['ingredient_id'] if row else None

    # --- 메인 실행 메서드 ---
    def run_recommendation(self):
        """추천 프로세스 전체를 순서대로 실행합니다."""
        # 복잡한 로직이므로 DatabaseManager 컨텍스트 사용
        with DatabaseManager() as cursor:
            # 0. 사용자 프로필 정보 로드
            cursor.execute("SELECT * FROM T_USER_PROFILE WHERE user_id = ?", (self.user_id,))
            self.user_profile = cursor.fetchone()
            if not self.user_profile:
                return {"error": f"사용자 ID {self.user_id}의 프로필을 찾을 수 없습니다."}

            # Step 1: 기본 점수 계산 (사용자 고민 선택 기반)
            self.calculate_base_scores(cursor)
            
            # Step 2: 프로필 기반 가중치 조정 (스트레스, 수면, 식습관)
            self.apply_profile_adjustments(cursor)
            
            # Step 3: 안전 필터링 (약물, 임산부 등) -> 핵심 기능!
            self.apply_safety_filters(cursor)
            
            # Step 4: 최종 결과 생성 (제품 추천 포함) 및 로깅
            final_results = self.finalize_and_log_results(cursor)
            
            return {
                "user_id": self.user_id,
                "recommendations": final_results
            }

    # ---------- 내부 로직 메서드들 (우리의 원본 코드 유지) ----------

    def calculate_base_scores(self, cursor):
        """Step 1: 기본 점수 계산 (사용자 고민 선택 기반)"""
        # group_concat을 사용하여 관련된 고민 이름을 함께 가져옵니다.
        query = '''
            SELECT rm.ingredient_id, SUM(rm.base_score) as added_score, group_concat(us.name) as related_concerns
            FROM T_USER_CHOICES uc
            JOIN T_REC_MAPPING rm ON uc.selection_id = rm.selection_id
            JOIN T_USER_SELECTION us ON uc.selection_id = us.selection_id
            WHERE uc.user_id = ?
            GROUP BY rm.ingredient_id
        '''
        cursor.execute(query, (self.user_id,))
        for row in cursor.fetchall():
            reason = f"선택한 건강 고민({row['related_concerns']})과 연관됨"
            self._add_score_with_reason(row['ingredient_id'], row['added_score'], reason)

    def apply_profile_adjustments(self, cursor):
        """Step 2: T_USER_PROFILE 데이터를 기반으로 보너스 점수(가중치)를 부여합니다."""
        profile = self.user_profile
        
        # --- 성분 ID 확보 ---
        magnesium_id = self._get_ingredient_id_by_name(cursor, '마그네슘')
        theanine_id = self._get_ingredient_id_by_name(cursor, '테아닌')
        lactium_id = self._get_ingredient_id_by_name(cursor, '락티움')
        vit_c_id = self._get_ingredient_id_by_name(cursor, '비타민 C')
        fiber_id = self._get_ingredient_id_by_name(cursor, '식이섬유')
        omega3_id = self._get_ingredient_id_by_name(cursor, '오메가3')
        milkthistle_id = self._get_ingredient_id_by_name(cursor, '밀크씨슬')
        potassium_id = self._get_ingredient_id_by_name(cursor, '칼륨')
        calcium_id = self._get_ingredient_id_by_name(cursor, '칼슘')

        # --- A. 스트레스 수준 ---
        stress_val = profile['stress_level']
        if stress_val == '상':
            reason = "높은 스트레스 수준 관리가 필요해요"
            self._add_score_with_reason(magnesium_id, 7, reason)
            self._add_score_with_reason(theanine_id, 7, reason)
        elif stress_val == '중':
            reason = "스트레스 관리에 도움을 줄 수 있어요"
            self._add_score_with_reason(magnesium_id, 3, reason)
            self._add_score_with_reason(theanine_id, 3, reason)

        # --- B. 수면의 질 ---
        sleep_score = profile['sleep_quality']
        if sleep_score <= 2:
            self._add_score_with_reason(magnesium_id, 5, "수면의 질 개선이 시급해요")
            self._add_score_with_reason(lactium_id, 8, "수면 문제 해결을 위한 전문 성분이에요")
        elif sleep_score == 3:
            self._add_score_with_reason(magnesium_id, 2, "편안한 잠자리에 도움을 줄 수 있어요")

        # --- C. 식습관 ---
        if profile['diet_habits']:
            habits = profile['diet_habits'].split(',')
            if 'lack_veggies' in habits:
                reason = "부족한 채소 섭취를 채워야 해요"
                self._add_score_with_reason(vit_c_id, 4, reason)
                self._add_score_with_reason(fiber_id, 4, reason)
            if 'greasy_food' in habits:
                reason = "기름진 식습관으로 인한 혈관/간 부담 완화"
                self._add_score_with_reason(omega3_id, 4, reason)
                self._add_score_with_reason(milkthistle_id, 4, reason)
            if 'instant_food' in habits:
                reason = "나트륨 배출 및 영양 불균형 해소 필요"
                self._add_score_with_reason(potassium_id, 4, reason)
                self._add_score_with_reason(calcium_id, 4, reason)

    def apply_safety_filters(self, cursor):
        """Step 3: 복용 약물 및 특이 체질 기반 안전 필터링 (T_SAFETY 활용)"""
        
        # 1. 사용자가 선택한 '약물' 및 '특이사항' 목록 가져오기
        cursor.execute('''
            SELECT us.name, us.group_name
            FROM T_USER_CHOICES uc
            JOIN T_USER_SELECTION us ON uc.selection_id = us.selection_id
            WHERE uc.user_id = ? AND us.group_name IN ('복용 약물', '특이사항')
        ''', (self.user_id,))
        user_selections = [row['name'] for row in cursor.fetchall()]

        # 2. 필터링 대상 키워드 정의
        filter_keywords = []
        if '임산부/수유부' in user_selections: filter_keywords.append('임산부/수유부')
        if '알레르기/특이체질' in user_selections: filter_keywords.append('알레르기')
        
        drug_keywords = ['혈압약', '고지혈증약/콜레스테롤약', '당뇨약', '혈전 예방약/아스피린', '위장약/제산제', '진통제/해열제 (장기 복용)', '항생제 (최근 복용 포함)', '알레르기/염증약', '경구 피임약/호르몬제', '갑상선약', '항우울제/신경정신과약']
        for selection in user_selections:
             if selection in drug_keywords:
                 filter_keywords.append('복용약 확인')
                 filter_keywords.append('의약품')
                 break
        
        if not filter_keywords: return

        # 3. T_SAFETY 테이블에서 해당 키워드에 걸리는 성분 ID 조회
        placeholders = ','.join(['?'] * len(filter_keywords))
        query = f'''
            SELECT DISTINCT ingredient_id 
            FROM T_SAFETY 
            WHERE target_name IN ({placeholders})
        '''
        cursor.execute(query, tuple(filter_keywords))
        for row in cursor.fetchall():
            self.filtered_ingredients.add(row['ingredient_id'])
        
        # 4. 점수 목록에서 필터링된 성분 제거
        for bad_id in self.filtered_ingredients:
            if bad_id in self.score_data:
                del self.score_data[bad_id] # 핵심: 아예 삭제

    # ---------- 제품 추천 및 최종 결과 관련 메서드 ----------

    def _is_safe_product(self, cursor, precautions_text):
        """제품 주의사항 텍스트 분석 및 안전성 판단"""
        if not precautions_text or not self.user_profile:
            return True 

        # 1. 알레르기 필터링
        if '알레르기' in precautions_text:
            # 같은 커서(트랜잭션)를 사용하여 조회
            cursor.execute('''
                SELECT 1 FROM T_USER_CHOICES uc
                JOIN T_USER_SELECTION us ON uc.selection_id = us.selection_id
                WHERE uc.user_id = ? AND us.name = '알레르기/특이체질'
            ''', (self.user_id,))
            if cursor.fetchone():
                return False # 안전하지 않음

        return True # 안전

    def search_safe_products(self, cursor, ingredient_name, limit=2):
        """성분명으로 제품 검색 후 안전 필터링 적용"""
        clean_name = ingredient_name.replace(" ", "")
        search_term = f"%{clean_name}%"
        
        cursor.execute('''
            SELECT product_name, company_name, precautions, main_ingredients_text
            FROM T_PRODUCT
            WHERE REPLACE(main_ingredients_text, ' ', '') LIKE ? 
               OR REPLACE(product_name, ' ', '') LIKE ?
            ORDER BY random() -- 랜덤하게 다양한 제품 노출
        ''', (search_term, search_term))
        
        safe_products = []
        for row in cursor.fetchall():
            if self._is_safe_product(cursor, row['precautions']):
                safe_products.append({
                    'product_name': row['product_name'],
                    'company_name': row['company_name']
                })
                if len(safe_products) >= limit:
                    break
        return safe_products

    def finalize_and_log_results(self, cursor, top_n=3):
        """Step 4: 최종 결과 생성 및 DB 로깅"""
        # 점수 내림차순 정렬
        sorted_ingredients = sorted(self.score_data.items(), key=lambda x: x[1]['total_score'], reverse=True)[:top_n]
        
        final_recommendations = []
        rank = 1
        for ing_id, data in sorted_ingredients:
            cursor.execute("SELECT name_kor, summary FROM T_INGREDIENT WHERE ingredient_id = ?", (ing_id,))
            ing_info = cursor.fetchone()
            
            if ing_info:
                ing_name = ing_info['name_kor']
                # 안전한 제품 검색
                recommended_products = self.search_safe_products(cursor, ing_name)

                # 이유 목록 문자열로 합치기 (DB 저장용)
                reasons_str = ", ".join(data['reasons'])

                rec_item = {
                    'rank': rank,
                    'ingredient_id': ing_id,
                    'name': ing_name,
                    'summary': ing_info['summary'],
                    'score': data['total_score'],
                    'reasons': data['reasons'], # 프론트엔드용 배열
                    'products': recommended_products
                }
                final_recommendations.append(rec_item)
                
                # DB에 추천 결과 로그 저장
                cursor.execute('''
                    INSERT INTO T_REC_RESULT (user_id, recommended_ingredient_id, score, recommended_reasons)
                    VALUES (?, ?, ?, ?)
                ''', (self.user_id, ing_id, data['total_score'], reasons_str))
                rank += 1
                
        return final_recommendations


# ==============================================================================
# 3. 검색 엔진 클래스 (카테고리 기반 제품 검색 및 상세 조회 담당)
# ==============================================================================
class SearchEngine:
    """
    사용자의 검색 요청(카테고리 클릭, 제품 상세 조회)을 처리합니다.
    팀원 코드에는 아예 없던 클래스입니다.
    """

    def search_products_by_category(self, category_name: str, limit=10):
        """
        카테고리명(예: '간 건강')을 받아 관련된 성분이 포함된 제품들을 검색합니다.
        복잡한 조인이 필요하므로 DatabaseManager를 사용합니다.
        """
        with DatabaseManager() as cursor:
            # 1단계: 연관 성분명 가져오기
            cursor.execute('''
                SELECT i.name_kor
                FROM T_INGREDIENT i
                JOIN T_REC_MAPPING rm ON i.ingredient_id = rm.ingredient_id
                JOIN T_USER_SELECTION us ON rm.selection_id = us.selection_id
                WHERE us.name = ? AND us.group_name = '건강 고민'
            ''', (category_name,))
            
            ingredient_names = [row['name_kor'] for row in cursor.fetchall()]

            if not ingredient_names:
                return []
            
            # 2단계: 동적 쿼리로 제품 검색
            like_conditions = []
            params = []
            for name in ingredient_names:
                clean_name = name.replace(" ", "")
                like_conditions.append("REPLACE(main_ingredients_text, ' ', '') LIKE ?")
                params.append(f"%{clean_name}%")

            where_clause = " OR ".join(like_conditions)
            query = f'''
                SELECT DISTINCT product_id, product_name, company_name, main_ingredients_text
                FROM T_PRODUCT
                WHERE ({where_clause})
                ORDER BY random()
                LIMIT ?
            '''
            params.append(limit)
            cursor.execute(query, tuple(params))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row['product_id'],
                    'name': row['product_name'],
                    'company': row['company_name'],
                    'ingredients_summary': row['main_ingredients_text'][:100] + "..." if row['main_ingredients_text'] else ""
                })
            return results

    def get_product_detail(self, product_id: int):
        """
        특정 제품 ID에 해당하는 상세 정보를 모두 조회합니다.
        간단한 단일 행 조회이므로 fetch_one 헬퍼 함수를 사용할 수 있습니다.
        """
        # 우리의 실제 테이블 T_PRODUCT 사용
        query = "SELECT * FROM T_PRODUCT WHERE product_id = ?"
        row = fetch_one(query, [product_id])
        
        if row:
            return dict(row) # 모든 컬럼 정보 반환
        else:
            return None

# (테스트 코드는 Flask 환경에서는 필요 없으므로 제거했습니다.)