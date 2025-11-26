# app_logic.py
# 영양제 추천 서비스의 백엔드 핵심 로직을 담당하는 파일입니다.
# 사용자 프로필 관리, 맞춤 영양제 추천(이유 포함), 제품 검색 기능을 제공합니다.

import sqlite3
import json
import re

# === 설정 ===
# 사용할 데이터베이스 파일명 (database.py로 생성한 파일)
DB_FILE = 'supplements_final.db'

# ==============================================================================
# 1. 데이터베이스 관리자 클래스
# ==============================================================================
class DatabaseManager:
    """
    DB 연결 및 해제를 담당하는 컨텍스트 매니저입니다.
    with DatabaseManager() as cursor: 형태로 사용하여
    연결 누수를 방지하고 트랜잭션(커밋/롤백)을 자동으로 관리합니다.
    """
    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self.conn = None
        self.cursor = None

    def __enter__(self):
        # DB 연결을 열고 커서를 반환합니다.
        self.conn = sqlite3.connect(self.db_file)
        # 데이터를 딕셔너리처럼 컬럼명으로 접근할 수 있게 설정합니다. (row['column_name'])
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        # with 블록을 빠져나갈 때 호출됩니다.
        if self.conn:
            if exc_type:
                # 에러가 발생했으면 작업을 취소(롤백)합니다.
                self.conn.rollback()
                print(f"[DB Error] 롤백되었습니다: {exc_type}")
            else:
                # 정상적으로 끝났으면 저장(커밋)합니다.
                self.conn.commit()
            # 연결을 닫습니다.
            self.conn.close()


# ==============================================================================
# 2. 사용자 프로필 관리자 클래스 (비회원 설문 데이터 저장 담당)
# ==============================================================================
class UserProfileManager:
    """
    프론트엔드에서 받은 설문 JSON 데이터를 분석하여
    DB의 T_USER_PROFILE과 T_USER_CHOICES 테이블에 저장하는 역할을 합니다.
    """
    
    def save_survey_data(self, survey_data: dict) -> int:
        """
        설문 데이터를 저장하고 새로 생성된 비회원 user_id를 반환합니다.
        """
        # JSON 데이터에서 각 영역별 정보 추출
        profile = survey_data.get('userProfile', {})
        concerns = survey_data.get('healthConcerns', [])
        medications = survey_data.get('medications', [])
        conditions = survey_data.get('specialConditions', [])

        with DatabaseManager() as cursor:
            # --- 2-1. 기본 프로필 정보 저장 (T_USER_PROFILE) ---
            # 식습관 배열(["lack_veggies", "greasy_food"])을 콤마 문자열("lack_veggies,greasy_food")로 변환
            diet_habits_str = ",".join(profile.get('dietHabits', []))
            
            # DB 스키마에 맞춰 데이터 입력 (스트레스: 상/중/하 문자열, 수면: 1~5 정수)
            cursor.execute('''
                INSERT INTO T_USER_PROFILE (age, gender, stress_level, sleep_quality, diet_habits)
                VALUES (?, ?, ?, ?, ?)
            ''', (profile.get('age'), profile.get('gender'), profile.get('stressLevel'), profile.get('sleepQuality'), diet_habits_str))
            
            # 방금 INSERT 하면서 생성된 오토인크리먼트 ID를 가져옵니다.
            user_id = cursor.lastrowid
            print(f"[INFO] 비회원 프로필 생성 완료 (ID: {user_id})")

            # --- 2-2. 선택지 정보 저장 (T_USER_CHOICES) ---
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
                    print(f"[Warning] 알 수 없는 선택지명: {choice_name}")

            return user_id


# ==============================================================================
# 3. 추천 엔진 클래스 (핵심 로직)
# ==============================================================================
class RecommendationEngine:
    """
    저장된 사용자 ID를 받아 맞춤 영양 성분과 제품을 추천하는 핵심 엔진입니다.
    점수 계산 시 추천 이유를 함께 기록합니다.
    """
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        # ✅ [변경] 점수와 이유를 함께 저장하는 구조체
        # 형식: { ingredient_id: {'total_score': int, 'reasons': [str, str...]} }
        self.score_data = {} 
        self.filtered_ingredients = set() # 안전 문제로 제외될 성분 ID 집합
        self.user_profile = None # 사용자 프로필 정보 캐싱용

    # --- ✅ [신규 추가] 점수와 이유를 함께 기록하는 헬퍼 함수 ---
    def _add_score_with_reason(self, ingredient_id, points, reason_text):
        """특정 성분에 점수를 더하고, 그 이유를 기록합니다."""
        if not ingredient_id: return
        
        if ingredient_id not in self.score_data:
            # 처음 추가되는 성분이면 데이터 구조 초기화
            self.score_data[ingredient_id] = {'total_score': 0, 'reasons': []}
            
        self.score_data[ingredient_id]['total_score'] += points
        # 이유 텍스트에 점수 정보도 같이 보기 좋게 추가 (예: "스트레스가 심해요 (+7점)")
        full_reason = f"{reason_text} (+{points}점)"
        self.score_data[ingredient_id]['reasons'].append(full_reason)
        # print(f"   -> [점수 추가] 성분ID {ingredient_id}: {full_reason}") # 디버깅용

    def _get_ingredient_id_by_name(self, cursor, name_kor):
        """성분 한글 이름으로 ID를 찾는 헬퍼 함수"""
        cursor.execute("SELECT ingredient_id FROM T_INGREDIENT WHERE name_kor = ?", (name_kor,))
        row = cursor.fetchone()
        return row['ingredient_id'] if row else None

    def run_recommendation(self):
        """추천 프로세스 전체를 순서대로 실행합니다."""
        with DatabaseManager() as cursor:
            # 0. 사용자 프로필 정보 로드 (이후 단계에서 사용)
            cursor.execute("SELECT * FROM T_USER_PROFILE WHERE user_id = ?", (self.user_id,))
            self.user_profile = cursor.fetchone()
            if not self.user_profile:
                print(f"[Error] 사용자 ID {self.user_id}의 프로필을 찾을 수 없습니다.")
                return []

            print(f"\n--- [추천 엔진 시작] 사용자 ID: {self.user_id} ---")
            
            # Step 1: 기본 점수 계산 (사용자 고민 선택 기반)
            self.calculate_base_scores(cursor)
            
            # Step 2: 프로필 기반 가중치 조정 (스트레스, 수면, 식습관)
            self.apply_profile_adjustments(cursor)
            
            # Step 3: 안전 필터링 (약물, 임산부 등) -> 가장 중요한 단계
            self.apply_safety_filters(cursor)
            
            # Step 4: 최종 결과 생성 (제품 추천 포함) 및 로깅
            final_results = self.finalize_and_log_results(cursor)
            print("--- [추천 엔진 종료] ---")
            return final_results

    # ---------- 내부 로직 메서드들 ----------

    def calculate_base_scores(self, cursor):
        """Step 1: 기본 점수 계산 (사용자 고민 선택 기반)"""
        print("-> Step 1: 기본 점수 계산 시작")
        # ✅ [수정] group_concat을 사용하여 관련된 고민 이름을 함께 가져옵니다.
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
            # ✅ [변경] 헬퍼 함수를 사용하여 점수와 이유를 기록합니다.
            reason = f"선택한 건강 고민({row['related_concerns']})과 연관됨"
            self._add_score_with_reason(row['ingredient_id'], row['added_score'], reason)

    def apply_profile_adjustments(self, cursor):
        """Step 2: T_USER_PROFILE 데이터를 기반으로 보너스 점수(가중치)를 부여합니다."""
        print("-> Step 2: 프로필 가중치 적용 시작")
        profile = self.user_profile
        
        # --- 가중치 부여 대상 성분 ID 미리 확보 ---
        magnesium_id = self._get_ingredient_id_by_name(cursor, '마그네슘')
        theanine_id = self._get_ingredient_id_by_name(cursor, '테아닌')
        lactium_id = self._get_ingredient_id_by_name(cursor, '락티움')
        
        # 식습관 관련 성분
        vit_c_id = self._get_ingredient_id_by_name(cursor, '비타민 C')
        fiber_id = self._get_ingredient_id_by_name(cursor, '식이섬유')
        omega3_id = self._get_ingredient_id_by_name(cursor, '오메가3')
        milkthistle_id = self._get_ingredient_id_by_name(cursor, '밀크씨슬')
        potassium_id = self._get_ingredient_id_by_name(cursor, '칼륨')
        calcium_id = self._get_ingredient_id_by_name(cursor, '칼슘')

        # --- A. 스트레스 수준 (상/중/하) 가중치 ---
        stress_val = profile['stress_level']
        if stress_val == '상':
            # ✅ [변경] 헬퍼 함수를 통해 구체적인 이유를 적어줍니다.
            reason = "높은 스트레스 수준 관리가 필요해요"
            self._add_score_with_reason(magnesium_id, 7, reason)
            self._add_score_with_reason(theanine_id, 7, reason)
            print("-> [가중치] 스트레스 '상' 적용")
        elif stress_val == '중':
            reason = "스트레스 관리에 도움을 줄 수 있어요"
            self._add_score_with_reason(magnesium_id, 3, reason)
            self._add_score_with_reason(theanine_id, 3, reason)
            print("-> [가중치] 스트레스 '중' 적용")

        # --- B. 수면의 질 (1~5점 정수) 가중치 ---
        sleep_score = profile['sleep_quality']
        if sleep_score <= 2: # 1점 또는 2점 (나쁨)
            # ✅ [변경]
            self._add_score_with_reason(magnesium_id, 5, "수면의 질 개선이 시급해요")
            self._add_score_with_reason(lactium_id, 8, "수면 문제 해결을 위한 전문 성분이에요")
            print(f"-> [가중치] 수면 질 나쁨({sleep_score}점) 적용")
        elif sleep_score == 3: # 3점 (보통)
            self._add_score_with_reason(magnesium_id, 2, "편안한 잠자리에 도움을 줄 수 있어요")
            print(f"-> [가중치] 수면 질 보통({sleep_score}점) 적용")

        # --- C. 식습관 가중치 (콤마 문자열 분석) ---
        if profile['diet_habits']:
            habits = profile['diet_habits'].split(',')
            
            # 1. 채소/과일 부족
            if 'lack_veggies' in habits:
                # ✅ [변경]
                reason = "부족한 채소 섭취를 채워야 해요"
                self._add_score_with_reason(vit_c_id, 4, reason)
                self._add_score_with_reason(fiber_id, 4, reason)
                print("-> [가중치] 채소 부족 적용")
            
            # 2. 기름진 음식 선호
            if 'greasy_food' in habits:
                reason = "기름진 식습관으로 인한 혈관/간 부담 완화"
                self._add_score_with_reason(omega3_id, 4, reason)
                self._add_score_with_reason(milkthistle_id, 4, reason)
                print("-> [가중치] 기름진 음식 선호 적용")

            # 3. 인스턴트/배달 선호
            if 'instant_food' in habits:
                reason = "나트륨 배출 및 영양 불균형 해소 필요"
                self._add_score_with_reason(potassium_id, 4, reason)
                self._add_score_with_reason(calcium_id, 4, reason)
                print("-> [가중치] 인스턴트 선호 적용")

    def apply_safety_filters(self, cursor):
        """Step 3: 복용 약물 및 특이 체질 기반 안전 필터링 (T_SAFETY 활용)"""
        
        # 1. 사용자가 선택한 '약물' 및 '특이사항' 목록 가져오기
        cursor.execute('''
            SELECT us.name, us.group_name
            FROM T_USER_CHOICES uc
            JOIN T_USER_SELECTION us ON uc.selection_id = us.selection_id
            WHERE uc.user_id = ? AND us.group_name IN ('복용 약물', '특이사항') # 특이사항 그룹명 수정 반영
        ''', (self.user_id,))
        user_selections = [row['name'] for row in cursor.fetchall()]

        # 2. 필터링 대상 키워드 정의
        filter_keywords = []
        if '임산부/수유부' in user_selections: filter_keywords.append('임산부/수유부')
        if '알레르기/특이체질' in user_selections: filter_keywords.append('알레르기')
        
        drug_keywords = [
            '혈압약', '고지혈증약/콜레스테롤약', '당뇨약', '혈전 예방약/아스피린', 
            '위장약/제산제', '진통제/해열제 (장기 복용)', '항생제 (최근 복용 포함)',
            '알레르기/염증약', '경구 피임약/호르몬제', '갑상선약', '항우울제/신경정신과약'
        ]
        for selection in user_selections:
             if selection in drug_keywords:
                 filter_keywords.append('복용약 확인')
                 filter_keywords.append('의약품')
                 break
        
        if not filter_keywords: return

        print(f"-> [안전 필터] 감지된 위험 요인: {filter_keywords}")

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
        
        # 4. 점수 목록에서 필터링된 성분 제거 (수정됨)
        removed_count = 0
        for bad_id in self.filtered_ingredients:
            # ✅ [변경] score_data 딕셔너리에서 키 자체를 삭제합니다.
            if bad_id in self.score_data:
                del self.score_data[bad_id]
                removed_count += 1
        if removed_count > 0:
            print(f"-> [안전 필터] {removed_count}개 성분이 안전 문제로 추천에서 제외되었습니다.")

    # ---------- 제품 추천 및 최종 결과 관련 메서드 ----------

    def _is_safe_product(self, precautions_text):
        """
        제품의 주의사항 텍스트(precautions)를 분석하여 사용자가 섭취하기에 안전한지 판단합니다.
        """
        if not precautions_text or not self.user_profile:
            # 주의사항이 없거나 프로필 정보가 없으면 일단 안전하다고 가정합니다.
            return True 

        # 1. 알레르기 필터링
        if '알레르기' in precautions_text:
            # 사용자가 설문에서 '알레르기/특이체질'을 선택했는지 확인
            with DatabaseManager() as cursor:
                cursor.execute('''
                    SELECT 1 FROM T_USER_CHOICES uc
                    JOIN T_USER_SELECTION us ON uc.selection_id = us.selection_id
                    WHERE uc.user_id = ? AND us.name = '알레르기/특이체질'
                ''', (self.user_id,))
                if cursor.fetchone():
                    # print(f"[제품 필터] 알레르기 주의 제품 제외됨")
                    return False # 안전하지 않음

        # 2. (확장 가능) 연령대, 성별, 특정 질환 기반 필터링 로직을 여기에 추가할 수 있습니다.
        # 예: 미성년자에게 '성인용' 키워드가 포함된 제품 제외 등

        return True # 모든 필터를 통과하면 안전

    def search_safe_products(self, cursor, ingredient_name, limit=2):
        """
        추천된 성분명으로 T_PRODUCT를 검색하고, 안전 필터를 통과한 제품만 반환합니다.
        """
        # 성분명이 주원료(main_ingredients_text)나 제품명(product_name)에 포함된 제품 검색
        # 띄어쓰기 무시 검색 적용 (REPLACE 사용)
        clean_name = ingredient_name.replace(" ", "")
        search_term = f"%{clean_name}%"
        
        cursor.execute('''
            SELECT product_name, company_name, precautions, main_ingredients_text
            FROM T_PRODUCT
            WHERE REPLACE(main_ingredients_text, ' ', '') LIKE ? 
               OR REPLACE(product_name, ' ', '') LIKE ?
        ''', (search_term, search_term))
        
        safe_products = []
        for row in cursor.fetchall():
            # 각 제품에 대해 안전성 체크 수행
            if self._is_safe_product(row['precautions']):
                safe_products.append({
                    'product_name': row['product_name'],
                    'company_name': row['company_name']
                })
                # 제한된 개수만큼 찾으면 중단 (성능 고려)
                if len(safe_products) >= limit:
                    break
        return safe_products

    def finalize_and_log_results(self, cursor, top_n=3):
        """
        Step 4: 최종 점수 기준으로 상위 성분을 선정하고, 안전한 제품을 검색하여 결과를 반환합니다.
        또한, 이 추천 내역(이유 포함)을 T_REC_RESULT에 기록합니다.
        """
        # ✅ [변경] 정렬 기준이 score_data 구조체의 'total_score'가 됩니다.
        sorted_ingredients = sorted(self.score_data.items(), key=lambda x: x[1]['total_score'], reverse=True)[:top_n]
        
        final_recommendations = []
        rank = 1
        # ing_id는 성분ID, data는 {'total_score': XX, 'reasons': [...]} 형태
        for ing_id, data in sorted_ingredients:
            cursor.execute("SELECT name_kor, summary FROM T_INGREDIENT WHERE ingredient_id = ?", (ing_id,))
            ing_info = cursor.fetchone()
            
            if ing_info:
                ing_name = ing_info['name_kor']
                recommended_products = self.search_safe_products(cursor, ing_name)

                # ✅ [핵심] 이유 목록 리스트를 하나의 문자열로 합칩니다. (DB 저장용)
                reasons_str = ", ".join(data['reasons'])

                rec_item = {
                    'rank': rank,
                    'ingredient_id': ing_id,
                    'name': ing_name,
                    'summary': ing_info['summary'],
                    'score': data['total_score'],
                    'reasons': data['reasons'], # ✅ 프론트엔드에는 배열 형태로 전달 (표시하기 좋음)
                    'products': recommended_products # 안전한 제품 추천 리스트 포함
                }
                final_recommendations.append(rec_item)
                
                # ✅ [변경] DB에는 합쳐진 이유 문자열을 저장합니다.
                cursor.execute('''
                    INSERT INTO T_REC_RESULT (user_id, recommended_ingredient_id, score, recommended_reasons)
                    VALUES (?, ?, ?, ?)
                ''', (self.user_id, ing_id, data['total_score'], reasons_str))
                rank += 1
                
        return final_recommendations


# ==============================================================================
# 4. 검색 엔진 클래스 (카테고리 기반 제품 검색 담당)
# ==============================================================================
class SearchEngine:
    """
    사용자의 검색 요청(키워드 검색, 카테고리 클릭 등)을 처리합니다.
    """

    def search_products_by_category(self, category_name: str, limit=10):
        """
        카테고리명(예: '간 건강')을 받아 관련된 성분이 포함된 제품들을 검색합니다.
        limit 파라미터로 반환할 제품의 최대 개수를 지정할 수 있습니다. (기본값: 10개)
        """
        print(f"\n--- [검색 엔진] 카테고리 검색 시작: '{category_name}' (최대 {limit}개) ---")
        with DatabaseManager() as cursor:
            # 1단계: 해당 카테고리와 매핑된 '성분 한글명'들을 모두 가져옵니다.
            # T_USER_SELECTION -> T_REC_MAPPING -> T_INGREDIENT 순으로 조인
            cursor.execute('''
                SELECT i.name_kor
                FROM T_INGREDIENT i
                JOIN T_REC_MAPPING rm ON i.ingredient_id = rm.ingredient_id
                JOIN T_USER_SELECTION us ON rm.selection_id = us.selection_id
                WHERE us.name = ? AND us.group_name = '건강 고민'
            ''', (category_name,))
            
            ingredient_names = [row['name_kor'] for row in cursor.fetchall()]

            if not ingredient_names:
                print(f"[Info] '{category_name}' 카테고리에 매핑된 성분이 없습니다.")
                return []
            
            print(f"-> 연관 성분 발견: {ingredient_names}")

            # 2단계: 찾아낸 성분명들이 포함된 제품을 검색하는 동적 쿼리를 만듭니다.
            # 띄어쓰기 무시를 위해 REPLACE를 사용합니다.
            like_conditions = []
            params = []
            for name in ingredient_names:
                # 성분명 자체의 공백도 제거
                clean_name = name.replace(" ", "")
                # "REPLACE(main_ingredients_text, ' ', '') LIKE '%성분명%'" 조건 추가
                like_conditions.append("REPLACE(main_ingredients_text, ' ', '') LIKE ?")
                params.append(f"%{clean_name}%")

            # OR로 연결된 거대한 WHERE 절 완성
            where_clause = " OR ".join(like_conditions)
            
            # 최종 제품 검색 쿼리 (중복 제거 DISTINCT 사용)
            query = f'''
                SELECT DISTINCT product_id, product_name, company_name, main_ingredients_text
                FROM T_PRODUCT
                WHERE ({where_clause})
                ORDER BY random() -- 매번 다른 제품이 보이도록 랜덤 정렬
                LIMIT ?
            '''
            # 파라미터 리스트 마지막에 limit 추가
            params.append(limit)

            print(f"-> 제품 검색 쿼리 실행 중...")
            cursor.execute(query, tuple(params))
            
            # 결과 정리 및 반환
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row['product_id'],
                    'name': row['product_name'],
                    'company': row['company_name'],
                    # 원재료명은 너무 기니까 앞부분만 잘라서 보여주기 요약
                    'ingredients_summary': row['main_ingredients_text'][:100] + "..." if row['main_ingredients_text'] else ""
                })
            print(f"--- [검색 엔진] 종료 (총 {len(results)}개 제품 발견) ---")
            return results


# ==============================================================================
# 실행 테스트 (로컬 개발 환경용)
# 실제 웹 서버에서는 이 부분이 실행되지 않고 위 클래스들만 import해서 사용합니다.
# ==============================================================================
if __name__ == "__main__":
    # --- 테스트 1: 기존 추천 엔진 테스트 ---
    print(">>> [테스트 1] 추천 엔진 실행 (이유 포함 여부 확인) >>>")
    # 테스트용 더미 설문 데이터
    dummy_survey_data = {
        "userProfile": {
            "gender": "male",
            "age": 40,
            # 식습관 가중치 테스트 (기름진 음식, 인스턴트)
            "dietHabits": ["greasy_food", "instant_food"],
            "sleepQuality": 2,        # 수면 가중치 테스트 (2점=나쁨)
            "stressLevel": "중"       # 스트레스 가중치 테스트 (중)
        },
        # 건강 고민 선택 (기본 점수)
        "healthConcerns": ["간 건강", "혈압 관리"],
        # 약물 선택 (안전 필터 테스트용)
        "medications": ["해당 없음"],
        # 특이사항 선택
        "specialConditions": ["해당 없음"]
    }

    # 1. 프로필 매니저를 통해 데이터 저장
    profile_mgr = UserProfileManager()
    try:
        new_user_id = profile_mgr.save_survey_data(dummy_survey_data)
    except Exception as e:
        print(f"[Critical Error] 데이터 저장 중 오류 발생: {e}")
        exit()

    # 2. 추천 엔진 인스턴스 생성 및 실행
    engine = RecommendationEngine(new_user_id)
    recommendations = engine.run_recommendation()

    # 3. 최종 결과 출력 (프론트엔드 응답 예시 - reasons 배열 확인 필요)
    print("\n>>> [최종 추천 결과 리포트 (JSON 형식 예상)] >>>")
    # 한글 출력을 위해 ensure_ascii=False 설정
    print(json.dumps(recommendations, indent=2, ensure_ascii=False))
    print("="*40 + "\n")


    # --- 테스트 2: 신규 검색 엔진 테스트 (카테고리 클릭 시뮬레이션) ---
    print(">>> [테스트 2] 카테고리 검색 엔진 실행 ('눈 건강') >>>")
    search_engine = SearchEngine()
    # '눈 건강' 아이콘을 클릭했다고 가정 (기본 limit=10 적용)
    search_results = search_engine.search_products_by_category("눈 건강")

    if not search_results:
        print("검색 결과가 없습니다.")
    else:
        print(f"검색 결과 (총 {len(search_results)}개):")
        for item in search_results:
            print(f"[{item['company']}] {item['name']}")
            # print(f"   - 성분 요약: {item['ingredients_summary']}") # 너무 길면 주석 처리
            print("-" * 20)