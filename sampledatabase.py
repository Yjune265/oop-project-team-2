import sqlite3
import re
import os

DB_FILE = 'supplements_sample.db'

# --- 1. 데이터베이스 스키마 생성 ---
def create_database_schema():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"기존 {DB_FILE} 파일을 삭제했습니다.")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 테이블 생성 (이전과 동일)
    cursor.execute('''CREATE TABLE T_USER_SELECTION (selection_id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(100) NOT NULL UNIQUE, group_name VARCHAR(100));''')
    cursor.execute('''CREATE TABLE T_INGREDIENT (ingredient_id INTEGER PRIMARY KEY AUTOINCREMENT, name_kor VARCHAR(100) NOT NULL UNIQUE, summary TEXT, rda FLOAT, ul FLOAT);''')
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
    if "질환" in warning_text or "의약품" in warning_text or "고혈압" in warning_text or "당뇨" in warning_text: return ('의약품/질환', '복용약 확인')
    if "알레르기" in warning_text or "과민" in warning_text: return ('체질', '알레르기')
    if "어린이" in warning_text or "영유아" in warning_text: return ('연령', '어린이')
    return ('기타', '주의')

# --- 3. [MOCK] API 1 (성분) 대량 데이터 삽입 ---
def fetch_and_populate_ingredients_MOCK():
    print("\n--- [MOCK] API 1 (성분) 대량 데이터 삽입 시작 ---")
    
    mock_data = {
        "I-0050": {
            "row": [
                {"APLC_RAWMTRL_NM": "핑거루트추출분말", "DAY_INTK_HIGHLIMIT": "600", "DAY_INTK_LOWLIMIT": "0", "PRIMARY_FNCLTY": "자외선에 의한 피부손상으로부터 피부 건강을 유지하는데 도움을 줄 수 있음", "IFTKN_ATNT_MATR_CN": ""},
                {"APLC_RAWMTRL_NM": "토마토추출물", "DAY_INTK_HIGHLIMIT": "15", "DAY_INTK_LOWLIMIT": "6", "PRIMARY_FNCLTY": "항산화에 도움을 줄 수 있음", "IFTKN_ATNT_MATR_CN": ""},
                {"APLC_RAWMTRL_NM": "도라지추출물", "DAY_INTK_HIGHLIMIT": "3", "DAY_INTK_LOWLIMIT": "0", "PRIMARY_FNCLTY": "노인의 인지능력 개선에 도움을 줄 수 있으나...", "IFTKN_ATNT_MATR_CN": ""},
                {"APLC_RAWMTRL_NM": "마테열수추출물", "DAY_INTK_HIGHLIMIT": "3000", "DAY_INTK_LOWLIMIT": "0", "PRIMARY_FNCLTY": "체지방 감소에 도움을 줄 수 있으나...", "IFTKN_ATNT_MATR_CN": ""},
                {"APLC_RAWMTRL_NM": "오메가-3 지방산 함유 유지", "DAY_INTK_HIGHLIMIT": "2000", "DAY_INTK_LOWLIMIT": "1000", "PRIMARY_FNCLTY": "기억력 개선에 도움을 줄 수 있음, 혈행개선", "IFTKN_ATNT_MATR_CN": ""},
                {"APLC_RAWMTRL_NM": "옻나무 추출분말", "DAY_INTK_HIGHLIMIT": "1000", "DAY_INTK_LOWLIMIT": "1000", "PRIMARY_FNCLTY": "갱년기 남성의 건강에 도움을 줄 수 있음", "IFTKN_ATNT_MATR_CN": ""},
                {"APLC_RAWMTRL_NM": "피니톨 분말", "DAY_INTK_HIGHLIMIT": "1000", "DAY_INTK_LOWLIMIT": "1000", "PRIMARY_FNCLTY": "혈당조절에 도움을 줄 수 있으나...", "IFTKN_ATNT_MATR_CN": "당뇨병 치료가 필요한 경우에는 의사와 상담 하에 사용"},
                {"APLC_RAWMTRL_NM": "보이차추출물", "DAY_INTK_HIGHLIMIT": "1000", "DAY_INTK_LOWLIMIT": "0", "PRIMARY_FNCLTY": "체지방 감소에 도움을 줄 수 있음", "IFTKN_ATNT_MATR_CN": ""},
                {"APLC_RAWMTRL_NM": "옥수수배아추출물", "DAY_INTK_HIGHLIMIT": "60", "DAY_INTK_LOWLIMIT": "40", "PRIMARY_FNCLTY": "피부보습에 도움을 줄 수 있음", "IFTKN_ATNT_MATR_CN": ""},
                {"APLC_RAWMTRL_NM": "올리브잎주정추출물", "DAY_INTK_HIGHLIMIT": "1000", "DAY_INTK_LOWLIMIT": "500", "PRIMARY_FNCLTY": "건강한 혈압의 유지에 도움을 줄 수 있음", "IFTKN_ATNT_MATR_CN": "혈압약을 복용하시는 분이 섭취 시에는 의사와 상담"},
                {"APLC_RAWMTRL_NM": "감태추출물", "DAY_INTK_HIGHLIMIT": "500", "DAY_INTK_LOWLIMIT": "500", "PRIMARY_FNCLTY": "수면의 질 개선에 도움을 줄 수 있음", "IFTKN_ATNT_MATR_CN": "요오드 함량이 높은 식품(해조류 등) 섭취 시 주의, 갑상선질환 주의"},
                {"APLC_RAWMTRL_NM": "유비퀴놀", "DAY_INTK_HIGHLIMIT": "100", "DAY_INTK_LOWLIMIT": "10", "PRIMARY_FNCLTY": "항산화에 도움을 줄 수 있으나...", "IFTKN_ATNT_MATR_CN": "임산부 수유부 섭취에 주의"},
                {"APLC_RAWMTRL_NM": "까마귀쪽나무 열매 주정추출물", "DAY_INTK_HIGHLIMIT": "200", "DAY_INTK_LOWLIMIT": "200", "PRIMARY_FNCLTY": "관절건강에 도움을 줄 수 있음", "IFTKN_ATNT_MATR_CN": ""},
                {"APLC_RAWMTRL_NM": "석류추출물", "DAY_INTK_HIGHLIMIT": "2000", "DAY_INTK_LOWLIMIT": "2000", "PRIMARY_FNCLTY": "갱년기 여성의 건강에 도움을 줄 수 있음", "IFTKN_ATNT_MATR_CN": "임산부와 수유부는 섭취를 피하는 것이 좋습니다. 항혈전제를 복용하시는 분은 의사와 상의"},
                {"APLC_RAWMTRL_NM": "원지추출분말", "DAY_INTK_HIGHLIMIT": "300", "DAY_INTK_LOWLIMIT": "300", "PRIMARY_FNCLTY": "성인의 기억력 개선에 도움을 줄 수 있습니다", "IFTKN_ATNT_MATR_CN": "위장장애가 있는 분은 섭취에 주의"},
                {"APLC_RAWMTRL_NM": "테아닌등복합추출물", "DAY_INTK_HIGHLIMIT": "210", "DAY_INTK_LOWLIMIT": "210", "PRIMARY_FNCLTY": "스트레스로 인한 긴장 완화, 기억력 개선", "IFTKN_ATNT_MATR_CN": "테아닌은 카페인과 길항작용이 있으므로 카페인 음료 섭취 삼가"},
                {"APLC_RAWMTRL_NM": "알로에복합추출물분말", "DAY_INTK_HIGHLIMIT": "1680", "DAY_INTK_LOWLIMIT": "420", "PRIMARY_FNCLTY": "혈중 콜레스테롤 수준의 개선, 배변활동", "IFTKN_ATNT_MATR_CN": "임산부, 수유부는 섭취 시 전문가와 상담"},
                {"APLC_RAWMTRL_NM": "L-글루타민", "DAY_INTK_HIGHLIMIT": "5000", "DAY_INTK_LOWLIMIT": "3000", "PRIMARY_FNCLTY": "과도한 운동 후 신체저항능력(면역) 향상에 도움", "IFTKN_ATNT_MATR_CN": "신장 및 간질환이 있는 환자는 섭취 주의"},
                {"APLC_RAWMTRL_NM": "메론추출물", "DAY_INTK_HIGHLIMIT": "1000", "DAY_INTK_LOWLIMIT": "500", "PRIMARY_FNCLTY": "산화스트레스로부터 인체를 보호(항산화), 자외선에 의한 피부홍반개선", "IFTKN_ATNT_MATR_CN": "밀 단백질 알레르기 주의"},
                {"APLC_RAWMTRL_NM": "소나무껍질추출물", "DAY_INTK_HIGHLIMIT": "1130", "DAY_INTK_LOWLIMIT": "1130", "PRIMARY_FNCLTY": "햇볕 또는 자외선에 의한 피부손상으로부터 피부건강유지에 도움", "IFTKN_ATNT_MATR_CN": ""},
                {"APLC_RAWMTRL_NM": "표고버섯균사체", "DAY_INTK_HIGHLIMIT": "2000", "DAY_INTK_LOWLIMIT": "0", "PRIMARY_FNCLTY": "간 건강에 도움을 줌", "IFTKN_ATNT_MATR_CN": ""},
                {"APLC_RAWMTRL_NM": "홍삼농축액", "DAY_INTK_HIGHLIMIT": "3000", "DAY_INTK_LOWLIMIT": "0", "PRIMARY_FNCLTY": "면역력 증진, 피로개선, 기억력 개선, 항산화", "IFTKN_ATNT_MATR_CN": "알레르기 주의"},
            ]
        }
    }
    process_ingredient_data(mock_data, "I-0050")

def process_ingredient_data(data, service_code):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    selection_dict = get_user_selections_dict(cursor)
    
    cnt_ingr = 0
    cnt_safe = 0
    cnt_map = 0

    rows = data.get(service_code, {}).get('row', [])
    for item in rows:
        ingr_name = item.get('APLC_RAWMTRL_NM')
        if not ingr_name: continue

        cursor.execute('''INSERT OR IGNORE INTO T_INGREDIENT (name_kor, summary, rda, ul) VALUES (?, ?, ?, ?)''', (ingr_name, item.get('PRIMARY_FNCLTY'), item.get('DAY_INTK_LOWLIMIT'), item.get('DAY_INTK_HIGHLIMIT')))
        if cursor.rowcount > 0: cnt_ingr += 1

        cursor.execute("SELECT ingredient_id FROM T_INGREDIENT WHERE name_kor = ?", (ingr_name,))
        res = cursor.fetchone()
        if not res: continue
        ing_id = res[0]

        cautions = item.get('IFTKN_ATNT_MATR_CN')
        if cautions:
            rules = re.split(r'[①②③④⑤]|\n|/', cautions)
            for rule in rules:
                rule = rule.strip()
                if len(rule) > 5:
                    t_type, t_name = parse_safety_keywords(rule)
                    cursor.execute('''INSERT INTO T_SAFETY (ingredient_id, warning_message, target_type, target_name) VALUES (?, ?, ?, ?)''', (ing_id, rule, t_type, t_name))
                    cnt_safe += 1
        
        func_text = item.get('PRIMARY_FNCLTY')
        if func_text:
            for keyword, sel_id in selection_dict.items():
                if keyword in func_text:
                    cursor.execute('''INSERT OR IGNORE INTO T_REC_MAPPING (selection_id, ingredient_id) VALUES (?, ?)''', (sel_id, ing_id))
                    if cursor.rowcount > 0: cnt_map += 1

    conn.commit()
    conn.close()
    print(f"[성분 완료] {cnt_ingr}개 성분, {cnt_safe}개 안전규칙, {cnt_map}개 로직 매핑")


# --- 4. [MOCK] API 2 (제품) 대량 데이터 삽입 ---
def fetch_and_populate_products_MOCK():
    print("\n--- [MOCK] API 2 (제품) 대량 데이터 삽입 시작 ---")
    
    mock_data = {
        "C003": {
            "row": [
                {"PRDLST_NM": "고려홍삼농축액", "BSSH_NM": "(주)화인내츄럴", "PRDLST_REPORT_NO": "2004001509475", "RAWMTRL_NM": "홍삼농축액(농축물)", "IFTKN_ATNT_MATR_CN": "알러지 등 특이체질의 경우 성분 확인 후 섭취."},
                {"PRDLST_NM": "가바트리플", "BSSH_NM": "코스맥스엔비티(주)", "PRDLST_REPORT_NO": "20070017035202", "RAWMTRL_NM": "산화아연, 보라지 종자유지, L-글루타민산 유래 GABA 함유 분말", "IFTKN_ATNT_MATR_CN": "임산부와 수유기 여성, 어린이는 섭취에 주의"},
                {"PRDLST_NM": "알로에아보레센스", "BSSH_NM": "(주)한국씨엔에스팜", "PRDLST_REPORT_NO": "20040020007894", "RAWMTRL_NM": "알로에 전잎(알로에아보레센스분말)", "IFTKN_ATNT_MATR_CN": "임산부는 섭취 시 주의하십시오."},
                {"PRDLST_NM": "행복한 한컵 락티움", "BSSH_NM": "태웅식품(주)", "PRDLST_REPORT_NO": "20040020003145", "RAWMTRL_NM": "유단백가수분해물(락티움), 비타민B군", "IFTKN_ATNT_MATR_CN": "우유 및 유제품 알레르기 주의"},
                {"PRDLST_NM": "홍삼타브렛", "BSSH_NM": "풍기인삼농협", "PRDLST_REPORT_NO": "2004001801121", "RAWMTRL_NM": "홍삼분말", "IFTKN_ATNT_MATR_CN": "의약품(당뇨치료제, 혈액항응고제) 복용 시 주의"},
                {"PRDLST_NM": "Silver plus propolis", "BSSH_NM": "(주)하치노다카라코리아", "PRDLST_REPORT_NO": "2004001902921", "RAWMTRL_NM": "프로폴리스추출물", "IFTKN_ATNT_MATR_CN": "프로폴리스에 알레르기를 나타내는 사람은 섭취에 주의"},
                {"PRDLST_NM": "아마가인지방산", "BSSH_NM": "(주)유니쎌팜", "PRDLST_REPORT_NO": "20040020028173", "RAWMTRL_NM": "아마씨유", "IFTKN_ATNT_MATR_CN": "특이체질 등 알러지 체질의 경우 성분을 확인"},
                {"PRDLST_NM": "더블액션임팩트", "BSSH_NM": "코스맥스바이오(주)", "PRDLST_REPORT_NO": "200400200021021", "RAWMTRL_NM": "공액리놀레산, 가르시니아캄보지아 추출물", "IFTKN_ATNT_MATR_CN": "간, 신장, 심장 질환, 알레르기 및 천식이 있거나 의약품 복용 시 전문가와 상담"},
                {"PRDLST_NM": "종근당건강멀티비타민포우먼", "BSSH_NM": "(주)에스엘에스", "PRDLST_REPORT_NO": "2004001706253", "RAWMTRL_NM": "비타민A, 비타민E, 비타민B1, 나이아신, 엽산, 비타민C", "IFTKN_ATNT_MATR_CN": "알레르기 체질이신분은 성분을 확인 후 섭취"},
                {"PRDLST_NM": "미라클", "BSSH_NM": "(주)유니쎌팜", "PRDLST_REPORT_NO": "20040020028166", "RAWMTRL_NM": "가르시니아캄보지아 추출물, 차전자피분말, 치커리", "IFTKN_ATNT_MATR_CN": "알레르기등 특이체질의 경우에는 성분을 확인하신 후 섭취"},
                {"PRDLST_NM": "유한m 오메가-3 비거파워", "BSSH_NM": "코스맥스엔비티(주)", "PRDLST_REPORT_NO": "20070017035215", "RAWMTRL_NM": "정제어유 (오메가-3)", "IFTKN_ATNT_MATR_CN": "특이체질, 알러지 체질인 경우에는 의사와 상담"},
                {"PRDLST_NM": "큐자임", "BSSH_NM": "아미코젠(주)", "PRDLST_REPORT_NO": "20040016037148", "RAWMTRL_NM": "코엔자임Q10 추출물", "IFTKN_ATNT_MATR_CN": ""},
                {"PRDLST_NM": "메가프리미엄골드", "BSSH_NM": "주식회사한미양행", "PRDLST_REPORT_NO": "20040015083497", "RAWMTRL_NM": "보라지 종자유지, 건조효모분말", "IFTKN_ATNT_MATR_CN": ""},
                {"PRDLST_NM": "하이비타큐-B", "BSSH_NM": "네이처퓨어코리아(주)", "PRDLST_REPORT_NO": "2010001900427", "RAWMTRL_NM": "판토텐산칼슘, 비타민B군", "IFTKN_ATNT_MATR_CN": "과량섭취시 부작용이 있을 수 있음"},
                {"PRDLST_NM": "관절애디메틸설폰", "BSSH_NM": "(주)유니쎌팜", "PRDLST_REPORT_NO": "20040020028169", "RAWMTRL_NM": "Opti-MSM, 상어연골추출물", "IFTKN_ATNT_MATR_CN": ""},
                {"PRDLST_NM": "온가족영양소", "BSSH_NM": "콜마비앤에이치(주)", "PRDLST_REPORT_NO": "20060020003446", "RAWMTRL_NM": "비타민E, 철, 아연, 판토텐산, 망간, 비타민A, 비타민D", "IFTKN_ATNT_MATR_CN": "특히 6세 이하는 과량섭취하지 않도록 주의"},
                {"PRDLST_NM": "한삼인홍센칼슘", "BSSH_NM": "코스맥스바이오(주)", "PRDLST_REPORT_NO": "200400200021028", "RAWMTRL_NM": "해조분말(칼슘), 산화마그네슘, 홍삼분말", "IFTKN_ATNT_MATR_CN": "위장장애, 소화불량의 증상이 있을 경우 섭취를 중단"},
                {"PRDLST_NM": "디믹스", "BSSH_NM": "아미코젠(주)", "PRDLST_REPORT_NO": "20040016037147", "RAWMTRL_NM": "녹차추출물분말, 알로에 겔", "IFTKN_ATNT_MATR_CN": "카페인이 함유되어 있어 초조감, 불면 등을 나타낼 수 있음"},
                {"PRDLST_NM": "엑티브표고버섯균사체AHCC", "BSSH_NM": "(주)서흥", "PRDLST_REPORT_NO": "20040020006741", "RAWMTRL_NM": "표고버섯균사체 AHCC", "IFTKN_ATNT_MATR_CN": "임신, 수유부나 의약품을 섭취하시는 분은 본 제품을 드시기 전에 의사와 상담"},
            ]
        }
    }
    process_product_data(mock_data, "C003")

def process_product_data(data, service_code):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cnt_prod = 0
    rows = data.get(service_code, {}).get('row', [])
    for item in rows:
        p_name = item.get('PRDLST_NM')
        if not p_name: continue
        cursor.execute('''INSERT OR IGNORE INTO T_PRODUCT (product_name, company_name, main_ingredients_text, precautions, api_source_id) VALUES (?, ?, ?, ?, ?)''', (p_name, item.get('BSSH_NM'), item.get('RAWMTRL_NM'), item.get('IFTKN_ATNT_MATR_CN'), item.get('PRDLST_REPORT_NO')))
        if cursor.rowcount > 0: cnt_prod += 1
    conn.commit()
    conn.close()
    print(f"[제품 완료] {cnt_prod}개 제품 저장됨")

# --- 메인 실행 ---
if __name__ == "__main__":
    create_database_schema()
    populate_user_selections()
    fetch_and_populate_ingredients_MOCK()
    fetch_and_populate_products_MOCK()
    print(f"\n--- {DB_FILE} 데이터베이스 생성 완료! ---")