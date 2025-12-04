# 초기 데이터베이스 생성 (최초 1회)

import sqlite3
import requests
import re
import os
import time

# === 설정 및 상수 ===
DB_FILE = 'supplements_final.db'

# API 키 설정 (사용자 제공 키 적용됨)
FOOD_SAFETY_KEY = "5867d3cf82cb40f7b3e1"
DRUG_INFO_KEY = "57bc1b35a117a2e11957d9f69efcd00889ed2caab2780081c0ac2432c21c0275"

# API별 배치 사이즈 설정
BATCH_SIZE_FOOD = 500   # 원료 API
BATCH_SIZE_DRUG = 100   # 의약품 API
BATCH_SIZE_PROD = 500   # 제품 API (안정성을 위해 500으로 설정)

# 헤더 공통 설정
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

# 동의어 사전 (매핑 정확도 향상용)
SYNONYM_DICT = {
    # --- 건강 고민 ---
    '피로/활력': ['피로', '활력', '에너지', '지구력', '운동수행능력', '비타민 B', '홍삼', '옥타코사놀'],
    '간 건강': ['간 건강', '간기능', '알콜', '숙취', '밀크씨슬', '실리마린', '헛개'],
    '다이어트/체지방': ['체지방', '다이어트', '체중', '비만', '가르시니아', '카테킨', '녹차추출물', '시서스'],
    '혈액순환/콜레스테롤': ['혈행', '콜레스테롤', '중성지질', '혈액', '혈전', '오메가3', 'EPA', 'DHA', '감마리놀렌산', '키토산'],
    '혈당 관리': ['혈당', '당뇨', '인슐린', '바나바', '여주', '난소화성말토덱스트린'],
    '혈압 관리': ['혈압', '고혈압', '코엔자임Q10', '나토배양물'],
    '눈 건강': ['눈 건강', '시력', '황반', '수정체', '안구건조', '루테인', '지아잔틴', '비타민 A', '베타카로틴', '아스타잔틴'],
    '뼈/관절/근육': ['뼈', '관절', '근력', '골다공증', '연골', '칼슘', '마그네슘', '비타민 D', 'MSM', '글루코사민', '초록입홍합', '보스웰리아'],
    '위/소화': ['위 점막', '소화', '속쓰림', '헬리코박터', '감초', '매실', '효소'],
    '장 건강/변비': ['장 건강', '배변', '유산균', '프로바이오틱스', '변비', '장내균총', '프리바이오틱스', '식이섬유', '알로에', '차전자피'],
    '피부': ['피부', '자외선', '보습', '주름', '탄력', '콜라겐', '히알루론산', '비타민 C', '스피루리나', '알로에'],
    '모발/두피/손톱': ['모발', '두피', '손톱', '단백질 대사', '비오틴', '맥주효모', '시스틴'],
    '구강 관리': ['구강', '치아', '잇몸', '충치', '프로폴리스', '자일리톨', '칼슘'],
    '면역력/알러지': ['면역', '알레르기', '과민반응', '아연', '프로폴리스', '베타글루칸', '홍삼', '알로에'],
    '수면 질 개선': ['수면', '잠', '스트레스 호르몬', '테아닌', '미강주정', '감태', '락티움'],
    '스트레스/마음건강': ['스트레스', '긴장', '불안', '마음', '테아닌', '마그네슘', '홍경천'],
    '기억력/인지력': ['기억력', '인지', '두뇌', '뇌세포', '오메가3', '포스파티딜세린', '은행잎추출물', '홍삼'],
    '항노화/항산화': ['항산화', '활성산소', '노화', '세포 보호', '비타민 C', '비타민 E', '코엔자임Q10', '셀레늄', '프로폴리스', '카테킨'],
    '남성 건강': ['남성', '전립선', '지구력', '활력', '쏘팔메토', '야관문', '아르기닌', '아연', '마카'],
    '여성 건강/PMS': ['여성', '월경', '생리 전', '질 건강', '감마리놀렌산', '철분', '이소플라본', '백수오'],
    '임신/임신준비': ['임신', '수유', '태아', '엽산', '철분', '비타민 D', '오메가3'],
    
    # --- 복용 약물 관련 키워드 ---
    '해당 없음': [],
    '혈압약': ['혈압', '이뇨제', '베타차단제', '칼슘채널차단제', 'ACE억제제'],
    '고지혈증약/콜레스테롤약': ['고지혈증', '콜레스테롤', '스타틴'],
    '당뇨약': ['당뇨', '혈당강하제', '메트포르민', '인슐린'],
    '혈전 예방약/아스피린': ['혈전', '아스피린', '항응고제', '항혈소판제', '와파린'],
    '위장약/제산제': ['위장약', '제산제', '위산분비억제제', 'PPI', 'H2차단제'],
    '진통제/해열제 (장기 복용)': ['진통제', '해열제', '소염제', 'NSAID', '타이레놀', '이부프로펜'],
    '항생제 (최근 복용 포함)': ['항생제', '항균제', '마이신'],
    '알레르기/염증약': ['알레르기', '비염', '항히스타민제', '스테로이드', '소염효소제', '부신피질호르몬'], 
    '경구 피임약/호르몬제': ['피임약', '호르몬제', '에스트로겐'],
    '갑상선약': ['갑상선', '씬지로이드', '레보티록신'],
    '항우울제/신경정신과약': ['항우울제', '신경정신과', 'SSRI', '세로토닌']
}

# 데이터 마이닝 타겟 목록
TARGET_NUTRIENTS_FOR_MINING = [
    "비타민 C", "비타민 D", "비타민 B1", "비타민 B2", "비타민 B6", "비타민 B12", "나이아신", "판토텐산", "엽산", "비오틴",
    "칼슘", "마그네슘", "철분", "아연", "구리", "망간", "셀레늄", "크롬", "몰리브덴",
    "프로바이오틱스", "오메가3", "코엔자임Q10", "루테인", "밀크씨슬", "프로폴리스"
]


# --- 1. 데이터베이스 스키마 생성 (9개 테이블) ---
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

    # --- 기본 테이블 생성 ---
    cursor.execute('''CREATE TABLE T_USER_SELECTION (selection_id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(100) NOT NULL UNIQUE, group_name VARCHAR(100));''')
    cursor.execute('''CREATE TABLE T_INGREDIENT (ingredient_id INTEGER PRIMARY KEY AUTOINCREMENT, name_kor VARCHAR(100) NOT NULL UNIQUE, summary TEXT, rda TEXT, ul TEXT, source_type VARCHAR(20));''')
    cursor.execute('''CREATE TABLE T_REC_MAPPING (mapping_id INTEGER PRIMARY KEY AUTOINCREMENT, selection_id INTEGER NOT NULL, ingredient_id INTEGER NOT NULL, base_score INTEGER DEFAULT 10, FOREIGN KEY (selection_id) REFERENCES T_USER_SELECTION(selection_id), FOREIGN KEY (ingredient_id) REFERENCES T_INGREDIENT(ingredient_id), UNIQUE(selection_id, ingredient_id));''')
    cursor.execute('''CREATE TABLE T_SAFETY (safety_id INTEGER PRIMARY KEY AUTOINCREMENT, ingredient_id INTEGER NOT NULL, target_type VARCHAR(50) DEFAULT '기타', target_name VARCHAR(100) DEFAULT '주의', risk_level INTEGER DEFAULT 2, warning_message TEXT NOT NULL, FOREIGN KEY (ingredient_id) REFERENCES T_INGREDIENT(ingredient_id));''')
    cursor.execute('''CREATE TABLE T_PRODUCT (product_id INTEGER PRIMARY KEY AUTOINCREMENT, product_name VARCHAR(255) NOT NULL, company_name VARCHAR(100), main_ingredients_text TEXT, precautions TEXT, api_source_id VARCHAR(100) UNIQUE);''')
    cursor.execute('''CREATE TABLE T_USER_PROFILE (user_id INTEGER PRIMARY KEY AUTOINCREMENT, age INTEGER, gender VARCHAR(10), stress_level VARCHAR(10), sleep_quality INTEGER, diet_habits TEXT, medications_etc TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);''')
    cursor.execute('''CREATE TABLE T_USER_CHOICES (user_id INTEGER NOT NULL, selection_id INTEGER NOT NULL, FOREIGN KEY (user_id) REFERENCES T_USER_PROFILE(user_id), FOREIGN KEY (selection_id) REFERENCES T_USER_SELECTION(selection_id), PRIMARY KEY (user_id, selection_id));''')
    cursor.execute('''
        CREATE TABLE T_DRUG (
            drug_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name VARCHAR(255) NOT NULL,
            entp_name VARCHAR(100),
            efficacy TEXT,
            interaction TEXT,
            caution TEXT,
            api_item_seq VARCHAR(50) UNIQUE
        );
    ''')

    # --- 추천 결과 저장 테이블 (추천 이유 컬럼 포함) ---
    cursor.execute('''
        CREATE TABLE T_REC_RESULT (
            result_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            recommended_ingredient_id INTEGER,
            score INTEGER,
            recommended_reasons TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES T_USER_PROFILE(user_id),
            FOREIGN KEY (recommended_ingredient_id) REFERENCES T_INGREDIENT(ingredient_id)
        );
    ''')

    print("총 9개 테이블 스키마 생성 완료.")
    conn.commit()
    conn.close()

# --- 2. 사용자 선택지 기초 데이터 입력 ---
def populate_user_selections():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    selections_data = [
        # --- 건강 고민 ---
        ('피로/활력', '건강 고민'), ('간 건강', '건강 고민'), ('다이어트/체지방', '건강 고민'),
        ('혈액순환/콜레스테롤', '건강 고민'), ('혈당 관리', '건강 고민'), ('혈압 관리', '건강 고민'),
        ('눈 건강', '건강 고민'), ('뼈/관절/근육', '건강 고민'), ('위/소화', '건강 고민'),
        ('장 건강/변비', '건강 고민'), ('피부', '건강 고민'), ('모발/두피/손톱', '건강 고민'),
        ('구강 관리', '건강 고민'), ('면역력/알러지', '건강 고민'), ('수면 질 개선', '건강 고민'),
        ('스트레스/마음건강', '건강 고민'), ('기억력/인지력', '건강 고민'), ('항노화/항산화', '건강 고민'),
        ('남성 건강', '건강 고민'), ('여성 건강/PMS', '건강 고민'), ('임신/임신준비', '건강 고민'),

        # --- ✅ [수정] 특이사항 (별도 그룹으로 분리) ---
        ('임산부/수유부', '특이사항'), ('알레르기/특이체질', '특이사항'),

        # --- 복용 약물 ---
        ('해당 없음', '복용 약물'),
        ('혈압약', '복용 약물'), ('고지혈증약/콜레스테롤약', '복용 약물'), ('당뇨약', '복용 약물'),
        ('혈전 예방약/아스피린', '복용 약물'), ('위장약/제산제', '복용 약물'),
        ('진통제/해열제 (장기 복용)', '복용 약물'), ('항생제 (최근 복용 포함)', '복용 약물'),
        ('알레르기/염증약', '복용 약물'), ('경구 피임약/호르몬제', '복용 약물'),
        ('갑상선약', '복용 약물'), ('항우울제/신경정신과약', '복용 약물')
    ]
    
    cursor.executemany("INSERT OR IGNORE INTO T_USER_SELECTION (name, group_name) VALUES (?, ?)", selections_data)
    conn.commit()
    conn.close()
    print(f"사용자 선택지 입력 완료 (특이사항 그룹 분리됨).")

# --- 헬퍼 함수들 ---
def get_user_selections_dict(cursor):
    cursor.execute("SELECT name, selection_id FROM T_USER_SELECTION")
    return {name: sel_id for name, sel_id in cursor.fetchall()}

def parse_safety_keywords(warning_text):
    if "임산부" in warning_text or "수유" in warning_text: return ('연령', '임산부/수유부')
    if "질환" in warning_text or "의약품" in warning_text or "고혈압" in warning_text or "당뇨" in warning_text: return ('의약품/질환', '복용약 확인')
    if "알레르기" in warning_text or "과민" in warning_text: return ('체질', '알레르기')
    if "어린이" in warning_text or "영유아" in warning_text: return ('연령', '어린이')
    return ('기타', '주의')

def process_mapping_for_ingredient(cursor, ing_id, func_text, selection_dict):
    cnt_map = 0
    if not func_text: return cnt_map
    clean_func_text = func_text.replace('(국문)', '').replace('\n', ' ')
    for sel_name, sel_id in selection_dict.items():
        # ✅ [수정] '건강 고민' 그룹에 속한 선택지만 매핑 대상으로 고려합니다.
        # (특이사항이나 약물은 영양소와 긍정적인 매핑 대상이 아님)
        cursor.execute("SELECT group_name FROM T_USER_SELECTION WHERE selection_id = ?", (sel_id,))
        group_name = cursor.fetchone()[0]
        if group_name != '건강 고민': continue
        
        search_keywords = SYNONYM_DICT.get(sel_name, [])
        if not search_keywords: continue
        is_matched = False
        for keyword in search_keywords:
            if keyword in clean_func_text:
                is_matched = True
                break
        if is_matched:
            cursor.execute('''INSERT OR IGNORE INTO T_REC_MAPPING (selection_id, ingredient_id) VALUES (?, ?)''', (sel_id, ing_id))
            if cursor.rowcount > 0: cnt_map += 1
    return cnt_map


# --- API 1 & 2: 식약처 원료 데이터 (I-0050, I-0040) ---
def fetch_food_safety_ingredients(service_code, source_type_name):
    print(f"\n--- 식약처 원료 API ({service_code}) 연동 시작 ---")
    start_idx = 1
    total_ingr = 0; total_safe = 0; total_map = 0

    while True:
        end_idx = start_idx + BATCH_SIZE_FOOD - 1
        API_URL = f"http://openapi.foodsafetykorea.go.kr/api/{FOOD_SAFETY_KEY}/{service_code}/json/{start_idx}/{end_idx}"
        print(f"[{service_code}] 요청: {start_idx} ~ {end_idx} 호출 중...")

        try:
            response = requests.get(API_URL, headers=HEADERS, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if service_code not in data or 'row' not in data[service_code] or not data[service_code]['row']:
                print(f"[{service_code}] 더 이상 데이터가 없습니다. 종료.")
                break

            c_ingr, c_safe, c_map = process_ingredient_data_batch(data, service_code, source_type_name)
            total_ingr += c_ingr; total_safe += c_safe; total_map += c_map
            start_idx += BATCH_SIZE_FOOD
            time.sleep(0.5)

        except Exception as e:
            print(f"[{service_code}] 오류 발생 ({start_idx}~{end_idx}): {e}")
            break
    print(f">>> [{service_code} 완료] 성분: {total_ingr}, 안전규칙: {total_safe}, 매핑: {total_map} <<<")

def process_ingredient_data_batch(data, service_code, source_type_name):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    selection_dict = get_user_selections_dict(cursor)
    cnt_ingr = 0; cnt_safe = 0; cnt_map = 0

    rows = data.get(service_code, {}).get('row', [])
    for item in rows:
        # ==========================================
        # 1. 원료명(Name) 파싱 로직 개선
        # ==========================================
        # I-0050은 'RAWMTRL_NM', I-0040은 'APLC_RAWMTRL_NM'을 씁니다.
        raw_name = item.get('RAWMTRL_NM') 
        if not raw_name:
            raw_name = item.get('APLC_RAWMTRL_NM')
        
        # 그래도 없으면(혹시 모를 예외) 건너뜀
        if not raw_name: continue
        
        # 이름 정제: "두충우슬추출복합물(KGC08EA)..." -> "두충우슬추출복합물"
        # 괄호 앞부분만 깔끔하게 잘라냅니다.
        ingr_name = re.split(r'\(', raw_name)[0].strip()

        # ==========================================
        # 2. 기능성 내용(Summary) 파싱 로직 개선
        # ==========================================
        # I-0050은 'PRIMARY_FNCLTY', I-0040은 'FNCLTY_CN'을 씁니다.
        func_text = item.get('PRIMARY_FNCLTY')
        if not func_text:
            func_text = item.get('FNCLTY_CN')

        # ==========================================
        # 3. 섭취량(RDA) 파싱 로직 개선
        # ==========================================
        # I-0050은 LOW/HIGH LIMIT으로 나뉘어 있고, I-0040은 DAY_INTK_CN 텍스트 하나입니다.
        rda_text = item.get('DAY_INTK_LOWLIMIT')
        ul_text = item.get('DAY_INTK_HIGHLIMIT')
        
        # I-0040인 경우 (상한/하한 키가 없으면) 섭취량 텍스트 전체를 RDA 컬럼에 넣습니다.
        if not rda_text and not ul_text:
            rda_text = item.get('DAY_INTK_CN')

        # DB 저장 (T_INGREDIENT)
        cursor.execute('''INSERT OR IGNORE INTO T_INGREDIENT (name_kor, summary, rda, ul, source_type) VALUES (?, ?, ?, ?, ?)''', 
                       (ingr_name, func_text, rda_text, ul_text, source_type_name))
        
        if cursor.rowcount > 0: cnt_ingr += 1

        # 방금 저장한(또는 이미 있는) ID 가져오기
        cursor.execute("SELECT ingredient_id FROM T_INGREDIENT WHERE name_kor = ?", (ingr_name,))
        res = cursor.fetchone()
        if not res: continue
        ing_id = res[0]

        # ==========================================
        # 4. 주의사항(Safety) 파싱
        # ==========================================
        cautions = item.get('IFTKN_ATNT_MATR_CN')
        if cautions:
            # 특수문자나 번호 등을 기준으로 쪼개서 저장
            rules = re.split(r'\(\d\)|\n|①|②|③|④|⑤|◆', cautions)
            for rule in rules:
                rule = rule.strip()
                if len(rule) > 5:
                    t_type, t_name = parse_safety_keywords(rule)
                    cursor.execute('''INSERT INTO T_SAFETY (ingredient_id, warning_message, target_type, target_name) VALUES (?, ?, ?, ?)''', 
                                   (ing_id, rule, t_type, t_name))
                    cnt_safe += 1
        
        # 매핑 로직 실행
        cnt_map += process_mapping_for_ingredient(cursor, ing_id, func_text, selection_dict)

    conn.commit()
    conn.close()
    return cnt_ingr, cnt_safe, cnt_map


# --- API 3: e약은요 의약품 정보 ---
def fetch_and_populate_drugs_easy():
    print("\n--- e약은요 API 연동 시작 ---")
    page_no = 1
    total_drugs = 0
    
    while True:
        API_URL = f"https://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList?serviceKey={DRUG_INFO_KEY}&pageNo={page_no}&numOfRows={BATCH_SIZE_DRUG}&type=json"
        print(f"[e약은요] 페이지: {page_no} 호출 중...")

        try:
            response = requests.get(API_URL, headers=HEADERS, timeout=30)
            if response.status_code != 200:
                print(f"[e약은요] 호출 오류: 상태 코드 {response.status_code}")
                break
            
            try:
                data = response.json()
            except requests.exceptions.JSONDecodeError:
                 print(f"[e약은요] JSON 파싱 오류. 종료.")
                 break

            items = data.get('body', {}).get('items', [])
            if not items:
                print(f"[e약은요] 더 이상 데이터가 없습니다. 종료.")
                break
            
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cnt_batch = 0
            for item in items:
                cursor.execute('''
                    INSERT OR IGNORE INTO T_DRUG (item_name, entp_name, efficacy, interaction, caution, api_item_seq)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (item.get('itemName'), item.get('entpName'), item.get('efcyQesitm'), item.get('intrcQesitm'), item.get('atpnQesitm'), item.get('itemSeq')))
                if cursor.rowcount > 0: cnt_batch += 1
            conn.commit()
            conn.close()
            
            total_drugs += cnt_batch
            page_no += 1
            time.sleep(0.5)
            
            total_count = data.get('body', {}).get('totalCount', 0)
            if total_drugs >= total_count and total_count > 0:
                 print("[e약은요] 전체 데이터 수집 완료.")
                 break

        except Exception as e:
            print(f"[e약은요] 오류 발생 (페이지 {page_no}): {e}")
            break
            
    print(f">>> [e약은요 완료] 총 의약품: {total_drugs}개 저장됨 <<<")


# --- API 4: 식약처 제품 정보 (C003) 및 데이터 마이닝 ---
def fetch_and_populate_products_and_mine():
    print("\n--- API 4 (제품 정보 - C003) 연동 및 마이닝 시작 ---")
    service_code = "C003"
    start_idx = 1
    total_prod = 0

    # 1. 제품 데이터 수집
    while True:
        end_idx = start_idx + BATCH_SIZE_PROD - 1
        API_URL = f"http://openapi.foodsafetykorea.go.kr/api/{FOOD_SAFETY_KEY}/{service_code}/json/{start_idx}/{end_idx}"
        print(f"[{service_code}] 요청: {start_idx} ~ {end_idx} 호출 중...")

        try:
            response = requests.get(API_URL, headers=HEADERS, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            if service_code not in data or 'row' not in data[service_code] or not data[service_code]['row']:
                print(f"[{service_code}] 더 이상 데이터가 없습니다. 수집 종료.")
                break

            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            rows = data.get(service_code, {}).get('row', [])
            for item in rows:
                p_name = item.get('PRDLST_NM')
                if not p_name: continue
                cursor.execute('''INSERT OR IGNORE INTO T_PRODUCT (product_name, company_name, main_ingredients_text, precautions, api_source_id) VALUES (?, ?, ?, ?, ?)''', 
                               (p_name, item.get('BSSH_NM'), item.get('RAWMTRL_NM'), item.get('IFTKN_ATNT_MATR_CN'), item.get('PRDLST_REPORT_NO')))
                if cursor.rowcount > 0: total_prod += 1
            conn.commit()
            conn.close()

            start_idx += BATCH_SIZE_PROD
            time.sleep(0.5)

        except Exception as e:
            print(f"[{service_code}] 오류 발생 ({start_idx}~{end_idx}): {e}")
            break
    print(f">>> [{service_code} 완료] 총 제품: {total_prod}개 저장됨 <<<")

    # 2. 데이터 마이닝
    print("\n--- [데이터 마이닝] 제품 정보에서 부족한 영양소 추출 시작 ---")
    mine_nutrients_from_products()

def mine_nutrients_from_products():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    selection_dict = get_user_selections_dict(cursor)
    total_mined = 0; total_mapped = 0

    for nutrient_name in TARGET_NUTRIENTS_FOR_MINING:
        cursor.execute("SELECT ingredient_id FROM T_INGREDIENT WHERE name_kor = ?", (nutrient_name,))
        if cursor.fetchone():
            print(f"[마이닝 건너뜀] '{nutrient_name}'은(는) 이미 DB에 있습니다.")
            continue
            
        cursor.execute('''
            SELECT main_ingredients_text FROM T_PRODUCT 
            WHERE main_ingredients_text LIKE ? 
            ORDER BY LENGTH(main_ingredients_text) DESC LIMIT 1
        ''', (f'%{nutrient_name}%',))
        
        row = cursor.fetchone()
        if row and row[0]:
            func_text = row[0]
            cursor.execute('''
                INSERT INTO T_INGREDIENT (name_kor, summary, source_type)
                VALUES (?, ?, '제품마이닝')
            ''', (nutrient_name, func_text))
            ing_id = cursor.lastrowid
            total_mined += 1
            
            mapped_cnt = process_mapping_for_ingredient(cursor, ing_id, func_text, selection_dict)
            total_mapped += mapped_cnt
            print(f"[마이닝 성공] '{nutrient_name}' 추출 및 매핑 완료 ({mapped_cnt}개 연결)")
        else:
             print(f"[마이닝 실패] '{nutrient_name}' 관련 제품을 찾지 못했습니다.")

    conn.commit()
    conn.close()
    print(f">>> [마이닝 완료] 총 {total_mined}개 영양소 추가, {total_mapped}개 매핑 연결 <<<")


# --- 메인 실행 ---
if __name__ == "__main__":
    start_time = time.time()
    print("=== 데이터베이스 구축 시작 ===")
    
    create_database_schema()
    populate_user_selections()
    
    fetch_food_safety_ingredients("I-0050", "개별인정형API")
    fetch_food_safety_ingredients("I-0040", "고시형API")
    fetch_and_populate_drugs_easy()
    fetch_and_populate_products_and_mine()
    
    end_time = time.time()
    print(f"\n\n=== 🎉 {DB_FILE} 데이터베이스 구축 완료! (소요 시간: {end_time - start_time:.2f}초) ===")