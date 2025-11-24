import sqlite3
import requests
import re
import os
import time

DB_FILE = 'supplements_final.db'
API_KEY = "5867d3cf82cb40f7b3e1"  # 사용자 제공 키

# === 동의어 사전 (매핑 정확도 향상용) ===
# 사용자 선택지 이름(Key)과 API 텍스트에서 찾을 실제 키워드 리스트(Value) 매핑
SYNONYM_DICT = {
    # --- 그룹 1: 건강 관리 ---
    '피로/활력': ['피로', '활력', '에너지', '지구력', '운동수행능력'],
    '간 건강': ['간 건강', '간기능', '알콜', '숙취'],
    '다이어트/체지방': ['체지방', '다이어트', '체중', '비만'],
    '혈액순환/콜레스테롤': ['혈행', '콜레스테롤', '중성지질', '혈액', '혈전'],
    '혈당 관리': ['혈당', '당뇨', '인슐린'],
    '혈압 관리': ['혈압', '고혈압'],

    # --- 그룹 2: 신체 부위 ---
    '눈 건강': ['눈 건강', '시력', '황반', '수정체', '안구건조'],
    '뼈/관절/근육': ['뼈', '관절', '근력', '골다공증', '연골', '칼슘 흡수'],
    '위/소화': ['위 점막', '소화', '속쓰림', '헬리코박터'],
    '장 건강/변비': ['장 건강', '배변', '유산균', '프로바이오틱스', '변비', '장내균총'],
    '피부': ['피부', '자외선', '보습', '주름', '탄력'],
    '모발/두피/손톱': ['모발', '두피', '손톱', '단백질 대사'],
    '구강 관리': ['구강', '치아', '잇몸', '충치'],

    # --- 그룹 3: 일상/정신 ---
    '면역력/알러지': ['면역', '알레르기', '과민반응'],
    '수면 질 개선': ['수면', '잠', '스트레스 호르몬'],
    '스트레스/마음건강': ['스트레스', '긴장', '불안', '마음'],
    '기억력/인지력': ['기억력', '인지', '두뇌', '뇌세포'],
    '항노화/항산화': ['항산화', '활성산소', '노화', '세포 보호'],

    # --- 그룹 4: 대상 특화 ---
    '남성 건강': ['남성', '전립선', '지구력', '활력'],
    '여성 건강/PMS': ['여성', '월경', '생리 전', '질 건강'],
    '임신/임신준비': ['임신', '수유', '태아', '엽산']
}


# --- 1. 데이터베이스 스키마 생성 ---
def create_database_schema():
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
            print(f"기존 {DB_FILE} 파일을 삭제했습니다.")
        except PermissionError:
            print(f"오류: {DB_FILE} 파일을 다른 프로그램이 사용 중입니다. 닫고 다시 시도해주세요.")
            exit()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    cursor.execute('''CREATE TABLE T_USER_SELECTION (selection_id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(100) NOT NULL UNIQUE, group_name VARCHAR(100));''')
    cursor.execute('''CREATE TABLE T_INGREDIENT (ingredient_id INTEGER PRIMARY KEY AUTOINCREMENT, name_kor VARCHAR(100) NOT NULL UNIQUE, summary TEXT, rda TEXT, ul TEXT);''')
    cursor.execute('''CREATE TABLE T_REC_MAPPING (mapping_id INTEGER PRIMARY KEY AUTOINCREMENT, selection_id INTEGER NOT NULL, ingredient_id INTEGER NOT NULL, base_score INTEGER DEFAULT 10, FOREIGN KEY (selection_id) REFERENCES T_USER_SELECTION(selection_id), FOREIGN KEY (ingredient_id) REFERENCES T_INGREDIENT(ingredient_id), UNIQUE(selection_id, ingredient_id));''')
    cursor.execute('''CREATE TABLE T_SAFETY (safety_id INTEGER PRIMARY KEY AUTOINCREMENT, ingredient_id INTEGER NOT NULL, target_type VARCHAR(50) DEFAULT '기타', target_name VARCHAR(100) DEFAULT '주의', risk_level INTEGER DEFAULT 2, warning_message TEXT NOT NULL, FOREIGN KEY (ingredient_id) REFERENCES T_INGREDIENT(ingredient_id));''')
    cursor.execute('''CREATE TABLE T_PRODUCT (product_id INTEGER PRIMARY KEY AUTOINCREMENT, product_name VARCHAR(255) NOT NULL, company_name VARCHAR(100), main_ingredients_text TEXT, precautions TEXT, api_source_id VARCHAR(100) UNIQUE);''')
    
    print("5개 테이블 스키마 생성 완료.")
    conn.commit()
    conn.close()

# --- 2. 사용자 선택지 (수동 입력) ---
def populate_user_selections():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 동의어 사전의 키(Key)들을 선택지 이름으로 사용
    selections_data = [
        ('피로/활력', '건강 관리'), ('간 건강', '건강 관리'), ('다이어트/체지방', '건강 관리'),
        ('혈액순환/콜레스테롤', '건강 관리'), ('혈당 관리', '건강 관리'), ('혈압 관리', '건강 관리'),
        ('눈 건강', '신체 부위'), ('뼈/관절/근육', '신체 부위'), ('위/소화', '신체 부위'),
        ('장 건강/변비', '신체 부위'), ('피부', '신체 부위'), ('모발/두피/손톱', '신체 부위'),
        ('구강 관리', '신체 부위'), ('면역력/알러지', '일상/정신'), ('수면 질 개선', '일상/정신'),
        ('스트레스/마음건강', '일상/정신'), ('기억력/인지력', '일상/정신'), ('항노화/항산화', '일상/정신'),
        ('남성 건강', '대상 특화'), ('여성 건강/PMS', '대상 특화'), ('임신/임신준비', '대상 특화')
    ]
    
    cursor.executemany("INSERT OR IGNORE INTO T_USER_SELECTION (name, group_name) VALUES (?, ?)", selections_data)
    conn.commit()
    conn.close()
    print(f"사용자 선택지 {len(selections_data)}개 입력 완료.")

# --- 헬퍼 함수들 ---
def get_user_selections_dict(cursor):
    cursor.execute("SELECT name, selection_id FROM T_USER_SELECTION")
    return {name: sel_id for name, sel_id in cursor.fetchall()}

def parse_safety_keywords(warning_text):
    if "임산부" in warning_text or "수유부" in warning_text: return ('연령', '임산부/수유부')
    if "질환" in warning_text or "의약품" in warning_text or "고혈압" in warning_text or "당뇨" in warning_text: return ('의약품/질환', '복용약 확인')
    if "알레르기" in warning_text or "과민" in warning_text: return ('체질', '알레르기')
    if "어린이" in warning_text or "영유아" in warning_text: return ('연령', '어린이')
    return ('기타', '주의')

# --- 3. [API 1] 성분 데이터 - 전체 데이터 반복 호출 ---
def fetch_and_populate_ingredients_ALL():
    print("\n--- API 1 (개별인정형 - I-0050) 전체 데이터 연동 시작 ---")
    service_code = "I-0050"
    batch_size = 500
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    start_idx = 1
    total_ingr = 0
    total_safe = 0
    total_map = 0

    while True:
        end_idx = start_idx + batch_size - 1
        API_URL = f"http://openapi.foodsafetykorea.go.kr/api/{API_KEY}/{service_code}/json/{start_idx}/{end_idx}"
        print(f"[API 1] 요청 범위: {start_idx} ~ {end_idx} 호출 중...")

        try:
            response = requests.get(API_URL, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if service_code not in data or 'row' not in data[service_code] or not data[service_code]['row']:
                print(f"[API 1] 더 이상 데이터가 없습니다. 종료합니다. (마지막 요청 시작점: {start_idx})")
                break

            c_ingr, c_safe, c_map = process_ingredient_data_batch(data, service_code)
            total_ingr += c_ingr
            total_safe += c_safe
            total_map += c_map

            start_idx += batch_size
            time.sleep(0.5)

        except Exception as e:
            print(f"[API 1] 오류 발생 ({start_idx}~{end_idx}): {e}")
            break

    print(f"\n>>> [API 1 최종 완료] 총 성분: {total_ingr}개, 안전규칙: {total_safe}개, 매핑: {total_map}개 <<<")

# --- 동의어 사전을 활용한 매핑 로직 개선 ---
def process_ingredient_data_batch(data, service_code):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    selection_dict = get_user_selections_dict(cursor)
    
    cnt_ingr = 0
    cnt_safe = 0
    cnt_map = 0

    rows = data.get(service_code, {}).get('row', [])
    for item in rows:
        raw_name = item.get('RAWMTRL_NM')
        if not raw_name: continue
        ingr_name = re.split(r'\(', raw_name)[0].strip()

        # 1. 성분 저장
        cursor.execute('''INSERT OR IGNORE INTO T_INGREDIENT (name_kor, summary, rda, ul) VALUES (?, ?, ?, ?)''', 
                       (ingr_name, item.get('PRIMARY_FNCLTY'), item.get('DAY_INTK_LOWLIMIT'), item.get('DAY_INTK_HIGHLIMIT')))
        if cursor.rowcount > 0: cnt_ingr += 1

        cursor.execute("SELECT ingredient_id FROM T_INGREDIENT WHERE name_kor = ?", (ingr_name,))
        res = cursor.fetchone()
        if not res: continue
        ing_id = res[0]

        # 2. 안전성 정보 저장
        cautions = item.get('IFTKN_ATNT_MATR_CN')
        if cautions:
            rules = re.split(r'\(\d\)|\n|①|②|③|④|⑤', cautions)
            for rule in rules:
                rule = rule.strip()
                if len(rule) > 5:
                    t_type, t_name = parse_safety_keywords(rule)
                    cursor.execute('''INSERT INTO T_SAFETY (ingredient_id, warning_message, target_type, target_name) VALUES (?, ?, ?, ?)''', 
                                   (ing_id, rule, t_type, t_name))
                    cnt_safe += 1
        
        # 3. 동의어 사전을 활용한 똑똑한 매핑
        func_text = item.get('PRIMARY_FNCLTY')
        if func_text:
            clean_func_text = func_text.replace('(국문)', '').replace('\n', ' ')
            
            # 모든 사용자 선택지를 순회하며 검사
            for sel_name, sel_id in selection_dict.items():
                # 해당 선택지에 연결된 동의어 리스트를 가져옴 (없으면 빈 리스트)
                search_keywords = SYNONYM_DICT.get(sel_name, [])
                
                is_matched = False
                # 동의어 리스트 중 하나라도 API 텍스트에 포함되어 있는지 확인
                for keyword in search_keywords:
                    if keyword in clean_func_text:
                        is_matched = True
                        break # 하나라도 찾으면 매칭 성공! 더 볼 필요 없음
                
                if is_matched:
                    cursor.execute('''INSERT OR IGNORE INTO T_REC_MAPPING (selection_id, ingredient_id) VALUES (?, ?)''', 
                                   (sel_id, ing_id))
                    if cursor.rowcount > 0: cnt_map += 1

    conn.commit()
    conn.close()
    return cnt_ingr, cnt_safe, cnt_map


# --- 4. [API 2] 제품 데이터 - 전체 데이터 반복 호출 ---
def fetch_and_populate_products_ALL():
    print("\n--- API 2 (품목제조신고 - C003) 전체 데이터 연동 시작 ---")
    service_code = "C003"
    batch_size = 1000
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

    start_idx = 1
    total_prod = 0

    while True:
        end_idx = start_idx + batch_size - 1
        API_URL = f"http://openapi.foodsafetykorea.go.kr/api/{API_KEY}/{service_code}/json/{start_idx}/{end_idx}"
        print(f"[API 2] 요청 범위: {start_idx} ~ {end_idx} 호출 중...")

        try:
            response = requests.get(API_URL, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if service_code not in data or 'row' not in data[service_code] or not data[service_code]['row']:
                print(f"[API 2] 더 이상 데이터가 없습니다. 종료합니다. (마지막 요청 시작점: {start_idx})")
                break

            c_prod = process_product_data_batch(data, service_code)
            total_prod += c_prod

            start_idx += batch_size
            time.sleep(0.5)

        except Exception as e:
            print(f"[API 2] 오류 발생 ({start_idx}~{end_idx}): {e}")
            break

    print(f"\n>>> [API 2 최종 완료] 총 제품: {total_prod}개 저장됨 <<<")

def process_product_data_batch(data, service_code):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cnt_prod = 0
    rows = data.get(service_code, {}).get('row', [])
    
    for item in rows:
        p_name = item.get('PRDLST_NM')
        if not p_name: continue

        cursor.execute('''
            INSERT OR IGNORE INTO T_PRODUCT (product_name, company_name, main_ingredients_text, precautions, api_source_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (p_name, item.get('BSSH_NM'), item.get('RAWMTRL_NM'), item.get('IFTKN_ATNT_MATR_CN'), item.get('PRDLST_REPORT_NO')))
        if cursor.rowcount > 0: cnt_prod += 1

    conn.commit()
    conn.close()
    return cnt_prod

# --- 메인 실행 ---
if __name__ == "__main__":
    create_database_schema()
    populate_user_selections()
    fetch_and_populate_ingredients_ALL()
    fetch_and_populate_products_ALL()
    
    print(f"\n\n=== {DB_FILE} 데이터베이스 구축이 완료되었습니다! ===")