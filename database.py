import sqlite3
import requests
import re
import os

DB_FILE = 'supplements_final.db'
API_KEY = "5867d3cf82cb40f7b3e1"  # 사용자 제공 키

# --- 1. 데이터베이스 스키마 생성 ---
def create_database_schema():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"기존 {DB_FILE} 파일을 삭제했습니다.")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # T_USER_SELECTION (수동 기획)
    cursor.execute('''
    CREATE TABLE T_USER_SELECTION (
        selection_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) NOT NULL UNIQUE,
        group_name VARCHAR(100)
    );
    ''')

    # T_INGREDIENT (I-0050 API로 구축)
    cursor.execute('''
    CREATE TABLE T_INGREDIENT (
        ingredient_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name_kor VARCHAR(100) NOT NULL UNIQUE,
        summary TEXT,
        rda FLOAT, -- 하한선
        ul FLOAT   -- 상한선
    );
    ''')

    # T_REC_MAPPING (API 데이터 매칭으로 구축)
    cursor.execute('''
    CREATE TABLE T_REC_MAPPING (
        mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
        selection_id INTEGER NOT NULL,
        ingredient_id INTEGER NOT NULL,
        base_score INTEGER DEFAULT 10,
        FOREIGN KEY (selection_id) REFERENCES T_USER_SELECTION(selection_id),
        FOREIGN KEY (ingredient_id) REFERENCES T_INGREDIENT(ingredient_id),
        UNIQUE(selection_id, ingredient_id)
    );
    ''')

    # T_SAFETY (I-0050 API로 구축)
    cursor.execute('''
    CREATE TABLE T_SAFETY (
        safety_id INTEGER PRIMARY KEY AUTOINCREMENT,
        ingredient_id INTEGER NOT NULL,
        target_type VARCHAR(50) DEFAULT '기타',
        target_name VARCHAR(100) DEFAULT '주의',
        risk_level INTEGER DEFAULT 2,
        warning_message TEXT NOT NULL,
        FOREIGN KEY (ingredient_id) REFERENCES T_INGREDIENT(ingredient_id)
    );
    ''')

    # T_PRODUCT (C003 API로 구축)
    cursor.execute('''
    CREATE TABLE T_PRODUCT (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name VARCHAR(255) NOT NULL,
        company_name VARCHAR(100),
        main_ingredients_text TEXT,
        precautions TEXT,
        api_source_id VARCHAR(100) UNIQUE
    );
    ''')
    
    print("5개 테이블 스키마 생성 완료.")
    conn.commit()
    conn.close()

# --- 2. 사용자 선택지 (수동 입력) ---
def populate_user_selections():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    selections = [
        ('간 건강', '주요 장기'), ('눈 건강', '주요 장기'), ('관절', '신체 부위'),
        ('피부', '신체 부위'), ('갱년기', '특정 대상'), ('면역', '기능'),
        ('피로', '기능'), ('혈액흐름', '기능'), ('기억력', '기능'),
        ('항산화', '기능'), ('수면', '기능'), ('스트레스', '기능'),
        ('혈압', '기능'), ('체지방 감소', '기능'), ('배변활동', '기능'),
        ('혈당조절', '기능'), ('콜레스테롤', '기능'), ('인지능력', '기능')
    ]
    cursor.executemany("INSERT OR IGNORE INTO T_USER_SELECTION (name, group_name) VALUES (?, ?)", selections)
    conn.commit()
    conn.close()

# --- 헬퍼 함수들 ---
def get_user_selections_dict(cursor):
    cursor.execute("SELECT name, selection_id FROM T_USER_SELECTION")
    return {name: sel_id for name, sel_id in cursor.fetchall()}

def parse_safety_keywords(warning_text):
    if "임산부" in warning_text or "수유부" in warning_text: return ('연령', '임산부/수유부')
    if "질환" in warning_text or "의약품" in warning_text: return ('의약품/질환', '복용약 확인')
    if "알레르기" in warning_text: return ('체질', '알레르기')
    if "어린이" in warning_text or "영유아" in warning_text: return ('연령', '어린이')
    return ('기타', '주의')

# --- 3. [API 1] 성분 데이터 구축 (I-0050: 개별인정형) ---
def fetch_and_populate_ingredients():
    print("\n--- API 1 (개별인정형 - I-0050) 연동 시작 ---")
    
    # [수정] 서비스 코드 I-0050 사용
    service_code = "I-0050"
    # 테스트를 위해 100개만 호출
    API_URL = f"http://openapi.foodsafetykorea.go.kr/api/{API_KEY}/{service_code}/json/1/100"

    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        data = response.json()
        
        if service_code in data and 'row' in data[service_code]:
            process_ingredient_data(data, service_code)
        else:
            print(f"API 1 (I-0050) 데이터 없음: {data}")

    except Exception as e:
        print(f"API 1 오류: {e}")

def process_ingredient_data(data, service_code):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    selection_dict = get_user_selections_dict(cursor)
    
    cnt_ingr = 0
    cnt_safe = 0
    cnt_map = 0

    rows = data.get(service_code, {}).get('row', [])
    for item in rows:
        # I-0050 키 값 매핑
        ingr_name = item.get('APLC_RAWMTRL_NM') # 신청원료명
        if not ingr_name: continue

        # 1. T_INGREDIENT 저장
        cursor.execute('''
            INSERT OR IGNORE INTO T_INGREDIENT (name_kor, summary, rda, ul)
            VALUES (?, ?, ?, ?)
        ''', (
            ingr_name,
            item.get('PRIMARY_FNCLTY'),     # 주된기능성
            item.get('DAY_INTK_LOWLIMIT'),  # 1일 섭취량 하한선
            item.get('DAY_INTK_HIGHLIMIT')  # 1일 섭취량 상한선
        ))
        if cursor.rowcount > 0: cnt_ingr += 1

        # ID 조회
        cursor.execute("SELECT ingredient_id FROM T_INGREDIENT WHERE name_kor = ?", (ingr_name,))
        res = cursor.fetchone()
        if not res: continue
        ing_id = res[0]

        # 2. T_SAFETY 저장
        cautions = item.get('IFTKN_ATNT_MATR_CN') # 섭취시 주의사항 내용
        if cautions:
            # ①, ② 등으로 나뉘거나 줄바꿈으로 나뉜 문장 분리
            rules = re.split(r'[①②③④⑤]|\n', cautions)
            for rule in rules:
                rule = rule.strip()
                if len(rule) > 5:
                    t_type, t_name = parse_safety_keywords(rule)
                    cursor.execute('''
                        INSERT INTO T_SAFETY (ingredient_id, warning_message, target_type, target_name)
                        VALUES (?, ?, ?, ?)
                    ''', (ing_id, rule, t_type, t_name))
                    cnt_safe += 1
        
        # 3. T_REC_MAPPING 저장 (기능성 매칭)
        func_text = item.get('PRIMARY_FNCLTY')
        if func_text:
            for keyword, sel_id in selection_dict.items():
                if keyword in func_text:
                    cursor.execute('''
                        INSERT OR IGNORE INTO T_REC_MAPPING (selection_id, ingredient_id)
                        VALUES (?, ?)
                    ''', (sel_id, ing_id))
                    if cursor.rowcount > 0: cnt_map += 1

    conn.commit()
    conn.close()
    print(f"[API 1 완료] 성분: {cnt_ingr}, 안전규칙: {cnt_safe}, 매핑: {cnt_map}")


# --- 4. [API 2] 제품 데이터 구축 (C003: 품목제조신고) ---
def fetch_and_populate_products():
    print("\n--- API 2 (품목제조신고 - C003) 연동 시작 ---")
    
    # 서비스 코드 C003 사용
    service_code = "C003"
    API_URL = f"http://openapi.foodsafetykorea.go.kr/api/{API_KEY}/{service_code}/json/1/100"

    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        data = response.json()
        
        if service_code in data and 'row' in data[service_code]:
            process_product_data(data, service_code)
        else:
            print(f"API 2 (C003) 데이터 없음: {data}")

    except Exception as e:
        print(f"API 2 오류: {e}")

def process_product_data(data, service_code):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cnt_prod = 0
    rows = data.get(service_code, {}).get('row', [])
    
    for item in rows:
        # C003 키 값 매핑
        p_name = item.get('PRDLST_NM')
        if not p_name: continue

        cursor.execute('''
            INSERT OR IGNORE INTO T_PRODUCT (
                product_name, company_name, main_ingredients_text, precautions, api_source_id
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            p_name,
            item.get('BSSH_NM'),         # 업소명
            item.get('RAWMTRL_NM'),      # 원재료 (핵심!)
            item.get('IFTKN_ATNT_MATR_CN'), # 섭취시주의사항
            item.get('PRDLST_REPORT_NO') # 품목제조번호 (고유키)
        ))
        if cursor.rowcount > 0: cnt_prod += 1

    conn.commit()
    conn.close()
    print(f"[API 2 완료] 제품: {cnt_prod}개 저장됨")

# --- 메인 실행 ---
if __name__ == "__main__":
    create_database_schema()      # DB 파일 생성
    populate_user_selections()    # 수동 선택지 입력
    fetch_and_populate_ingredients() # I-0050 호출
    fetch_and_populate_products()    # C003 호출
    
    print(f"\n--- {DB_FILE} 구축이 완료되었습니다 ---")