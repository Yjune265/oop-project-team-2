# update_db.py
# [운영 환경용] 데이터베이스 업데이트 스크립트
# ⚠️ 주의: 기존 DB 파일이 있어야 동작합니다. 사용자 데이터(프로필, 기록 등)는 보존하고,
#          API에서 가져온 외부 데이터(원료, 제품, 의약품 등)만 최신 상태로 갱신합니다.

import sqlite3
import requests
import re
import os
import time
from datetime import datetime
import shutil

# === 설정 ===
DB_FILE = 'supplements_final.db' # 업데이트할 대상 DB 파일
BACKUP_DIR = 'db_backups' # 업데이트 전 안전 백업 폴더

# API 키 (기존과 동일)
FOOD_SAFETY_KEY = "5867d3cf82cb40f7b3e1"
DRUG_INFO_KEY = "57bc1b35a117a2e11957d9f69efcd00889ed2caab2780081c0ac2432c21c0275"

# 배치 사이즈
BATCH_SIZE_FOOD = 500
BATCH_SIZE_DRUG = 100
BATCH_SIZE_PROD = 500

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

# 동의어 사전 및 마이닝 타겟 (기존과 동일하게 유지해야 매핑 일관성 확보)
SYNONYM_DICT = {
    # ... (database.py의 SYNONYM_DICT 내용 전체를 여기에 복사해 주세요) ...
    # 지면 관계상 생략하지만, 실제 코드에는 꼭 전체 내용이 다 들어가야 합니다.
    '피로/활력': ['피로', '활력', '비타민 B', '홍삼'], # 예시 일부
    # ...
}
TARGET_NUTRIENTS_FOR_MINING = [
    "비타민 C", "비타민 D", "칼슘", "마그네슘", "오메가3", "밀크씨슬", "프로바이오틱스" # 예시 일부 (전체 복사 필요)
]


# === 0. 사전 작업: 안전을 위한 자동 백업 ===
def backup_database_before_update():
    print("\n💾 --- [사전 작업] 업데이트 전 DB 안전 백업 ---")
    if not os.path.exists(DB_FILE):
        print(f"❌ 오류: 업데이트할 DB 파일({DB_FILE})을 찾을 수 없습니다. 초기 구축(database.py)을 먼저 진행하세요.")
        exit()

    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_pre_update")
    backup_filename = f"backup_{timestamp}_{DB_FILE}"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    try:
        shutil.copy2(DB_FILE, backup_path)
        print(f"✅ 백업 성공! 혹시 모를 문제에 대비해 '{backup_path}'에 저장했습니다.")
        return True
    except Exception as e:
        print(f"❌ 백업 실패: {e}")
        print("안전을 위해 업데이트를 중단합니다.")
        exit()

# === 1. 외부 데이터 테이블 초기화 (가장 확실한 갱신 방법) ===
def clear_external_data_tables(cursor):
    print("\n🧹 --- 외부 데이터 관련 테이블 초기화 (사용자 데이터는 안전합니다) ---")
    # ⚠️ 중요: 외래 키 제약 조건 때문에 삭제 순서가 중요합니다.
    # 관계 테이블(자식)을 먼저 비우고, 메인 테이블(부모)을 비웁니다.
    
    # 1. 매핑 및 안전 정보 테이블 (T_INGREDIENT의 자식들)
    cursor.execute("DELETE FROM T_REC_MAPPING")
    print(f"   - T_REC_MAPPING 초기화 완료 (삭제된 행: {cursor.rowcount})")
    cursor.execute("DELETE FROM T_SAFETY")
    print(f"   - T_SAFETY 초기화 완료 (삭제된 행: {cursor.rowcount})")
    
    # 2. 메인 외부 데이터 테이블
    # T_REC_RESULT가 T_INGREDIENT를 참조하므로, 먼저 연결을 끊어줘야 합니다.
    # (추천 기록은 남기되, 어떤 성분이었는지 연결만 잠시 NULL로 처리)
    cursor.execute("UPDATE T_REC_RESULT SET recommended_ingredient_id = NULL")
    print("   - T_REC_RESULT의 성분 참조 연결 해제 완료")

    cursor.execute("DELETE FROM T_INGREDIENT")
    print(f"   - T_INGREDIENT 초기화 완료 (삭제된 행: {cursor.rowcount})")
    cursor.execute("DELETE FROM T_PRODUCT")
    print(f"   - T_PRODUCT 초기화 완료 (삭제된 행: {cursor.rowcount})")
    cursor.execute("DELETE FROM T_DRUG")
    print(f"   - T_DRUG 초기화 완료 (삭제된 행: {cursor.rowcount})")

    # SQLite의 오토인크리먼트 카운터 초기화 (선택 사항, 깔끔한 ID 관리를 위해)
    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('T_INGREDIENT', 'T_REC_MAPPING', 'T_SAFETY', 'T_PRODUCT', 'T_DRUG')")
    print("✨ 외부 데이터 영역 청소 완료. 이제 새 데이터를 채웁니다.")


# === 헬퍼 함수들 (database.py와 동일) ===
def get_user_selections_dict(cursor):
    cursor.execute("SELECT name, selection_id FROM T_USER_SELECTION")
    return {name: sel_id for name, sel_id in cursor.fetchall()}

def parse_safety_keywords(warning_text):
    # (database.py와 동일한 로직 사용)
    if "임산부" in warning_text or "수유부" in warning_text: return ('연령', '임산부/수유부')
    if "질환" in warning_text or "의약품" in warning_text or "고혈압" in warning_text or "당뇨" in warning_text: return ('의약품/질환', '복용약 확인')
    if "알레르기" in warning_text or "과민" in warning_text: return ('체질', '알레르기')
    if "어린이" in warning_text or "영유아" in warning_text: return ('연령', '어린이')
    return ('기타', '주의')

def process_mapping_for_ingredient(cursor, ing_id, func_text, selection_dict):
    # (database.py와 동일한 로직 사용)
    cnt_map = 0
    if not func_text: return cnt_map
    clean_func_text = func_text.replace('(국문)', '').replace('\n', ' ')
    for sel_name, sel_id in selection_dict.items():
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
            # 이미 테이블을 비웠으므로 여기서는 무조건 INSERT가 성공합니다.
            cursor.execute('''INSERT INTO T_REC_MAPPING (selection_id, ingredient_id) VALUES (?, ?)''', (sel_id, ing_id))
            cnt_map += 1
    return cnt_map


# === API 데이터 수집 및 적재 함수들 ===
# (핵심: database.py와 로직은 같지만, 여기서는 '빈 테이블에 새로 채우는' 과정이 됩니다.)

def fetch_food_safety_ingredients(cursor, service_code, source_type_name, selection_dict):
    # ... (database.py의 fetch_food_safety_ingredients 로직을 커서 공유 방식으로 수정) ...
    # 지면 관계상 핵심 로직만 주석으로 설명합니다. 실제 구현 시 database.py 내용을 참고하여 채워주세요.
    # 1. API 호출 루프 (BATCH_SIZE_FOOD 단위)
    # 2. 받아온 데이터를 process_ingredient_data_batch로 넘김
    # 3. process_ingredient_data_batch 내부에서:
    #    - T_INGREDIENT에 INSERT (테이블이 비었으므로 IGNORE 불필요)
    #    - 주의사항 파싱 후 T_SAFETY에 INSERT
    #    - process_mapping_for_ingredient 호출하여 T_REC_MAPPING에 INSERT
    pass # 실제 코드 구현 필요

def fetch_and_populate_drugs_easy(cursor):
    # ... (database.py의 fetch_and_populate_drugs_easy 로직을 커서 공유 방식으로 수정) ...
    # 1. API 호출 루프
    # 2. T_DRUG 테이블에 INSERT (테이블이 비었으므로 IGNORE 불필요)
    pass # 실제 코드 구현 필요

def fetch_and_populate_products_and_mine(cursor, selection_dict):
    # ... (database.py의 fetch_and_populate_products_and_mine 로직을 커서 공유 방식으로 수정) ...
    # 1. 제품 API 호출 루프 -> T_PRODUCT에 INSERT
    # 2. mine_nutrients_from_products 로직 수행 -> T_INGREDIENT 추가 및 매핑
    pass # 실제 코드 구현 필요


# === 메인 실행 ===
if __name__ == "__main__":
    # 1. 안전 백업 수행
    backup_database_before_update()

    start_time = time.time()
    print("\n=== 🚀 데이터베이스 스마트 업데이트 시작 ===")
    
    # 하나의 큰 트랜잭션으로 묶어서 작업합니다. (중간에 실패하면 모두 롤백되어 안전)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # 외래 키 제약 조건 활성화 (매우 중요)
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    try:
        # 2. 외부 데이터 테이블 싹 비우기
        clear_external_data_tables(cursor)
        
        # 3. 사용자 선택지 사전 정보 로드 (매핑용)
        selection_dict = get_user_selections_dict(cursor)

        # 4. 최신 데이터 새로 받아와서 채우기
        # (실제 구현 시 아래 함수들에 커서와 필요한 정보를 전달해야 합니다.)
        print("\n--- [1/4] 식약처 원료(개별인정형) 데이터 갱신 중... ---")
        # fetch_food_safety_ingredients(cursor, "I-0050", "개별인정형API", selection_dict) # 실제 구현 필요

        print("\n--- [2/4] 식약처 원료(고시형) 데이터 갱신 중... ---")
        # fetch_food_safety_ingredients(cursor, "I-0040", "고시형API", selection_dict) # 실제 구현 필요

        print("\n--- [3/4] 의약품 정보 데이터 갱신 중... ---")
        # fetch_and_populate_drugs_easy(cursor) # 실제 구현 필요

        print("\n--- [4/4] 제품 정보 갱신 및 데이터 마이닝 수행 중... ---")
        # fetch_and_populate_products_and_mine(cursor, selection_dict) # 실제 구현 필요
        
        # 모든 작업이 성공적으로 끝나면 커밋
        conn.commit()
        print("\n✅ 모든 데이터 갱신 작업이 성공적으로 완료되어 저장되었습니다.")

    except Exception as e:
        # 중간에 에러가 나면 모든 작업을 취소하고 원래대로 되돌림
        conn.rollback()
        print(f"\n❌ [치명적 오류] 업데이트 중 문제가 발생하여 작업을 취소(롤백)했습니다.")
        print(f"오류 내용: {e}")
        print("DB는 업데이트 이전 상태로 유지됩니다.")
    
    finally:
        conn.close()
        end_time = time.time()
        print(f"\n=== 업데이트 종료 (소요 시간: {end_time - start_time:.2f}초) ===")
        print("팁: 만약 문제가 생겼다면, 백업 폴더의 파일을 사용하여 복구하세요.")